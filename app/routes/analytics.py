"""
Analytics routes for teachers.

Governing authority: DOM-ITR-001 (Interpretation Domain) and SPEC-ITR-001
(Interpretation Observation Specification). Route handlers in this module
render Interpretation outputs computed by app/utils/analytics_engine.py.

Current runtime is in known noncompliance with several DOM v1.2 invariants
(threshold ownership, alert-content prescription, historical-configuration
binding); see DOM-ITR-001 §XIII.b and §XIII.c for the inventory tracked
for downstream remediation.
"""

from datetime import datetime, timedelta
from app.utils.canonical_temporal_resolver import (
    utc_now, ensure_utc,
    canonical_temporal_resolver, SYSTEM_LEVEL_EVALUATION, CLASS_LEVEL_EVALUATION,
)
from flask import Blueprint, session, jsonify, request, flash, redirect, url_for, g
from sqlalchemy import desc

from app.extensions import db, limiter
from app.feats.base import requires_feat_context
from app.auth import admin_required
from app.models import (
    PayrollSettings, RentSettings, ClassEconomy, Seat
)
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_payroll_settings,
    get_rent_settings,
    verify_teacher_owns_class,
)
from app.models import Transaction
from app.services.ledger_service import get_available_balance
from app.utils.join_code import get_display_join_code

# Define allowed window types constant
ALLOWED_WINDOW_TYPES = {'week', 'month', 'pay_cycle', 'rent_cycle'}
from app.utils.analytics_engine import AnalyticsEngine
from app.utils.helpers import render_template_with_fallback as render_template

from jinja2 import TemplateNotFound

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/admin/analytics')


def _anchor_window_end(now_utc: datetime, class_id: str) -> datetime:
    """Align window end to the start of the current class-local day for stable caching."""
    from types import SimpleNamespace
    ctx = SimpleNamespace(class_id=class_id)
    bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=now_utc,
    )
    return bounds.boundary_start_utc

def _active_class_option(user_id: int, class_id: str | None):
    """Build the option dict for the single active class, or None.

    Class isolation (INV-ARC-004 V.1): the analytics dashboard operates on the
    one active canonical class. Ownership is verified, but the class acted upon
    comes from the request context — never from enumerating the teacher's
    classes. Block/section is display-only (V.2) and is not a scope key.
    """
    if not user_id:
        return None
    resolved_class_id = (class_id or '').strip()
    if not resolved_class_id:
        return None
    class_row = verify_teacher_owns_class(resolved_class_id, user_id)
    if not class_row:
        return None
    return {
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
        'block': (class_row.display_name or '').strip().upper(),
        'label': class_row.display_name or class_row.join_code,
    }


def resolve_current_class_context(user_id: int, class_id: str | None):
    """Resolve the active class context using explicit class_id authority.

    Returns ``(selected, available_classes)`` where ``available_classes`` is
    capped at the single active class. There is no per-feature class switcher:
    the sole legal class switcher is the nav-bar context switcher
    (INV-ARC-010).
    """
    selected = _active_class_option(user_id, class_id)
    available_classes = [selected] if selected else []
    return selected, available_classes


def get_block_for_class_id(class_id: str):
    class_row = get_class_economy(class_id)
    if class_row and class_row.display_name:
        return class_row.display_name.strip().upper()
    return None


def _get_payroll_settings_for_class_id(class_id: str):
    """Resolve payroll settings for a selected class via class_id authority."""
    if not class_id:
        return None
    return get_payroll_settings(class_id)


def get_pay_cycle_days(class_id: str | None = None) -> int:
    payroll_settings = _get_payroll_settings_for_class_id(class_id) if class_id else None
    if payroll_settings and payroll_settings.payroll_frequency_days:
        return payroll_settings.payroll_frequency_days
    return 7


def _get_rent_settings_for_class_id(class_id: str):
    """Resolve rent settings for a selected class via class_id authority."""
    if not class_id:
        return None
    return get_rent_settings(class_id)


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
    anchored_end = _anchor_window_end(now, class_id)
    
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

    per SPEC-ITR-001:
    - System health metrics always visible
    - Readable in under 5 seconds
    - Aggregated at class level
    - Auto-updating

    Domain data reaches template via AnalyticsDashboardView + shared layout context
    (join_code, available_classes, current_class_label, current_page).
    All formatting, logic, and ORM access is handled by the builder.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context, ContextResolutionError
        context = resolve_canonical_context()
        user_id = context.user_id
        class_id = context.class_id

        # Resolve the active class directly from canonical class authority.
        class_row = get_class_economy(class_id)
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

    active_alerts = []

    # The "recent economy events" panel is a DOM-ITR-001 contextual-annotation
    # surface that is NOT IMPLEMENTED in v2 (§XIII.a). AuditEvent is a
    # tamper-evident integrity chain, not an Interpretation annotation source, so
    # feeding its rows here mislabels integrity operations as economy events. The
    # dashboard builder reads event fields defensively (so it did not crash like
    # the /events timeline did), but the data is still not lawful Interpretation
    # output. Present no events until the annotation surface is specified.
    recent_events = []

    # Build the page view model using the analytics builder
    # Pass g.canonical_context for SPEC-TIME-001 compliant timezone conversion
    from app.services.analytics.builders import build_analytics_dashboard_view
    dashboard_view = build_analytics_dashboard_view(
        snapshot_orm=snapshot,
        alerts_list=active_alerts,
        events_list=recent_events,
        window_type=window_type,
        window_start=window_start,
        window_end=window_end,
        canonical_execution_context=g.canonical_context,
    )

    return render_template(
        'admin_analytics_dashboard.html',
        view=dashboard_view,
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
    
    alerts_data = []
    
    return jsonify({'alerts': alerts_data})


@analytics_bp.route('/alert/<int:alert_id>/acknowledge', methods=['POST'])
@admin_required
@requires_feat_context("FEAT-ITR-001")
def acknowledge_alert(alert_id):
    """
    Mark an alert as acknowledged by the teacher.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
    except Exception:
        return jsonify({'error': 'No class period selected'}), 400
    
    flash('Alerts are no longer persisted in v2.', 'warning')
    return redirect(url_for('analytics.dashboard'))


@analytics_bp.route('/events')
@admin_required
def events():
    """
    Display contextual analytics events for the currently selected class period.

    per SPEC-ITR-001:
    - Shows rent changes, wage changes, inflation events, etc.
    - Provides context for understanding metric changes.
    """
    try:
        from app.services.context_resolver import resolve_canonical_context
        context = resolve_canonical_context()
        class_id = context.class_id
        from app.models import ClassEconomy
        class_row = get_class_economy(class_id)
        if not class_row:
            raise Exception("No class found")
        join_code = get_display_join_code(class_row.class_id)
        available_classes = [{"class_id": class_id, "join_code": join_code}] # Note: minimal stub for UI
    except Exception:
        flash('You need to set up class periods before viewing analytics.', 'warning')
        return redirect(url_for('admin.students'))
    
    # Economy-event timeline (rent/wage/inflation "contextual annotations") is a
    # DOM-ITR-001 capability that is NOT IMPLEMENTED in v2 (§II, §XIII.a: Annotation
    # Signals absent from runtime — no lawful source exists). The previous code
    # rendered `audit_events` rows here, but AuditEvent is a tamper-evident
    # integrity chain (payload/context digests), not an Interpretation surface, and
    # lacks the fields this timeline needs (event_type, old_value, new_value,
    # description, affected_students) — which raised UndefinedError at render time.
    # Until the Interpretation annotation surface is specified and built, present
    # the template's graceful empty state rather than fabricate events.
    events_list = []

    try:
        return render_template(
            'admin_analytics_events.html',
            events=events_list,
            join_code=join_code,
            available_classes=available_classes
        )
    except TemplateNotFound:
        return jsonify({'events': [], 'join_code': join_code})


@analytics_bp.route('/student/<int:student_id>')
@admin_required
def student_drill_down(student_id):
    """
    Drill-down view for individual student vs CWI.
    
    per SPEC-ITR-001:
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
    class_row = get_class_economy(class_id)
    if not class_row:
        flash('Class period not found.', 'warning')
        return redirect(url_for('admin.students'))
    join_code = class_row.join_code

    # Get student with scoping
    student = Seat.query.filter(
        Seat.id == student_id,
        Seat.class_id == class_id,
    ).first()
    if student is None:
        flash('Student not found for this class period.', 'warning')
        return redirect(url_for('admin.students'))
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=g.canonical_context,
        primitive="current_time",
    )
    now_utc = now_evaluation.canonical_now_utc
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
    current_balance = get_available_balance(seat.id, class_id, "checking")
    
    # Calculate expected balance based on CWI
    # This is a simplified calculation - could be enhanced
    expected_balance = cwi * weeks_enrolled
    
    # Calculate deviation
    if expected_balance > 0:
        deviation = ((current_balance - expected_balance) / expected_balance) * 100
    else:
        deviation = 0
    
    # Get recent transactions (last 30 days)
    thirty_days_ago = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=g.canonical_context,
        primitive="shift_timestamp",
        reference_time_utc=now_utc,
        timestamp=now_utc,
        elapsed_seconds=-(30 * 24 * 60 * 60),
    ).shifted_timestamp_utc
    transaction_rows = Transaction.query.filter(
        Transaction.target_seat_id == seat.id,
        Transaction.class_id == class_id,
        Transaction.timestamp >= thirty_days_ago,
        Transaction.is_void.is_(False)
    ).order_by(Transaction.timestamp.desc()).limit(50).all()
    student_profile = seat.identity_profile
    student_name = student_profile.full_name if student_profile else f"Seat {seat.id}"
    running_balance = current_balance
    recent_transactions = []
    for transaction in transaction_rows:
        recent_transactions.append({
            "timestamp": transaction.timestamp,
            "description": transaction.description,
            "amount": transaction.amount,
            "balance_after_transaction": running_balance,
        })
        running_balance = running_balance - transaction.amount
    
    try:
        return render_template(
            'admin_analytics_student_detail.html',
            student=student,
            student_name=student_name,
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
            'student_name': student_name,
            'current_balance': float(current_balance),
            'expected_balance': float(expected_balance),
            'deviation': deviation,
            'cwi': cwi,
            'recent_transactions': [
                {
                    'timestamp': row["timestamp"].isoformat() if row["timestamp"] else None,
                    'amount': float(row["amount"]),
                    'description': row["description"],
                    'balance_after_transaction': float(row["balance_after_transaction"]),
                }
                for row in recent_transactions
            ],
            'join_code': join_code
        }), 404
