"""
Main routes for Classroom Token Hub.

Contains public-facing utility routes including health checks, legal pages,
debug endpoints, and public hall pass verification.
"""

import unicodedata
from types import SimpleNamespace
from flask import Blueprint, redirect, url_for, jsonify, current_app, session, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, limiter
from app.models import User
from app.hash_utils import hash_username_lookup
from app.utils.helpers import render_template_with_fallback as render_template, is_safe_url
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

# Create blueprint
main_bp = Blueprint('main', __name__)


# -------------------- HOME AND LEGAL PAGES --------------------

@main_bp.route('/')
def home():
    """
    Smart root route:
    - If logged in as student -> Student Dashboard
    - If logged in as system admin -> admin dashboard
    - If logged in as sysadmin -> Sysadmin Dashboard
    - If not logged in -> Redirect to Marketing Site (classroomtokenhub.com)
    """
    # Check for user session and redirect accordingly
    from app.auth import get_current_user

    user = get_current_user()
    if user:
        role = getattr(user.user_role, "value", user.user_role)
        if role == 'sysadmin':
            return redirect(url_for('sysadmin.dashboard'))
        elif role == 'teacher':
            return redirect(url_for('admin.dashboard'))
        elif role == 'student':
            return redirect(url_for('student.dashboard'))
    else:
        # Default: Redirect to marketing site
        # Use environment variable or default to the canonical domain
        marketing_url = current_app.config.get('MARKETING_SITE_URL', 'https://classroomtokenhub.com')
        return redirect(marketing_url)


@main_bp.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        current_app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500


@main_bp.route('/health/deep')
def health_check_deep():
    """
    Extended health check that validates critical system components.

    Checks:
    - Database connectivity
    - Seat table accessibility
    - Administrator table accessibility
    - Hall passes table accessibility (if accessible)

    Returns JSON with component status for detailed monitoring.
    Individual table checks that fail are logged but don't fail the entire check.
    """
    checks = {}
    overall_status = 'ok'

    # Check database connectivity
    try:
        with db.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        checks['database'] = 'connected'
    except SQLAlchemyError as e:
        current_app.logger.exception('Database connectivity check failed')
        checks['database'] = 'error'
        overall_status = 'degraded'

    # Check if seat table is accessible
    try:
        with db.engine.connect() as conn:
            seat_count = conn.execute(text('SELECT COUNT(*) FROM seats')).scalar()
        checks['seats_table'] = 'accessible'
        checks['seat_count'] = seat_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Seats table check failed: %s', str(e))
        checks['seats_table'] = 'error'
        overall_status = 'degraded'

    # Check if teacher user rows are accessible
    try:
        teacher_count = User.query.filter(User.user_role == UserRole.TEACHER).count()
        checks['teachers_table'] = 'accessible'
        checks['teacher_count'] = teacher_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Teachers table check failed: %s', str(e))
        checks['teachers_table'] = 'error'
        overall_status = 'degraded'

    # Check if hall pass logs table is accessible (may fail due to RLS/tenant context)
    try:
        with db.engine.connect() as conn:
            hall_pass_count = conn.execute(text('SELECT COUNT(*) FROM hall_pass_logs')).scalar()
        checks['hall_pass_logs_table'] = 'accessible'
        checks['hall_pass_count'] = hall_pass_count
    except SQLAlchemyError as e:
        current_app.logger.warning('Hall pass logs table check failed: %s', str(e))
        checks['hall_pass_logs_table'] = 'not_accessible'
        # Don't mark as degraded - this might be expected due to RLS

    # Audit lineage integrity check (reads operational_events — never runs verifier inline)
    try:
        with db.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT level, payload
                FROM operational_events
                WHERE level IN ('ERROR', 'CRITICAL')
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            """)).mappings().first()
        if row is None:
            checks['audit_lineage'] = 'not_initialized'
            checks['audit_lineage_last_checked'] = None
        else:
            checks['audit_lineage'] = 'passing'
            checks['audit_lineage_last_checked'] = None
            checks['audit_lineage_latest_level'] = row.get('level')
            payload = row.get('payload') or {}
            if isinstance(payload, dict):
                checks['audit_lineage_latest_error_type'] = payload.get('error_type')
    except Exception:
        current_app.logger.exception('Audit lineage status check failed')
        checks['audit_lineage'] = 'error'
        overall_status = 'degraded'

    # Return 200 if at least database is working, 500 if database is down
    if checks.get('database') == 'connected':
        return jsonify({
            'status': overall_status,
            'checks': checks
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'error': 'Database connectivity failed',
            'checks': checks
        }), 500


@main_bp.route('/privacy')
def privacy():
    """Render the Privacy & Data Handling Policy page."""
    github_pages_url = current_app.config.get(
        'GITHUB_PAGES_URL',
        'https://timwonderer.github.io/classroom-economy'
    )
    return redirect(f"{github_pages_url}/privacy.html")


@main_bp.route('/terms')
def terms():
    """Render the Terms of Service page."""
    github_pages_url = current_app.config.get(
        'GITHUB_PAGES_URL',
        'https://timwonderer.github.io/classroom-economy'
    )
    return redirect(f"{github_pages_url}/terms.html")


@main_bp.route('/district')
def district():
    """Render the district assurance brief page."""
    github_pages_url = current_app.config.get(
        'GITHUB_PAGES_URL',
        'https://timwonderer.github.io/classroom-economy'
    )
    return redirect(f"{github_pages_url}/district.html")


@main_bp.route('/offline')
def offline():
    """Render the offline fallback page."""
    return render_template('offline.html')


@main_bp.route('/sw.js')
@limiter.exempt
def service_worker():
    """Serve the service worker file from the root scope.

    Exempt from rate limiting because browsers check this frequently
    for PWA updates and it's a static file that doesn't need protection.
    """
    return current_app.send_static_file('sw.js')


# -------------------- HALL PASS PUBLIC VERIFICATION (NO AUTH REQUIRED) --------------------

def _normalize_first_name(value):
    """Normalize first name: strip, NFKC, lowercase."""
    if not value:
        return ''
    return unicodedata.normalize('NFKC', value.strip().lower())


def _normalize_last_name(value):
    """Normalize last name: strip, NFKC, lowercase."""
    if not value:
        return ''
    return unicodedata.normalize('NFKC', value.strip().lower())


@main_bp.route('/verify/hallpass/<teacher_public_token>', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def verify_hall_pass(teacher_public_token):
    """
    Public hall pass verification for office staff.

    GET:  Show a form with class dropdown, first name, last name fields.
    POST: Verify whether a specific student has a valid hall pass for today.

    Designed per Hall Pass Public Verification Spec v1.0:
    - Reveals no roster
    - Reveals no multi-day history
    - Reveals no internal identifiers
    - Non-enumerable (token-based)
    - Rotatable
    """
    from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, HallPassLog, IdentityProfile, Seat

    _GENERIC_UNAVAILABLE = "Verification page not available."

    teacher_user = User.query.filter_by(hall_pass_verify_token=teacher_public_token).first()

    if not teacher_user:
        return render_template(
            'hall_pass_verify.html',
            unavailable=True,
            message=_GENERIC_UNAVAILABLE
        ), 404

    # Build the display list from the teacher's classes; POST must still resolve
    # the selected class directly by class_id.
    classes_rows = (
        ClassEconomy.query.filter_by(user_id=teacher_user.id)
        .order_by(ClassEconomy.display_name)
        .all()
    )
    def _class_display_label(class_row):
        label_parts = [part for part in (class_row.section, class_row.display_name) if part]
        return " - ".join(label_parts) if label_parts else class_row.class_id

    classes = []
    for c in classes_rows:
        classes.append({
            "class_id": c.class_id,
            "label": _class_display_label(c),
        })

    if request.method == 'GET':
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result=None
        )

    # ---- POST: verification attempt ----
    raw_first_name = request.form.get('first_name', '')
    raw_last_name = request.form.get('last_name', '')
    selected_class_id = request.form.get('class_id', '')

    first_name_norm = _normalize_first_name(raw_first_name)
    last_name_norm = _normalize_last_name(raw_last_name)

    # Reject malformed input uniformly
    if not first_name_norm or not last_name_norm or not selected_class_id:
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result={'outcome': 'no_match'}
        )

    first_name_hash = hash_username_lookup(first_name_norm)
    last_name_hash = hash_username_lookup(last_name_norm)

    # Validate selected class directly under the teacher's ownership boundary.
    selected_class_row = ClassEconomy.query.filter_by(
        class_id=selected_class_id,
        user_id=teacher_user.id,
    ).first()
    if not selected_class_row:
        return render_template(
            'hall_pass_verify.html',
            unavailable=False,
            token=teacher_public_token,
            classes=classes,
            result={'outcome': 'no_match'}
        )

    public_temporal_context = SimpleNamespace(class_id=selected_class_id)
    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=public_temporal_context,
        primitive="evaluation_day_boundaries",
    )
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=public_temporal_context,
        primitive="current_time",
    )

    # Query today's hall pass records for this class scope.
    passes_query = HallPassLog.query.filter(
        HallPassLog.class_id == selected_class_id,
        HallPassLog.timestamp >= day_bounds.boundary_start_utc,
        HallPassLog.timestamp < day_bounds.boundary_end_utc,
    ).order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc())

    # Filter via canonical seat claim hashes. IdentityProfile is display-only.
    # Stop at 2 matches: enough to distinguish unique vs ambiguous.
    matched = []
    for entry in passes_query.yield_per(100):
        seat = Seat.query.filter_by(
            id=entry.requested_by_seat_id,
            class_id=entry.class_id,
            role="student",
        ).first()
        if not seat:
            continue
        if (
            seat.claim_first_name_hash == first_name_hash
            and seat.claim_last_name_hash == last_name_hash
        ):
            matched.append(entry)
        if len(matched) >= 2:
            # Ambiguous — stop early
            break

    if len(matched) == 0:
        result = {'outcome': 'no_match'}
    elif len(matched) > 1:
        result = {'outcome': 'ambiguous'}
    else:
        entry = matched[0]
        class_label = _class_display_label(selected_class_row)
        profile = IdentityProfile.query.filter_by(
            seat_id=entry.requested_by_seat_id,
            class_id=entry.class_id,
        ).first()
        attendance_rows = (
            AttendanceSession.query.filter_by(
                class_id=entry.class_id,
                target_seat_id=entry.requested_by_seat_id,
                hall_pass_id=entry.hall_pass_id,
            )
            .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
            .all()
        )
        left_row = next(
            (
                row for row in attendance_rows
                if row.status == "inactive"
                and row.reason_code == AttendanceReasonCode.HALL_PASS.value
            ),
            None,
        )
        return_row = next(
            (
                row for row in attendance_rows
                if left_row is not None
                and row.status == "active"
                and row.timestamp >= left_row.timestamp
            ),
            None,
        )
        status = "returned" if return_row else "left" if left_row else "approved"
        time_out_str = None
        elapsed_mins = None
        if left_row:
            time_out_str = left_row.timestamp.isoformat().replace('+00:00', 'Z')
            if status == "left":
                elapsed = canonical_temporal_resolver(
                    CLASS_LEVEL_EVALUATION,
                    canonical_execution_context=public_temporal_context,
                    primitive="time_since",
                    reference_time_utc=now_evaluation.canonical_now_utc,
                    start=left_row.timestamp,
                )
                elapsed_mins = elapsed.elapsed_seconds // 60

        return_time_str = None
        if return_row:
            return_time_str = return_row.timestamp.isoformat().replace('+00:00', 'Z')

        result = {
            'outcome': 'match',
            'student_display': " ".join(
                part for part in [
                    getattr(profile, "first_name", None),
                    getattr(profile, "last_name", None),
                ] if part
            ).strip(),
            'class_label': class_label,
            'destination': entry.destination,
            'time_out': time_out_str,
            'status': status,
            'elapsed_mins': elapsed_mins,
            'return_time': return_time_str,
        }

    return render_template(
        'hall_pass_verify.html',
        unavailable=False,
        token=teacher_public_token,
        classes=classes,
        result=result
    )


# -------------------- DEBUG ROUTES --------------------

@main_bp.route('/debug/filters')
def debug_filters():
    """List all available Jinja2 filters for debugging."""
    return jsonify(list(current_app.jinja_env.filters.keys()))


@main_bp.route('/switch-view')
def switch_view():
    """Switches the view between mobile and desktop."""
    view = request.args.get('view', 'mobile')
    next_url = request.args.get('next', url_for('main.home'))

    if view == 'desktop':
        session['force_desktop'] = True
    else:
        session.pop('force_desktop', None)

    if not is_safe_url(next_url):
        return redirect(url_for('main.home'))

    return redirect(next_url)  # nosec # Safe: validated by is_safe_url()


@main_bp.route('/debug/admin-db-test')
def debug_admin_db_test():
    """
    Temporary route to confirm admin and invite codes tables are accessible.
    """
    try:
        admins = User.query.filter(User.user_role == UserRole.TEACHER).all()
        with db.engine.connect() as conn:
            invite_codes_count = conn.execute(text('SELECT COUNT(*) FROM teacher_invite_codes')).scalar()
        return jsonify({
            "admin_count": len(admins),
            "invite_codes_count": invite_codes_count,
            "status": "success"
        }), 200
    except Exception as e:
        current_app.logger.exception("System admin DB test failed")
        return jsonify({"status": "error", "message": "System admin DB test failed due to an internal error."}), 500
