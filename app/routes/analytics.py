"""
Analytics routes for teachers.

Implements the analytics dashboard per analytics-specification.md.

Key Principles:
- System health metrics always visible (5-second readability)
- Visual alerts only (no automatic notifications)
- No Drilldown. Period. All analytics should be displayed as aggregates.
- All metrics CWI-relative
- Trends over snapshots
"""

from datetime import datetime, timedelta
from app.utils.time import utc_now, ensure_utc, day_bounds_utc
from flask import Blueprint, session, jsonify, request, flash, redirect, url_for, g
from sqlalchemy import desc

from app.extensions import db, limiter
from app.feats.base import feat_shell
from app.auth import admin_required
from app.models import (
    AnalyticsAlert, AnalyticsEvent,
    PayrollSettings, RentSettings, ClassEconomy, Seat
)
from app.models import Transaction
from app.utils.join_code import get_display_join_code

# Define allowed window types constant
ALLOWED_WINDOW_TYPES = {'week', 'month', 'pay_cycle', 'rent_cycle'}
from app.utils.analytics_engine import AnalyticsEngine
from app.utils.helpers import render_template_with_fallback as render_template

from jinja2 import TemplateNotFound

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/admin/analytics')


def _anchor_window_end(now_utc: datetime) -> datetime:
    """Align window end to the start of the current class-local day for stable caching."""
    anchor_start_utc, _ = day_bounds_utc(timestamp_utc=now_utc)
    return anchor_start_utc

def get_teacher_class_options(user_id: int):
    if not user_id:
        return []

    classes = ClassEconomy.query.filter_by(user_id=user_id).order_by(ClassEconomy.display_name).all()

    options = []
    for c in classes:
        options.append({
            'class_id': c.class_id,
            'join_code': c.join_code,
            'block': (c.display_name or '').strip().upper(),
            'label': c.display_name or c.join_code
        })

    return options


def resolve_current_class_context(user_id: int, class_id: str | None):
    """Resolve the requested class context using explicit class_id authority."""
    available_classes = get_teacher_class_options(user_id)
    by_class_id = {
        (item.get('class_id') or ''): item
        for item in available_classes
        if item.get('class_id')
    }

    selected = by_class_id.get((class_id or '').strip())

    if not selected:
        return None, available_classes

    return selected, available_classes


def get_block_for_class_id(class_id: str):
    class_row = db.session.get(ClassEconomy, class_id)
    if class_row and class_row.display_name:
        return class_row.display_name.strip().upper()
    return None


def _get_payroll_settings_for_class_id(class_id: str):
    """Resolve payroll settings for a selected class via class_id authority."""
    if not class_id:
        return None

    return (
        PayrollSettings.query.filter(
            PayrollSettings.class_id == class_id,
        )
        .order_by(desc(PayrollSettings.block.isnot(None)))
        .first()
    )


def get_pay_cycle_days(class_id: str | None = None) -> int:
    payroll_settings = _get_payroll_settings_for_class_id(class_id) if class_id else None
    if payroll_settings and payroll_settings.payroll_frequency_days:
        return payroll_settings.payroll_frequency_days
    return 7


def _get_rent_settings_for_class_id(class_id: str):
    """Resolve rent settings for a selected class via class_id authority."""
    if not class_id:
        return None

    return (
        RentSettings.query.filter(
            RentSettings.class_id == class_id,
        )
        
        .first()
    )


def get_rent_cycle_days(class_id: str | None = None) -> int:
    rent_settings = _get_rent_settings_for_class_id(class_id) if class_id else None
    if not rent_settings:
        return 30
    frequency_type = rent_settings.frequency_type or 'monthly'
    if frequency_type == 'daily':
        return 1
    if frequency_type == 'weekly':
        return 7
    if frequency_type == 'custom':
        custom_value = rent_settings.custom_frequency_value or 1
        custom_unit = rent_settings.custom_frequency_unit or 'days'
        if custom_unit == 'weeks':
            return custom_value * 7
        if custom_unit == 'months':
            return custom_value * 30
        return custom_value
    return 30


def get_time_window(
    window_type: str,
    class_id: str,
    custom_start=None,
    custom_end=None
):
    """
    Calculate time window boundaries.
    
    Args:
        window_type: 'week', 'pay_cycle', 'rent_cycle', 'month', 'custom'
        custom_start: Start date for custom window
        custom_end: End date for custom window
    
    Returns:
        Tuple of (window_start, window_end)
    """
    now = utc_now()
    anchored_end = _anchor_window_end(now)
    
    if window_type == 'week':
        # Last 7 days
        window_start = anchored_end - timedelta(days=7)
        window_end = anchored_end
    elif window_type == 'month':
        # Last 30 days
        window_start = anchored_end - timedelta(days=30)
        window_end = anchored_end
    elif window_type == 'pay_cycle':
        # Based on payroll frequency (default 7 days)
        pay_cycle_days = get_pay_cycle_days(class_id=class_id)
        window_start = anchored_end - timedelta(days=pay_cycle_days)
        window_end = anchored_end
    elif window_type == 'rent_cycle':
        # Based on rent frequency (default monthly)
        rent_cycle_days = get_rent_cycle_days(class_id=class_id)
        window_start = anchored_end - timedelta(days=rent_cycle_days)
        window_end = anchored_end
    elif window_type == 'custom' and custom_start and custom_end:
        window_start = custom_start
        window_end = custom_end
    else:
        # Default to week
        window_start = anchored_end - timedelta(days=7)
        window_end = anchored_end
    
    return window_start, window_end


@analytics_bp.route('/')
@admin_required
def dashboard():
    """
    Main analytics dashboard.
    
    Per spec section 4.1:
    - System health metrics always visible
    - Readable in under 5 seconds
    - Aggregated at class level
    - Auto-updating
    """
    try:
        from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
        context = resolve_canonical_context()
        user_id = context.user_id
        class_id = context.class_id
        
        # Resolve the active class directly from canonical class authority.
        class_row = db.session.get(ClassEconomy, class_id)
        if not class_row:
            raise ContextResolutionError("Class not found")
        join_code = get_display_join_code(class_row.class_id)
        selected_class, available_classes = resolve_current_class_context(user_id, class_id)
        if not selected_class:
            raise ContextResolutionError("No class context available")
    except Exception as e:
        flash('You need to set up class periods before viewing analytics.', 'warning')
        return redirect(url_for('admin.students'))

    # Get or set time window preference, validated against allowed values
    requested_window_type = request.args.get('window', 'week')
    window_type = requested_window_type if requested_window_type in ALLOWED_WINDOW_TYPES else 'week'
    
    # Calculate time window
    window_start, window_end = get_time_window(window_type, class_id)
    
    # Initialize analytics engine
    engine = AnalyticsEngine(class_id)
    
    # INV-ARC-007: analytics GET must be read-only.
    snapshot = (
        engine.get_snapshot_read_only(window_type, window_start, window_end)
        if getattr(g, "read_only", False)
        else engine.get_or_create_snapshot(window_type, window_start, window_end)
    )
    
    # Get active alerts
    active_alerts = AnalyticsAlert.query.filter(
        AnalyticsAlert.class_id == class_id,
        AnalyticsAlert.window_type == window_type,
        AnalyticsAlert.window_start == window_start,
        AnalyticsAlert.window_end == window_end,
        AnalyticsAlert.resolved_at.is_(None)
    ).order_by(
        # Sort by severity: critical, warning, info
        desc(AnalyticsAlert.severity == 'critical'),
        desc(AnalyticsAlert.severity == 'warning'),
        AnalyticsAlert.created_at.desc()
    ).all()
    
    # Get recent events for context
    recent_events = AnalyticsEvent.query.filter(
        AnalyticsEvent.class_id == class_id,
        AnalyticsEvent.event_date >= window_start,
        AnalyticsEvent.event_date <= window_end
    ).order_by(AnalyticsEvent.event_date.desc()).limit(10).all()
    
    return render_template(
        'admin_analytics_dashboard.html',
        snapshot=snapshot,
        alerts=active_alerts,
        events=recent_events,
        window_type=window_type,
        window_start=window_start,
        window_end=window_end,
        join_code=join_code,
        available_classes=available_classes,
        current_class_label=selected_class['label'],
        current_page='analytics'
    )


@analytics_bp.route('/api/snapshot/<window_type>')
@admin_required
@limiter.limit("30 per minute")
def api_snapshot(window_type):
    """
    API endpoint to get analytics snapshot data.
    
    Returns JSON with system health metrics.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
    except Exception:
        return jsonify({'error': 'No class period selected'}), 400

    if window_type not in ALLOWED_WINDOW_TYPES:
        return jsonify({'error': 'Invalid window type'}), 400
    
    # Calculate time window
    window_start, window_end = get_time_window(window_type, class_id)
    
    # Initialize analytics engine
    engine = AnalyticsEngine(class_id)
    
    # INV-ARC-007: analytics GET must be read-only.
    snapshot = (
        engine.get_snapshot_read_only(window_type, window_start, window_end)
        if getattr(g, "read_only", False)
        else engine.get_or_create_snapshot(window_type, window_start, window_end)
    )
    
    # Convert to JSON-serializable format
    snapshot_data = {
        'window_type': snapshot.window_type,
        'window_start': snapshot.window_start.isoformat(),
        'window_end': snapshot.window_end.isoformat(),
        'metrics': {
            'participation_rate': snapshot.participation_rate,
            'money_velocity': snapshot.money_velocity,
            'cwi_deviation_within_20pct': snapshot.cwi_deviation_within_20pct,
            'budget_survival_pass_rate': snapshot.budget_survival_pass_rate,
        },
        'cwi_value': snapshot.cwi_value,
        'trends': {
            'balance': snapshot.balance_trend,
            'velocity': snapshot.velocity_trend,
            'participation': snapshot.participation_trend,
        },
        'context': {
            'total_students': snapshot.total_students,
            'active_students': snapshot.active_students,
            'total_transactions': snapshot.total_transactions,
        },
        'computed_at': snapshot.computed_at.isoformat(),
        'is_complete': snapshot.is_complete
    }
    
    return jsonify(snapshot_data)


@analytics_bp.route('/api/alerts')
@admin_required
@limiter.limit("30 per minute")
def api_alerts():
    """
    API endpoint to retrieve active analytics alerts for the current class period.

    Returns:
        flask.Response: JSON object with either:
            - {"error": "No class period selected"} and HTTP 400 if no join code
              is present in the session, or
            - {"alerts": [...]} with a list of active alerts, each containing
              id, type, severity, what_changed, why_it_matters, suggested_action,
              triggered_at, and acknowledged.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
    except Exception:
        return jsonify({'error': 'No class period selected'}), 400

    requested_window_type = request.args.get('window', 'week')
    window_type = requested_window_type if requested_window_type in ALLOWED_WINDOW_TYPES else 'week'
    window_start, window_end = get_time_window(window_type, class_id)
    
    active_alerts = AnalyticsAlert.query.filter(
        AnalyticsAlert.class_id == class_id,
        AnalyticsAlert.window_type == window_type,
        AnalyticsAlert.window_start == window_start,
        AnalyticsAlert.window_end == window_end,
        AnalyticsAlert.resolved_at.is_(None)
    ).order_by(
        desc(AnalyticsAlert.severity == 'critical'),
        desc(AnalyticsAlert.severity == 'warning'),
        AnalyticsAlert.created_at.desc()
    ).all()
    
    alerts_data = []
    for alert in active_alerts:
        alerts_data.append({
            'id': alert.id,
            'alert_key': alert.alert_key,
            'severity': alert.severity,
            'what_changed': alert.what_changed,
            'why_it_matters': alert.why_it_matters,
            'suggested_action': alert.suggested_action,
            'created_at': alert.created_at.isoformat(),
            'acknowledged': alert.acknowledged_at is not None
        })
    
    return jsonify({'alerts': alerts_data})


@analytics_bp.route('/alert/<int:alert_id>/acknowledge', methods=['POST'])
@admin_required
@feat_shell("FEAT-ANLY-001")
def acknowledge_alert(alert_id):
    """
    Mark an alert as acknowledged by the teacher.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
        from app.models import ClassEconomy
        class_row = db.session.get(ClassEconomy, class_id)
    except Exception:
        return jsonify({'error': 'No class period selected'}), 400
    
    alert = AnalyticsAlert.query.filter(
        AnalyticsAlert.id == alert_id,
        AnalyticsAlert.class_id == class_id,
        AnalyticsAlert.resolved_at.is_(None)
    ).first()
    
    if not alert:
        flash('Alert not found.', 'danger')
        return redirect(url_for('analytics.dashboard'))
    
    alert.acknowledge()
    db.session.flush()
    flash('Alert acknowledged.', 'success')
    
    return redirect(url_for('analytics.dashboard'))


@analytics_bp.route('/events')
@admin_required
def events():
    """
    Display contextual analytics events for the currently selected class period.

    Per spec section 5.2:
    - Shows rent changes, wage changes, inflation events, etc.
    - Provides context for understanding metric changes.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
        from app.models import ClassEconomy
        class_row = db.session.get(ClassEconomy, class_id)
        if not class_row:
            raise Exception("No class found")
        join_code = get_display_join_code(class_row.class_id)
        available_classes = [{"class_id": class_id, "join_code": join_code}] # Note: minimal stub for UI
    except Exception:
        flash('You need to set up class periods before viewing analytics.', 'warning')
        return redirect(url_for('admin.students'))
    
    # Get all events for this class
    events_list = AnalyticsEvent.query.filter(
        AnalyticsEvent.class_id == class_id
    ).order_by(AnalyticsEvent.event_date.desc()).all()
    
    try:
        return render_template(
            'admin_analytics_events.html',
            events=events_list,
            join_code=join_code,
            available_classes=available_classes
        )
    except TemplateNotFound:
        # Fallback: return JSON response if template not found
        events_data = []
        for event in events_list:
            events_data.append({
                'id': event.id,
                'event_type': event.event_type,
                'description': event.description,
                'event_date': event.event_date.isoformat(),
                'affected_students': event.affected_students
            })
        return jsonify({'events': events_data, 'join_code': join_code})


@analytics_bp.route('/student/<int:student_id>')
@admin_required
def student_drill_down(student_id):
    """
    Drill-down view for individual student vs CWI.
    
    Per spec section 4.3:
    - Only available after user interaction (not default view)
    - Must be contextualized with CWI expectations
    - Must explain why the metric matters
    """
    user_id = g.canonical_context.user_id
    class_id = g.canonical_context.class_id
    selected_class, available_classes = resolve_current_class_context(user_id, class_id)
    if not selected_class:
        flash('You need to set up class periods before viewing analytics.', 'warning')
        return redirect(url_for('admin.students'))

    # Get class economy row
    class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
    if not class_row:
        flash('Class period not found.', 'warning')
        return redirect(url_for('admin.students'))

    # Get student with scoping
    student = Seat.query.filter(
        Seat.id == student_id,
        Seat.class_id == class_id,
    ).first()
    if student is None:
        flash('Student not found for this class period.', 'warning')
        return redirect(url_for('admin.students'))
    # Use actual enrollment duration when possible; fall back to 18 weeks if unknown
    weeks_enrolled = 18  # default/fallback for legacy behavior

    # Try to determine when the student enrolled in this class period
    student_seat = student

    enrollment_start = None
    if student_seat is not None and student_seat.claimed_at:
        enrollment_start = student_seat.claimed_at
    elif hasattr(student, "created_at"):
        # Fallback: use the student's created_at if per-class timestamp is unavailable
        enrollment_start = student.created_at

    if enrollment_start is not None:
        now_utc = utc_now()
        # Ensure timezone-aware arithmetic
        enrollment_start_utc = ensure_utc(enrollment_start)

        enrollment_duration_days = (now_utc - enrollment_start_utc).days
        if enrollment_duration_days > 0:
            weeks_enrolled = enrollment_duration_days / 7.0
        else:
            # If enrollment is less than a day old, treat as a very short enrollment
            weeks_enrolled = 0
    
    # Initialize analytics engine
    engine = AnalyticsEngine(class_id)
    cwi = engine._get_cwi()

    seat = student_seat
    if not seat:
        return jsonify({'error': 'Student has no canonical seat in selected class'}), 400
    
    # Get student balance
    current_balance = student.get_checking_balance(
        class_id=class_id,
        seat_id=seat.id,
    )
    
    # Calculate expected balance based on CWI
    # This is a simplified calculation - could be enhanced
    expected_balance = cwi * weeks_enrolled
    
    # Calculate deviation
    if expected_balance > 0:
        deviation = ((current_balance - expected_balance) / expected_balance) * 100
    else:
        deviation = 0
    
    # Get recent transactions (last 30 days)
    thirty_days_ago = utc_now() - timedelta(days=30)
    recent_transactions = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.class_id == class_id,
        Transaction.timestamp >= thirty_days_ago,
        Transaction.is_void.is_(False)
    ).order_by(Transaction.timestamp.desc()).limit(50).all()
    
    try:
        return render_template(
            'admin_analytics_student_detail.html',
            student=student,
            current_balance=current_balance,
            expected_balance=expected_balance,
            deviation=deviation,
            cwi=cwi,
            recent_transactions=recent_transactions,
            join_code=join_code
        )
    except TemplateNotFound:
        # Fallback: return JSON response if template not found
        return jsonify({
            'error': 'Template not found',
            'student_id': student.id,
            'student_name': student.name,
            'current_balance': current_balance,
            'expected_balance': expected_balance,
            'deviation': deviation,
            'cwi': cwi,
            'recent_transactions': [
                {
                    'id': t.id,
                    'timestamp': t.timestamp.isoformat(),
                    'amount': t.amount,
                    'description': t.description
                } for t in recent_transactions
            ],
            'join_code': join_code
        }), 404
