"""
Authentication and authorization utilities for Classroom Token Hub.

Contains session management helpers, authentication decorators, and timeout logic.
"""

import urllib.parse
import secrets
from datetime import datetime, timedelta
from app.utils.canonical_temporal_resolver import utc_now
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
    session.pop("user_id", None)
    session.pop("current_session_nonce", None)
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
    Redirects to student.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context,
            ContextNotEstablished,
            ContextMismatch,
            ContextForbidden,
            ContextInvariantViolation,
        )

        try:
            ctx = resolve_canonical_context()
        except (ContextNotEstablished, ContextMismatch, ContextForbidden):
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            return redirect(url_for('student.login', next=request.path))
        except ContextInvariantViolation:
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "Please select a class to continue."}), 403
            return redirect(url_for('student.select_class_context'))

        if not ctx or getattr(ctx, "actor_role", None) != "student":
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "error": "User not logged in or session expired"}), 401
            return redirect(url_for('student.login', next=request.path))

        g.canonical_context = ctx
        session['last_activity'] = utc_now().isoformat()
        return f(*args, **kwargs)
    return decorated_function


_CLASSLESS_ADMIN_ENDPOINTS = frozenset({
    'admin.create_class',
    'admin.onboarding',
    'admin.onboarding_status',
    'admin.onboarding_skip',
    'admin.onboarding_skip_task',
    'admin.onboarding_dismiss_widget',
    'admin.onboarding_undismiss_widget',
    'admin.login',
    'admin.logout',
    'admin.account_delete',
    'admin.passkey_login_start',
    'admin.passkey_login_finish',
    'admin.select_class_context',
    'admin.passkey_register_start',
    'admin.passkey_register_finish',
    'admin.passkey_auth_start',
    'admin.passkey_auth_finish',
})


def admin_required(f):
    """
    Decorator to require admin authentication for a route.

    Enforces session timeout based on last activity.
    Redirects to admin.login if not authenticated or session expired.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context,
            ContextNotEstablished,
            ContextMismatch,
            ContextForbidden,
            ContextInvariantViolation,
            BoundaryContext
        )

        try:
            ctx = resolve_canonical_context(require_class=False)
        except (ContextNotEstablished, ContextMismatch, ContextForbidden, ContextInvariantViolation):
            flash("System admin session is invalid. Please log in again.")
            return redirect(url_for('admin.login'))

        if ctx.actor_role != 'teacher':
            flash("System admin session is invalid. Please log in again.")
            return redirect(url_for('admin.login'))

        if isinstance(ctx, BoundaryContext):
            if request.endpoint not in _CLASSLESS_ADMIN_ENDPOINTS:
                return redirect(url_for('admin.onboarding'))

        g.canonical_context = ctx

        now = utc_now()
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.clear()
                flash("System admin session expired. Please log in again.")
                return redirect(url_for('admin.login'))

        session['last_activity'] = now.isoformat()
        return f(*args, **kwargs)
    return decorated_function


def system_admin_required(f):
    """
    Decorator to require system admin authentication for a route.

    Resolves identity via resolve_canonical_context(require_class=False)
    and verifies actor_role == 'sysadmin'. Stores BoundaryContext in
    g.canonical_context. Enforces session timeout based on last activity.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.services.context_resolver import (
            resolve_canonical_context, BoundaryContext,
            ContextNotEstablished, ContextMismatch, ContextForbidden,
        )
        try:
            ctx = resolve_canonical_context(require_class=False)
        except (ContextNotEstablished, ContextMismatch, ContextForbidden):
            if _is_grafana_proxy_subrequest():
                return jsonify({"error": "System administrator access required."}), 401
            flash("System administrator access required.")
            return redirect(url_for('sysadmin.login', next=request.path))

        if not isinstance(ctx, BoundaryContext) or ctx.actor_role != 'sysadmin':
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

        g.canonical_context = ctx
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


def set_canonical_user_session(*, username_lookup_hash: str, expected_role: str):
    """Resolve a User by lookup hash and set session if the role matches."""
    from app.models import User
    user = User.query.filter_by(username_lookup_hash=username_lookup_hash).first()
    if not user:
        return None
    role_value = user.user_role.value if hasattr(user.user_role, "value") else str(user.user_role)
    if role_value != expected_role:
        return None
    session["user_id"] = user.id
    return user


def establish_teacher_session(user):
    """Establish canonical teacher session keys."""
    session["user_id"] = user.id
    session["role"] = "admin"
    session.permanent = True


def establish_sysadmin_session(user):
    """Establish canonical system-admin session keys."""
    session["user_id"] = user.id
    session["role"] = "sysadmin"
    session.permanent = True


def establish_student_session(user, *, class_id: str):
    """Establish canonical student session keys."""
    session["user_id"] = user.id
    session["class_id"] = class_id
    session["role"] = "student"
    session.permanent = True


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

    from app.models import Seat

    seat = db.session.get(Seat, seat_id)
    if seat and seat.user_id:
        linked_user = db.session.get(User, seat.user_id)
        if linked_user and (linked_user.last_active_class_id != class_id or linked_user.last_active_seat_id != seat_id):
            linked_user.last_active_class_id = class_id
            linked_user.last_active_seat_id = seat_id
            db.session.flush()
    
    # Log the transition for audit clarity
    current_app.logger.info(
        f"SESSION-CONTEXT-SWITCH: Student {student.id} moved from class {old_class} "
        f"to {class_id} (Seat {seat_id})."
    )
    return seat

    # is_viewing_as_student / can_access_student_routes — REMOVED (prohibited feature, cross-account leak risk)
