"""
Authentication and authorization utilities for Classroom Token Hub.

Contains session management helpers, authentication decorators, and timeout logic.
"""

import urllib.parse
import secrets
from datetime import datetime, timedelta
from app.utils.time import utc_now
from functools import wraps

import sqlalchemy as sa
from flask import session, flash, redirect, url_for, request, current_app, jsonify, abort, g
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.hash_utils import hash_username_lookup
from app.utils.auth_username import normalize_auth_username


# -------------------- SESSION CONFIGURATION --------------------

SESSION_TIMEOUT_MINUTES = 10
SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES = 60


def _table_exists(table_name: str) -> bool:
    """Return whether the current database exposes the given table."""
    conn = db.session.connection()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return whether the current database exposes the given column on a table."""
    if not _table_exists(table_name):
        return False
    conn = db.session.connection()
    inspector = sa.inspect(conn)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def _get_safe_next_path() -> str:
    """
    Return a safe relative path that can be used as a `next` parameter.

    Ensures the value is a same-site path without scheme or host to avoid
    open redirect vulnerabilities if used in a subsequent redirect.
    """
    # Start from the Flask path, which is already URL-decoded and does not
    # include the scheme or host for normal requests.
    raw_path = request.path or "/"

    # Normalize any backslashes to forward slashes to avoid browser quirks.
    raw_path = raw_path.replace("\\", "/")

    # Parse the path in case an attacker has tried to smuggle in a scheme
    # or netloc via malformed input.
    parsed = urllib.parse.urlparse(raw_path)

    # Only allow pure paths without scheme or netloc.
    if parsed.scheme or parsed.netloc:
        return "/"

    path = parsed.path or "/"

    # Disallow protocol-relative style (`//evil.com`) paths.
    if path.startswith("//"):
        return "/"

    # Ensure the path is absolute within this application.
    if not path.startswith("/"):
        path = "/" + path

    return path


def _is_grafana_proxy_subrequest() -> bool:
    path = request.path or ""
    return path.startswith("/sysadmin/grafana/") or path == "/sysadmin/grafana/auth-check"


def _expire_system_admin_session():
    session.pop("is_system_admin", None)
    session.pop("sysadmin_id", None)
    session.pop("user_id", None)
    session.pop("last_activity", None)
    session.pop("sysadmin_auth_username", None)
    session.pop("passkey_sysadmin_auth_username", None)
    session.pop("force_sysadmin_username_migration", None)


def _system_admin_timeout_expired(last_activity) -> bool:
    return (utc_now() - last_activity) > timedelta(minutes=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES)


# -------------------- AUTHENTICATION DECORATORS --------------------

def login_required(f):
    """
    Decorator to require student authentication for a route.

    Enforces a strict 10-minute timeout from login time for students.
    Also allows admins in view-as-student mode to access student routes.
    Redirects to student.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow access if admin is viewing as student
        if is_viewing_as_student():
            # Admins must also have a student context when bypassing login_required
            if 'student_id' not in session:
                session['view_as_student'] = False
                # Return JSON for API requests
                if request.path.startswith('/api/'):
                    return jsonify({"status": "error", "error": "No student context"}), 401
                flash("Select a student before viewing the student experience.")
                return redirect(url_for('admin.dashboard'))

            # Update admin's last activity
            session['last_activity'] = utc_now().isoformat()
            return f(*args, **kwargs)

        # Regular student authentication check
        if 'student_id' not in session:
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")  # nosec # Safe: validated by _get_safe_next_path()

        # Enforce strict 10-minute timeout from login time
        login_time_str = session.get('login_time')
        if not login_time_str:
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('user_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            session.pop('teacher_display_name_cache', None)
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Session is invalid. Please log in again."}), 401
            flash("Session is invalid. Please log in again.")
            return redirect(url_for('student.login'))

        login_time = datetime.fromisoformat(login_time_str)
        if (utc_now() - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('user_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            session.pop('teacher_display_name_cache', None)
            # Return JSON for API requests
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Session expired. Please log in again."}), 401
            flash("Session expired. Please log in again.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('student.login')}?next={encoded_next}")  # nosec # Safe: validated by _get_safe_next_path()

        # Continue to update last_activity for other potential uses, but it no longer controls the timeout
        student = get_logged_in_student()
        if not student:
            session.pop('student_id', None)
            session.pop('user_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            session.pop('teacher_display_name_cache', None)
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Account is inactive. Contact your teacher."}), 403
            flash("Your account is inactive. Contact your teacher.", "error")
            return redirect(url_for('student.login'))

        session['last_activity'] = utc_now().isoformat()
        seat = sync_student_session_context(student)
        if seat is None:
            session.pop('student_id', None)
            session.pop('user_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            session.pop('teacher_display_name_cache', None)
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Account scope is unavailable."}), 403
            flash("Account scope is unavailable.", "error")
            return redirect(url_for('student.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to require admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to admin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"Admin access attempt: session = {dict(session)}")
        if not session.get("is_admin"):
            flash("You must be an admin to view this page.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")  # nosec # Safe: validated by _get_safe_next_path()

        admin = get_current_admin()
        if not admin:
            session.pop("is_admin", None)
            session.pop("admin_id", None)
            session.pop("last_activity", None)
            session.pop("admin_display_name", None)
            session.pop("admin_display_name_admin_id", None)
            flash("Admin session is invalid. Please log in again.")
            next_path = _get_safe_next_path()
            encoded_next = urllib.parse.quote(next_path, safe="")
            return redirect(f"{url_for('admin.login')}?next={encoded_next}")  # nosec # Safe: validated by _get_safe_next_path()

        now = utc_now()
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.clear()
                flash("Admin session expired. Please log in again.")
                next_path = _get_safe_next_path()
                encoded_next = urllib.parse.quote(next_path, safe="")
                return redirect(f"{url_for('admin.login')}?next={encoded_next}")

        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


def system_admin_required(f):
    """
    Decorator to require system admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to sysadmin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_system_admin"):
            if _is_grafana_proxy_subrequest():
                return jsonify({"error": "System administrator access required."}), 401
            flash("System administrator access required.")
            return redirect(url_for('sysadmin.login', next=request.path))
        last_activity = session.get('last_activity')
        now = utc_now()
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            last_activity = last_activity if last_activity.tzinfo else last_activity.replace(tzinfo=utc_now().tzinfo)
            if _system_admin_timeout_expired(last_activity):
                _expire_system_admin_session()
                if _is_grafana_proxy_subrequest():
                    return jsonify({"error": "Session expired. Please log in again."}), 401
                flash("Session expired. Please log in again.")
                return redirect(url_for('sysadmin.login', next=request.path))
        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


# -------------------- HELPER FUNCTIONS --------------------

def is_student_account_active(student):
    """Return True when a student account exists and has not been deleted."""
    return student is not None


def get_logged_in_user():
    """Return the logged-in canonical credential identity, if present."""
    return get_current_user()


def set_canonical_user_session(*, username_lookup_hash: str | None, expected_role: str):
    """Set the canonical user session anchor for a migrated credential principal."""
    from app.models import User

    session.pop("user_id", None)
    if not username_lookup_hash:
        return None

    user = User.query.filter_by(username_lookup_hash=username_lookup_hash).first()
    if not user or getattr(user.user_role, "value", user.user_role) != expected_role:
        return None

    session["user_id"] = user.id
    return user


def find_canonical_user_by_auth_username(username: str, *, expected_role: str):
    """Return the canonical credential principal for a normalized login name."""
    from app.models import User

    normalized = normalize_auth_username(username)
    if not normalized:
        return None

    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(normalized)).first()
    if not user or getattr(user.user_role, "value", user.user_role) != expected_role:
        return None
    return user


def resolve_admin_shadow_for_user(user):
    """Resolve the unique legacy teacher row needed by compatibility routes."""
    from app.models import Admin

    if not user or not user.username_lookup_hash:
        return None
    return Admin.query.filter_by(username_lookup_hash=user.username_lookup_hash).first()


def resolve_system_admin_shadow_for_user(user):
    """Resolve the unique legacy system-admin row needed by compatibility routes."""
    from app.models import SystemAdmin

    if not user or not user.username_lookup_hash:
        return None
    return SystemAdmin.query.filter_by(username_lookup_hash=user.username_lookup_hash).first()


def resolve_student_shadow_for_user(user):
    """Resolve one legacy student shadow through the canonical user's owned seats."""
    from app.models import Seat, Student, IdentityProfile

    if not user:
        return None

    session_student_id = _safe_int_id(session.get("student_id"))
    if session_student_id:
        student = Student.query.filter_by(id=session_student_id).first()
        if student:
            return student

    students = (
        Student.query
        .join(IdentityProfile, IdentityProfile.id == Student.identity_id)
        .join(Seat, Seat.id == IdentityProfile.seat_id)
        .filter(
            Seat.user_id == user.id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
        )
        .distinct()
        .limit(2)
        .all()
    )
    return students[0] if len(students) == 1 else None


def get_current_student_seat():
    """Return the active seat for the current student session, if present."""
    seat = get_current_seat()
    return seat


def _first_present_session_value(*keys):
    """Return the first non-empty value found in session for the provided keys."""
    for key in keys:
        value = session.get(key)
        if value is not None and value != "":
            return value
    return None


def _safe_int_id(value):
    """Return int(value) for integer ID fields when possible, otherwise None."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def get_current_seat():
    """
    Return the current Seat from session context.

    Resolution order:
    1) current_seat_id
    Returns None when canonical seat context cannot be resolved safely.
    """
    from app.models import Seat

    if hasattr(g, "_auth_current_seat_cache"):
        return g._auth_current_seat_cache

    context = getattr(g, "_auth_canonical_context_cache", None)
    if context is None:
        try:
            from app.services.context_resolver import resolve_canonical_context

            context = resolve_canonical_context()
        except Exception:
            context = None
        g._auth_canonical_context_cache = context
    if not context:
        return None
    seat = db.session.get(Seat, context.seat_id)
    if seat:
        g._auth_current_seat_cache = seat
    return seat


def get_current_class_id():
    """
    Return current class identifier from canonical request context.
    """
    context = getattr(g, "_auth_canonical_context_cache", None)
    if context is None:
        try:
            from app.services.context_resolver import resolve_canonical_context, ContextResolutionError

            context = resolve_canonical_context()
        except Exception:
            context = None
        g._auth_canonical_context_cache = context
    return getattr(context, "class_id", None) if context else None


def get_current_user():
    """
    Return the current User from session/seat context.

    Resolution order:
    1) canonical user_id session key
    Returns None when unavailable.
    """
    from app.models import User

    if hasattr(g, "_auth_current_user_cache"):
        return g._auth_current_user_cache

    user_id = _safe_int_id(session.get('user_id'))
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            g._auth_current_user_cache = user
            return user

    return None


def require_seat_context():
    """
    Return a Seat when valid seat context exists.

    Aborts with HTTP 401 when seat context cannot be resolved.
    """
    seat = get_current_seat()
    if seat:
        return seat
    abort(401)


def switch_student_session_context(student, *, class_id: str, seat_id: int):
    """
    CANONICAL SESSION CONTEXT SWITCH.
    Logs the transition and ensures all session keys are synchronized.
    """
    from flask import session, current_app
    from app.models import User
    
    old_class = getattr(getattr(g, "canonical_context", None), "class_id", None)

    # Sync seat/user identifiers via bridge utility
    seat = sync_student_session_context(student, class_id=class_id, seat_id=seat_id)
    if seat and seat.user_id:
        linked_user = db.session.get(User, seat.user_id)
        if linked_user and linked_user.last_active_class_id != class_id:
            linked_user.last_active_class_id = class_id
            db.session.flush()
    
    # Log the transition for audit clarity
    current_app.logger.info(
        f"SESSION-CONTEXT-SWITCH: Student {student.id} moved from class {old_class} "
        f"to {class_id} (Seat {seat_id})."
    )
    return seat


def sync_student_session_context(
    student=None,
    *,
    class_id: str | None = None,
    seat_id: int | None = None,
    join_code: str | None = None,
    allow_writes: bool = False,
):
    """Backfill user/seat session keys for the current class context."""
    from app.models import User, Seat, IdentityProfile

    if student is None and 'student_id' in session:
        student = get_logged_in_student()
    if not student:
        session.pop('user_id', None)
        return None

    target_class_id = class_id
    target_seat_id = seat_id
    seat = None
    explicit_seat_requested = bool(target_seat_id)
    if target_seat_id:
        seat = db.session.get(Seat, target_seat_id)
    
    if not seat and target_class_id:
        seat = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .filter(
                IdentityProfile.id == student.identity_id,
                Seat.class_id == target_class_id,
            )
            .first()
        )

    if seat and not getattr(seat, "claimed_at", None):
        current_app.logger.info(
            "STUDENT-CLAIM-GATE: rejecting unclaimed seat_id=%s for student_id=%s",
            getattr(seat, "id", None),
            student.id,
        )
        seat = None

    # Fail closed when an explicit seat anchor is present but invalid.
    if explicit_seat_requested and seat is None:
        return None

    linked_user = None
    if seat and seat.user_id:
        linked_user = db.session.get(User, seat.user_id)

    if not linked_user:
        linked_user = (
            User.query
            .join(Seat, Seat.user_id == User.id)
            .filter(
                Seat.id == student.identity_profile.seat_id,
                Seat.user_id.isnot(None),
            )
            .order_by(Seat.id.asc())
            .first()
        )

    # Durable identity-scoped class preference: resolve class first, then owned seat.
    if not seat and linked_user and linked_user.last_active_class_id:
        candidate_seat = Seat.query.filter_by(
            user_id=linked_user.id,
            class_id=linked_user.last_active_class_id,
        ).first()
        if candidate_seat:
            seat = candidate_seat
            target_class_id = candidate_seat.class_id

    if not linked_user:
        if not allow_writes:
            linked_user = None
        else:
            linked_user = User(
                username_hash=hash_username_lookup(f"pending_{student.id}_{secrets.token_urlsafe(8)}"),
                password_hash=generate_password_hash(secrets.token_urlsafe(24)),
            )
            db.session.add(linked_user)
            db.session.flush()

    # V2 invariant: seats are provisioned from canonical class setup/claim flow.
    # Missing seat is invalid state and must not be auto-created here.
    if not seat:
        return None

    if seat and linked_user and seat.user_id != linked_user.id and allow_writes:
        seat.user_id = linked_user.id
        db.session.flush()

    if seat:
        if seat.user_id:
            session['user_id'] = seat.user_id
    else:
        session.pop('user_id', None)

    return seat


def get_logged_in_student():
    """
    Get the currently logged-in legacy student shadow from canonical session state.

    Returns:
        Student: The route compatibility Student object, or None if not logged in.
    """
    user = get_current_user()
    if not user:
        return None

    if getattr(user.user_role, "value", user.user_role) != "student":
        return None

    student = resolve_student_shadow_for_user(user)
    if not student:
        return None

    session_student_id = _safe_int_id(session.get("student_id"))
    if session_student_id and session_student_id != student.id:
        return None

    session["student_id"] = student.id
    if not is_student_account_active(student):
        return None
    return student


def get_current_admin():
    """Return the legacy admin route shadow for the current canonical teacher user."""
    if hasattr(g, "_auth_current_admin_cache"):
        return g._auth_current_admin_cache

    if not session.get("is_admin"):
        return None

    user = get_current_user()
    if not user or getattr(user.user_role, "value", user.user_role) != "teacher":
        return None

    admin = resolve_admin_shadow_for_user(user)
    if not admin:
        return None

    session_admin_id = _safe_int_id(session.get("admin_id"))
    if session_admin_id and session_admin_id != admin.id:
        return None

    session["admin_id"] = admin.id
    g._auth_current_admin_cache = admin
    return admin


def get_current_system_admin():
    """Return the legacy sysadmin route shadow for the current canonical sysadmin user."""
    if hasattr(g, "_auth_current_system_admin_cache"):
        return g._auth_current_system_admin_cache

    if not session.get("is_system_admin"):
        return None

    user = get_current_user()
    if not user or getattr(user.user_role, "value", user.user_role) != "sysadmin":
        return None

    sysadmin = resolve_system_admin_shadow_for_user(user)
    if not sysadmin:
        return None

    session_sysadmin_id = _safe_int_id(session.get("sysadmin_id"))
    if session_sysadmin_id and session_sysadmin_id != sysadmin.id:
        return None

    session["sysadmin_id"] = sysadmin.id
    g._auth_current_system_admin_cache = sysadmin
    return sysadmin


def ensure_admin_join_code(admin_id):
    """Validate an existing admin join-code selection without auto-resolving one."""
    from app.models import ClassEconomy  # Imported lazily to avoid circular import

    if not admin_id:
        return

    return


def get_admin_student_query(include_unassigned=True):
    """Return a Student query scoped to the current admin's ownership.

    System admins are allowed to see all students. Regular admins only see
    students whose identity profile is linked to a seat in a class owned by
    this teacher (via Seat → ClassEconomy).

    Args:
        include_unassigned (bool): [DEPRECATED] No longer used. Kept for backward compatibility.
    """
    from app.models import Student, Seat, IdentityProfile, ClassEconomy

    if session.get("is_system_admin"):
        return Student.query

    admin = get_current_admin()
    if not admin:
        return Student.query.filter(sa.text("0=1"))

    # Students linked to this teacher via Seat → ClassEconomy ownership
    teacher_student_ids = (
        db.session.query(Student.id)
        .join(IdentityProfile, IdentityProfile.id == Student.identity_id)
        .join(Seat, Seat.id == IdentityProfile.seat_id)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(ClassEconomy.teacher_id == admin.id)
        .subquery()
    )

    return Student.query.filter(
        Student.id.in_(sa.select(teacher_student_ids)),
    )


def get_student_for_admin(student_id, include_unassigned=True):
    """Return a student the current admin can access, or None."""
    query = get_admin_student_query(include_unassigned=include_unassigned)
    return query.filter_by(id=student_id).first()


def is_viewing_as_student():
    """
    Check if the current user is an admin viewing as a student.

    Returns:
        bool: True if admin is in view-as-student mode, False otherwise.
    """
    return session.get("is_admin") and session.get("view_as_student", False)


def can_access_student_routes():
    """
    Check if the current user can access student routes.

    Returns True if:
    - User is a logged-in student, OR
    - User is an admin in view-as-student mode

    Returns:
        bool: True if user can access student routes, False otherwise.
    """
    return 'student_id' in session or is_viewing_as_student()
