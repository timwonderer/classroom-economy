"""
System Admin routes for Classroom Token Hub.

High-level system administration including admin management, invite codes,
system logs, error monitoring, and debug/testing tools.
"""

import os
import re
import binascii
import secrets
import io
import base64
from urllib.parse import urlparse
import sqlalchemy as sa
import qrcode
import requests
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from app.utils.canonical_temporal_resolver import utc_now, ensure_utc
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify, Response, abort
from flask import g
from sqlalchemy import delete, or_, case
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden, NotFound, ServiceUnavailable
import pyotp

from app.extensions import db, limiter
from app.feats.base import feat_shell
from app.models import (
    Seat, PasskeyCredential,
    Transaction, TransactionStatus, HallPassLog,
    # Legacy tap models are unauthorized; use attendance_sessions (DOM-PROD-001).
    FeatureSettings, RentSettings, BankingSettings,
    HallPassSettings, ClassEconomy, User, UserRole,
    PayrollSettings, StoreItem, Announcement, Issue, IssueStatusHistory, IssueResolutionAction
)
from app.auth import (
    establish_sysadmin_session,
    system_admin_required,
    _expire_system_admin_session,
    _system_admin_timeout_expired,
    find_canonical_user_by_auth_username,
    get_current_user,
)
from app.forms import SystemAdminLoginForm, SystemAdminInviteForm

# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso
from app.utils.encryption import encrypt_totp, decrypt_totp
from app.hash_utils import hash_username_lookup
from app.services import ledger_service
from app.utils.passwordless_client import (
    create_register_token,
    verify_signin_token,
    get_public_api_key
)
from app.utils.auth_username import normalize_auth_username
from app.utils.opaque_refs import make_opaque_ref, resolve_opaque_ref
from app.services.admin_identity_service import (
    count_active_admin_invite_codes,
    create_admin_invite_code,
    create_admin_credential,
    delete_admin_credentials_for_user,
    delete_admin_credential,
    delete_admin_onboarding_for_user,
    delete_admin_account_rows,
    get_admin_invite_code_by_id,
    list_admin_invite_codes,
    admin_has_passkeys,
    list_admin_credentials,
    mark_admin_invite_code_used,
    touch_admin_credentials_last_used,
)
from app.services.announcement_service import (
    create_system_announcement,
    delete_system_announcement,
    update_system_announcement,
)
from app.utils.issue_helpers import record_resolution_action
from app.services.recovery_service import delete_recovery_rows_for_user

# Create blueprint
sysadmin_bp = Blueprint('sysadmin', __name__, url_prefix='/sysadmin')

# Constants
INACTIVITY_THRESHOLD_DAYS = 180  # Number of days of inactivity before highlighting inactive admins


def _resolve_admin_user(admin: User) -> User | None:
    """Resolve the canonical admin user."""
    if not admin or not admin.username_lookup_hash:
        return None
    return User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()


def _resolve_legacy_admin(user: User) -> User | None:
    """Resolve the canonical teacher user for the supplied auth username hash."""
    if not user or not user.username_lookup_hash:
        return None
    return User.query.filter_by(
        username_lookup_hash=user.username_lookup_hash,
        user_role=UserRole.TEACHER,
    ).first()


def _user_student_counts(user_ids: list[int]) -> tuple[dict[int, int], dict[int, dict[str, int]]]:
    """Aggregate claimed student seats per admin user."""
    if not user_ids:
        return {}, {}

    user_students = (
        db.session.query(
            ClassEconomy.user_id.label("user_id"),
            Seat.id.label("seat_id"),
            ClassEconomy.section.label("block"),
        )
        .join(Seat, Seat.class_id == ClassEconomy.class_id)
        .filter(
            ClassEconomy.user_id.in_(user_ids),
            Seat.role == "student",
            Seat.user_id.isnot(None),
            Seat.claimed_at.isnot(None),
        )
        .subquery()
    )

    count_rows = (
        db.session.query(
            user_students.c.user_id,
            db.func.count(user_students.c.seat_id).label("count"),
        )
        .group_by(user_students.c.user_id)
        .all()
    )
    total_counts = {row.user_id: row.count for row in count_rows}

    period_rows = (
        db.session.query(
            user_students.c.user_id,
            user_students.c.block,
            db.func.count(user_students.c.seat_id).label("count"),
        )
        .group_by(user_students.c.user_id, user_students.c.block)
        .all()
    )
    periods: dict[int, dict[str, int]] = {}
    for user_id, block, count in period_rows:
        periods.setdefault(user_id, {})[block] = count
    return total_counts, periods


def _find_sysadmin_by_auth_username(username: str):
    """Lookup sysadmin by lookup hash."""
    normalized = normalize_auth_username(username)
    if not normalized:
        return None

    lookup_hash = hash_username_lookup(normalized)
    return User.query.filter_by(
        username_lookup_hash=lookup_hash,
        user_role=UserRole.SYSADMIN,
    ).first()


def _sysadmin_auth_username_exists(username: str, *, exclude_sysadmin_id: int | None = None) -> bool:
    normalized = normalize_auth_username(username)
    if not normalized:
        return False
    lookup_hash = hash_username_lookup(normalized)
    user = User.query.filter_by(username_lookup_hash=lookup_hash).first()
    if user:
        if exclude_sysadmin_id is not None:
            excluded_admin = db.session.get(User, exclude_sysadmin_id)
            if excluded_admin and excluded_admin.username_lookup_hash == lookup_hash and getattr(excluded_admin.user_role, "value", excluded_admin.user_role) == UserRole.SYSADMIN.value:
                return False
        return True

    admin = _find_sysadmin_by_auth_username(username)
    if not admin:
        return False
    if exclude_sysadmin_id is not None and admin.id == exclude_sysadmin_id:
        return False
    return True


def _tail_log_lines(file_path: str, max_lines: int = 200, chunk_size: int = 8192):
    """Return the last ``max_lines`` from a log file without loading the entire file."""

    if not os.path.exists(file_path):
        return []

    lines = []
    buffer = b""
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()

        while len(lines) <= max_lines and position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            f.seek(position)
            buffer = f.read(read_size) + buffer
            lines = buffer.splitlines()

    return [line.decode(errors="ignore") for line in lines[-max_lines:]]



# -------------------- AUTHENTICATION --------------------

@sysadmin_bp.route('/auth-check', methods=['GET'])
@limiter.exempt
def auth_check():
    """Internal auth probe for Nginx `auth_request`.

    Returns:
      - 204 if the current session is an authenticated system admin
      - 401 otherwise

    Note: Do NOT decorate with `@system_admin_required` because that may redirect
    to the login page; `auth_request` needs a clean 2xx/401 signal.
    """
    # Validate sysadmin auth via canonical context.
    from app.services.context_resolver import (
        resolve_canonical_context, BoundaryContext,
        ContextNotEstablished, ContextMismatch, ContextForbidden,
    )
    try:
        ctx = resolve_canonical_context(require_class=False)
    except (ContextNotEstablished, ContextMismatch, ContextForbidden):
        raise Unauthorized("System admin authentication required")
    if not isinstance(ctx, BoundaryContext) or ctx.actor_role != 'sysadmin':
        raise Unauthorized("System admin authentication required")

    # Enforce session timeout for security, consistent with other decorators.
    last_activity_str = session.get("last_activity")
    if last_activity_str:
        last_activity = datetime.fromisoformat(last_activity_str)
        last_activity = ensure_utc(last_activity)
        if _system_admin_timeout_expired(last_activity):
            _expire_system_admin_session()
            raise Unauthorized("Session expired")

    # Update activity to keep session alive.
    session["last_activity"] = utc_now().isoformat()
    return ("", 204)

@sysadmin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
@feat_shell("FEAT-OPS-001")
def login():
    """System admin login with TOTP authentication."""
    session.pop("user_id", None)
    session.pop("current_session_nonce", None)
    session.pop("last_activity", None)
    session.pop("force_sysadmin_username_migration", None)  # noqa: safety — no-op if key absent
    form = SystemAdminLoginForm()
    if form.validate_on_submit():
        username = normalize_auth_username(form.username.data)
        totp_code = form.totp_code.data.strip()
        user = find_canonical_user_by_auth_username(username, expected_role="sysadmin")
        if user:
            try:
                decrypted_secret = decrypt_totp(user.totp_secret_encrypted)
            except (TypeError, ValueError):
                current_app.logger.warning(
                    "System admin login failed: invalid encrypted TOTP secret for user_id=%s",
                    user.id,
                )
                decrypted_secret = None
            if decrypted_secret:
                totp_valid = False
                try:
                    totp = pyotp.TOTP(decrypted_secret)
                    totp_valid = totp.verify(totp_code, valid_window=1)
                except (binascii.Error, TypeError, ValueError):
                    current_app.logger.warning(
                        "System admin login failed: TOTP secret is not valid base32 for sysadmin_id=%s",
                        user.id,
                    )
                    totp_valid = False
                if totp_valid:
                    # Canonical session — no extinct keys
                    establish_sysadmin_session(user)
                    nonce = secrets.token_urlsafe(32)
                    session["current_session_nonce"] = nonce
                    user.current_session_nonce = nonce
                    session["sysadmin_auth_username"] = username
                    session['last_activity'] = utc_now().isoformat()
                    # Establish global maintenance bypass for subsequent role testing.
                    session['maintenance_global_bypass'] = True
                    flash("System admin login successful.")
                    next_url = request.args.get("next")
                    redirect_target = None
                    if next_url:
                        # Normalize backslashes and only allow relative in-app redirects.
                        normalized_next = next_url.replace('\\', '')
                        parsed_next = urlparse(normalized_next)
                        if (not parsed_next.scheme and not parsed_next.netloc and is_safe_url(normalized_next)):
                            redirect_target = normalized_next
                        else:
                            redirect_target = url_for("sysadmin.dashboard")
                    else:
                        redirect_target = url_for("sysadmin.dashboard")
                    return redirect(redirect_target)
        flash("Invalid credentials or TOTP.", "error")
        return redirect(url_for("sysadmin.login"))
    return render_template("system_admin_login.html", form=form)


@sysadmin_bp.route('/logout')
def logout():
    """System admin logout."""
    session.pop("user_id", None)
    session.pop("current_session_nonce", None)
    session.pop("last_activity", None)
    session.pop("sysadmin_auth_username", None)
    session.pop("passkey_sysadmin_auth_username", None)
    session.pop("force_sysadmin_username_migration", None)  # noqa: safety — no-op if key absent
    # Intentionally DO NOT remove maintenance_global_bypass so admin can test other roles.
    flash("Logged out.")
    return redirect(url_for("sysadmin.login"))


# -------------------- PASSKEY AUTHENTICATION (Official SDK Implementation) --------------------

@sysadmin_bp.route('/passkey/register/start', methods=['POST'])
@system_admin_required
@limiter.limit("10 per minute")
def passkey_register_start():
    """
    Start passkey registration - Generate registration token.

    Official SDK Pattern: Create RegisterToken and get token from passwordless.dev
    """
    try:
        ctx = g.canonical_context
        user = get_current_user()
        if not user or ctx.actor_role != 'sysadmin':
            abort(404)

        # Generate registration token using official SDK
        user_id = f"user_{user.id}"
        username = session.get("sysadmin_auth_username") or user.auth_username or f"sysadmin_{user.id}"
        displayname = f"System administrator: {username}"

        token = create_register_token(user_id, username, displayname)

        return jsonify({
            "token": token,
            "apiKey": get_public_api_key()
        }), 200

    except ValueError as e:
        current_app.logger.error(f"Passwordless.dev configuration error: {e}")
        return jsonify({"error": "Passkey service not configured"}), 503
    except Exception as e:
        current_app.logger.error(f"Error starting passkey registration: {e}")
        return jsonify({"error": "Failed to start registration"}), 500


@sysadmin_bp.route('/passkey/register/finish', methods=['POST'])
@system_admin_required
@limiter.limit("10 per minute")
def passkey_register_finish():
    """
    Finish passkey registration - Save credential metadata.

    After frontend completes WebAuthn ceremony, store credential metadata.
    """
    try:
        ctx = g.canonical_context
        user = get_current_user()
        if not user or ctx.actor_role != 'sysadmin':
            return jsonify({"error": "Canonical system admin identity is missing"}), 409
        sysadmin = User.query.filter_by(
            username_lookup_hash=user.username_lookup_hash,
            user_role=UserRole.SYSADMIN,
        ).first()
        if not sysadmin:
            return jsonify({"error": "System admin record not found"}), 404
        data = request.get_json()

        # No token is required in the payload for registration finish; nothing to check here.

        # Note: Credential is stored on passwordless.dev servers
        # We just track that registration occurred for UX purposes
        authenticator_name = data.get('authenticatorName', 'Unnamed Passkey')

        create_admin_credential(user.id, authenticator_name, credential_id=None)

        flash("Passkey registered successfully!", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error finishing passkey registration: {e}")
        return jsonify({"error": "Failed to register passkey"}), 500


@sysadmin_bp.route('/passkey/auth/start', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_start():
    """
    Start passkey authentication - Return public API key.

    Official SDK Pattern: Frontend needs public API key to initiate signin
    """
    try:
        data = request.get_json()
        session.pop("passkey_sysadmin_auth_username", None)

        if not data or 'username' not in data:
            return jsonify({"error": "Missing username"}), 400

        username = normalize_auth_username(data['username'])

        user = find_canonical_user_by_auth_username(username, expected_role="sysadmin")
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        # Check if user has passkeys
        has_passkeys = admin_has_passkeys(user.id)
        if not has_passkeys:
            return jsonify({"error": "Invalid credentials"}), 401

        session["passkey_sysadmin_auth_username"] = username

        return jsonify({
            "apiKey": get_public_api_key()
        }), 200

    except ValueError as e:
        current_app.logger.error(f"Passwordless.dev configuration error: {e}")
        return jsonify({"error": "Passkey service not configured"}), 503
    except Exception as e:
        current_app.logger.error(f"Error starting passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 500


@sysadmin_bp.route('/passkey/auth/finish', methods=['POST'])
@feat_shell("FEAT-OPS-001")
@limiter.limit("20 per minute")
def passkey_auth_finish():
    """
    Finish passkey authentication - Verify token and create session.

    Official SDK Pattern: Verify signin token and create authenticated session
    """
    try:
        data = request.get_json()

        if not data or 'token' not in data:
            return jsonify({"error": "Missing token"}), 400

        # Verify token using official SDK
        verified_user = verify_signin_token(data['token'])

        # Extract canonical user ID from Passwordless user_id (format: "user_{id}").
        external_user_id = verified_user.user_id
        if not external_user_id or not external_user_id.startswith('user_'):
            return jsonify({"error": "Invalid user ID"}), 401

        try:
            canonical_user_id = int(external_user_id.replace('user_', ''))
        except ValueError:
            current_app.logger.error(f"Invalid userId format: {external_user_id}")
            return jsonify({"error": "Invalid user ID format"}), 401

        user = db.session.get(User, canonical_user_id)
        if not user or getattr(user.user_role, "value", user.user_role) != "sysadmin":
            return jsonify({"error": "Invalid user ID"}), 401
        now = utc_now()
        touch_admin_credentials_last_used(user.id, now)

        # Create session — canonical keys only
        establish_sysadmin_session(user)
        nonce = secrets.token_urlsafe(32)
        session["current_session_nonce"] = nonce
        user.current_session_nonce = nonce
        session["sysadmin_auth_username"] = (
            session.get("passkey_sysadmin_auth_username") or f"sysadmin_{user.id}"
        )
        session['last_activity'] = now.isoformat()
        session['maintenance_global_bypass'] = True

        # Determine redirect URL
        next_url = request.args.get("next")
        if not is_safe_url(next_url):
            redirect_url = url_for("sysadmin.dashboard")
        else:
            redirect_url = next_url or url_for("sysadmin.dashboard")

        return jsonify({
            "success": True,
            "redirect": redirect_url
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error finishing passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 401


@sysadmin_bp.route('/passkey/list', methods=['GET'])
@system_admin_required
def passkey_list():
    """List all passkeys for current system admin."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "Canonical system admin identity is missing"}), 409
        credentials = list_admin_credentials(user.id)

        return jsonify([{
            "id": cred.id,
            "name": cred.authenticator_name or "Unnamed Passkey",
            "created_at": cred.created_at.isoformat() if cred.created_at else None,
            "last_used": cred.last_used.isoformat() if cred.last_used else None
        } for cred in credentials]), 200

    except Exception as e:
        current_app.logger.error(f"Error listing passkeys: {e}")
        return jsonify({"error": "Failed to list passkeys"}), 500


@sysadmin_bp.route('/passkey/<int:credential_id>/delete', methods=['POST'])
@system_admin_required
@limiter.limit("10 per minute")
def passkey_delete(credential_id):
    """Delete a passkey."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "Canonical system admin identity is missing"}), 409
        deleted = delete_admin_credential(credential_id, user.id)
        if not deleted:
            return jsonify({"error": "Passkey not found"}), 404

        flash("Passkey deleted successfully.", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting passkey: {e}")
        return jsonify({"error": "Failed to delete passkey"}), 500


@sysadmin_bp.route('/passkey/settings')
@system_admin_required
def passkey_settings():
    """Passkey management page."""
    ctx = g.canonical_context
    user = get_current_user()
    if not user or ctx.actor_role != 'sysadmin':
        abort(404)
    credentials = list_admin_credentials(user.id)

    return render_template("system_admin_passkey_settings.html",
                         admin=user,
                         credentials=credentials)


# -------------------- DASHBOARD --------------------

@sysadmin_bp.route('/dashboard', methods=['GET', 'POST'])
@system_admin_required
def dashboard():
    """
    System admin dashboard with unified statistics and quick actions.
    Shows admin count, student count, active invites, recent admins, and recent errors.
    """
    # Gather statistics
    total_admins = User.query.filter_by(user_role=UserRole.TEACHER).count()
    total_students = Seat.query.filter(Seat.role == 'student').count()
    active_invites = count_active_admin_invite_codes()
    system_admin_count = User.query.filter(User.user_role == UserRole.SYSADMIN).count()

    # Open tickets = new user reports + pending/in-review escalated issues
    new_reports_count = Issue.query.filter(
        Issue.status.in_([Issue.STATUS_OPEN, Issue.STATUS_TEACHER_REVIEW]),
    ).count()
    open_issues_count = Issue.query.filter(
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            'elevated',
            'developer_review',
        ])
    ).count()
    open_tickets = new_reports_count + open_issues_count

    # Recent admins (last 5) are the canonical teacher Users.
    recent_admins = (
        User.query.filter_by(user_role=UserRole.TEACHER)
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    # Recent errors (last 5)
    recent_errors = db.session.execute(
        sa.text(
            "SELECT id, created_at, level, message, payload "
            "FROM operational_events "
            "WHERE level IN ('ERROR', 'CRITICAL') "
            "ORDER BY created_at DESC, id DESC LIMIT 5"
        )
    ).mappings().all()

    # System admins
    system_admins = (
        User.query.filter(User.user_role == UserRole.SYSADMIN)
        .order_by(User.id.asc())
        .all()
    )

    return render_template(
        "system_admin_dashboard.html",
        total_admins=total_admins,
        total_students=total_students,
        active_invites=active_invites,
        system_admin_count=system_admin_count,
        open_tickets=open_tickets,
        recent_admins=recent_admins,
        recent_errors=recent_errors,
        system_admins=system_admins
    )


# -------------------- LOGGING AND MONITORING --------------------

@sysadmin_bp.route('/combined-logs')
@system_admin_required
def combined_logs():
    """
    Unified log viewer with two tabs: Error Logs and Network Activity.
    Replaces the separate error-logs and network-activity pages.
    """
    active_tab = request.args.get('tab', 'errors')
    per_page = 50

    # ── Error Logs (Tab 1) ──
    error_type_filter = request.args.get('error_type', '')
    error_page = request.args.get('page', 1, type=int)
    error_rows = db.session.execute(
        sa.text(
            "SELECT id, created_at, level, payload "
            "FROM operational_events "
            "WHERE level IN ('ERROR', 'CRITICAL') "
            "ORDER BY created_at DESC, id DESC"
        )
    ).mappings().all()
    error_logs = error_rows[(error_page - 1) * per_page:error_page * per_page]
    error_pagination = None
    error_types = sorted({row.get('payload', {}).get('error_type') for row in error_rows if row.get('payload') and row.get('payload').get('error_type')})

    # ── Network Activity (Tab 2) ──
    ip_filter = request.args.get('ip', '')
    net_page = request.args.get('net_page', 1, type=int)
    net_rows = error_rows
    network_logs = net_rows[(net_page - 1) * per_page:net_page * per_page]
    net_pagination = None
    ip_addresses = []
    total_requests = len(error_rows)
    total_errors = len(error_rows)
    unique_ips = 0
    error_type_stats = []

    return render_template(
        "sysadmin_combined_logs.html",
        current_page="logs",
        active_tab=active_tab,
        # Error tab
        error_logs=error_logs,
        error_pagination=error_pagination,
        error_types=error_types,
        current_error_type=error_type_filter,
        total_errors=total_errors,
        # Network tab
        network_logs=network_logs,
        net_pagination=net_pagination,
        ip_addresses=ip_addresses,
        current_ip=ip_filter,
        total_requests=total_requests,
        unique_ips=unique_ips,
        error_type_stats=error_type_stats,
    )

@sysadmin_bp.route('/logs')
@system_admin_required
def logs():
    """
    View system logs from the log file.
    Parses and structures the last 200 lines of logs for display.
    """
    log_file = os.getenv("LOG_FILE", "app.log")
    structured_logs = []
    try:
        lines = _tail_log_lines(log_file, max_lines=200)
        log_pattern = re.compile(r'\[(.*?)\]\s+(\w+)\s+in\s+(\w+):\s+(.*)')
        current_log = None
        for line in lines:
            match = log_pattern.match(line)
            if match:
                # Start a new log entry
                timestamp, level, module, message = match.groups()
                current_log = {
                    "timestamp": timestamp,
                    "level": level,
                    "module": module,
                    "message": message.strip()
                }
                structured_logs.append(current_log)
            else:
                # Continuation of the previous log entry (stack trace, etc.)
                if current_log:
                    current_log["message"] += "<br>" + line.strip()
                else:
                    # Orphan line with no preceding log; treat as its own entry
                    current_log = {
                        "timestamp": "",
                        "level": "",
                        "module": "",
                        "message": line.strip()
                    }
                    structured_logs.append(current_log)
    except Exception as e:
        structured_logs = [{"timestamp": "", "level": "ERROR", "module": "logs", "message": f"Error reading log file: {e}"}]
    return render_template("system_admin_logs.html", logs=structured_logs, current_page="sysadmin_logs")


@sysadmin_bp.route('/error-logs')
@system_admin_required
def error_logs():
    """
    View error logs from the database.
    Shows all errors captured by the error logging system with pagination and filtering.
    """
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get error type filter if provided
    error_type_filter = request.args.get('error_type', '')

    error_logs_data = []
    pagination = None
    error_types = []

    return render_template(
        "system_admin_error_logs.html",
        error_logs=error_logs_data,
        pagination=pagination,
        error_types=error_types,
        current_error_type=error_type_filter,
        current_page="sysadmin_error_logs"
    )


@sysadmin_bp.route('/logs-testing')
@system_admin_required
def logs_testing():
    """
    Combined page for viewing error logs and testing error pages.
    Shows recent errors and provides links to test error handlers.
    """
    # Get recent error logs
    recent_errors = []

    # Get system logs URL
    logs_url = url_for("sysadmin.logs")

    return render_template(
        "system_admin_logs_testing.html",
        recent_errors=recent_errors,
        logs_url=logs_url,
        current_page="sysadmin_logs_testing"
    )


@sysadmin_bp.route('/network-activity')
@system_admin_required
def network_activity():
    """
    View network activity log showing all HTTP requests and responses.
    Displays data from error logs, grouped by IP address and request path.
    """
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get IP filter if provided
    ip_filter = request.args.get('ip', '')

    # Query error logs as proxy for network activity
    network_logs = []
    pagination = None
    ip_addresses = []
    total_requests = 0
    unique_ips = 0
    error_type_stats = []

    return render_template(
        "system_admin_network_activity.html",
        network_logs=network_logs,
        pagination=pagination,
        ip_addresses=ip_addresses,
        current_ip=ip_filter,
        total_requests=total_requests,
        unique_ips=unique_ips,
        error_type_stats=error_type_stats,
        current_page="network_activity"
    )


# -------------------- ERROR TESTING ROUTES --------------------

@sysadmin_bp.route('/test-errors/400')
@system_admin_required
def test_error_400():
    """Trigger a 400 Bad Request error for testing."""
    raise BadRequest("This is a test 400 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/401')
@system_admin_required
def test_error_401():
    """Trigger a 401 Unauthorized error for testing."""
    raise Unauthorized("This is a test 401 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/403')
@system_admin_required
def test_error_403():
    """Trigger a 403 Forbidden error for testing."""
    raise Forbidden("This is a test 403 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/404')
@system_admin_required
def test_error_404():
    """Trigger a 404 Not Found error for testing."""
    raise NotFound("This is a test 404 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/500')
@system_admin_required
def test_error_500():
    """Trigger a 500 Internal Server Error for testing."""
    # Intentionally cause a division by zero error
    x = 1 / 0
    return "This should never be reached"


@sysadmin_bp.route('/test-errors/503')
@system_admin_required
def test_error_503():
    """Trigger a 503 Service Unavailable error for testing."""
    raise ServiceUnavailable("This is a test 503 error triggered by system admin for testing purposes.")


# -------------------- ADMIN MANAGEMENT --------------------

@sysadmin_bp.route('/admins')
@system_admin_required
def manage_admins():
    """Teacher account management for canonical teacher Users."""
    teachers = User.query.filter_by(user_role=UserRole.TEACHER).order_by(User.id.asc()).all()
    user_student_counts, _ = _user_student_counts([teacher.id for teacher in teachers])

    admin_data = [
        {
            'id': teacher.id,
            'username': f"user_{teacher.id}",
            'student_count': user_student_counts.get(teacher.id, 0),
            'created_at': teacher.created_at,
            'last_login': None,
        }
        for teacher in teachers
    ]

    return render_template(
        'system_admin_manage_admins.html',
        admins=admin_data,
        current_page='sysadmin_admins'
    )


@sysadmin_bp.route('/admins/<int:user_id>/reset-totp', methods=['POST'])
@system_admin_required
@feat_shell("FEAT-OPS-001")
def reset_admin_totp(user_id):
    """
    Reset TOTP for a teacher account.

    user_id is the canonical User.id (matches what manage_admins() renders).
    Teacher TOTP lives on User.totp_secret_encrypted; login checks that field only.
    """
    user = db.get_or_404(User, user_id)

    try:
        display_name = user.get_display_username()
        new_secret = pyotp.random_base32()
        encrypted_totp_secret = encrypt_totp(new_secret)
        user.totp_secret_encrypted = encrypted_totp_secret
        stored_secret = user.totp_secret_encrypted

        # Generate QR code
        totp_uri = pyotp.totp.TOTP(new_secret).provisioning_uri(
            name=display_name,
            issuer_name="Classroom Economy System Admin"
        )

        img = qrcode.make(totp_uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        qr_b64 = base64.b64encode(buf.read()).decode('utf-8')

        return jsonify({
            "status": "success",
            "message": f"TOTP secret reset for {display_name}",
            "totp_secret": stored_secret,
            "totp_secret_plain": new_secret,
            "qr_code": qr_b64,
            "username": display_name
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting TOTP for user {user_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An internal error occurred while resetting the TOTP secret."
        }), 500


@sysadmin_bp.route('/admins/<int:user_id>/delete', methods=['POST'])
@system_admin_required
@feat_shell("FEAT-OPS-001")
def delete_admin(user_id):
    """Delete a teacher account and all students created under that teacher."""
    admin_user = db.get_or_404(User, user_id)

    try:
        admin_username = admin_user.get_display_username()
        class_ids = [
            class_id for (class_id,) in db.session.query(ClassEconomy.class_id)
            .filter(ClassEconomy.user_id == admin_user.id)
            .all()
        ]
        deleted_class_count = len(class_ids)
        deleted_student_count = db.session.query(Seat.id).filter(
            Seat.class_id.in_(class_ids),
            Seat.role == "student",
        ).count() if class_ids else 0

        from app.utils.deletion import collapse_universe
        for cid in class_ids:
            collapse_universe(cid, reason="Teacher account deletion", actor_membership_id=None)

        delete_recovery_rows_for_user(admin_user.id)
        delete_admin_credentials_for_user(admin_user.id)
        delete_admin_onboarding_for_user(admin_user.id)

        legacy_admin = _resolve_legacy_admin(admin_user)
        delete_admin_account_rows(admin_user, legacy_admin=legacy_admin)

        flash(
            f"Teacher '{admin_username}' deleted. Removed {deleted_student_count} student seats across {deleted_class_count} classes.",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting admin {user_id}")
        flash(f"Error deleting admin: {str(e)}", "error")

    return redirect(url_for('sysadmin.manage_admins'))


@sysadmin_bp.route('/manage-teachers', methods=['GET', 'POST'])
@system_admin_required
def manage_teachers():
    """
    Manage invite codes.
    """
    # Handle invite code form submission
    form = SystemAdminInviteForm()
    if form.validate_on_submit():
        code = (form.code.data.strip() if form.code.data else None) or secrets.token_urlsafe(8)
        current_app.logger.info(f"Creating invite code: {repr(code)} (length: {len(code)})")
        expiry_days = request.form.get('expiry_days', 30, type=int)
        expires_at = utc_now() + timedelta(days=expiry_days)
        invite = create_admin_invite_code(code=code, expires_at=expires_at)
        current_app.logger.info(f"Invite code created in database: {repr(invite.code)} (id: {invite.id})")
        flash(f"Invite code '{code}' created successfully.", "success")
        return redirect(url_for("sysadmin.manage_teachers") + "#invite-codes")

    # Get all invite codes and organize them.
    all_invites = list_admin_invite_codes()
    
    # Organize invites: active, expired, or used.
    active_invites = []
    expired_invites = []
    used_invites = []
    
    current_time = utc_now()
    
    for invite in all_invites:
        if invite.used:
            used_invites.append(invite)
        elif invite.expires_at and invite.expires_at < current_time:
            expired_invites.append(invite)
        else:
            active_invites.append(invite)

    # Build rich admin data (from overview logic)
    all_admins = User.query.filter(User.user_role == UserRole.TEACHER).order_by(User.id.asc()).all()
    inactivity_threshold = utc_now() - timedelta(days=INACTIVITY_THRESHOLD_DAYS)

    user_ids_by_admin_id = {
        admin.id: admin.id
        for admin in all_admins
    }
    user_student_counts, user_periods = _user_student_counts(list(user_ids_by_admin_id.values()))
    admin_pending_requests = {}

    admins = []
    for admin in all_admins:
        user_id = user_ids_by_admin_id.get(admin.id)
        total_students = user_student_counts.get(user_id, 0) if user_id else 0
        periods = user_periods.get(user_id, {}) if user_id else {}
        pending_requests = admin_pending_requests.get(admin.id, [])

        is_inactive = False
        if admin.last_login:
            last_login = admin.last_login
            last_login = ensure_utc(last_login)
            is_inactive = last_login < inactivity_threshold
        else:
            is_inactive = True

        admins.append({
            'id': admin.id,
            'username': admin.get_display_username(),
            'last_login': admin.last_login,
            'is_inactive': is_inactive,
            'total_students': total_students,
            'periods': periods,
            'pending_requests': pending_requests,
            'can_delete_account': False,
        })

    return render_template(
        "system_admin_manage_teachers.html",
        form=form,
        active_invites=active_invites,
        expired_invites=expired_invites,
        used_invites=used_invites,
        teachers=admins,
        inactivity_threshold_days=INACTIVITY_THRESHOLD_DAYS,
    )


@sysadmin_bp.route('/manage-teachers/void/<int:code_id>', methods=['POST'])
@system_admin_required
def void_invite_code(code_id):
    """Void (mark as used) an unused invite code so it can no longer be claimed."""
    invite = get_admin_invite_code_by_id(code_id)
    if not invite:
        raise NotFound("Invite code not found")
    if invite.used:
        flash("This invite code has already been used or voided.", "warning")
    else:
        mark_admin_invite_code_used(code_id)
        flash(f"Invite code '{invite.code}' has been voided.", "success")
    return redirect(url_for("sysadmin.manage_teachers") + "#invite-codes")


@sysadmin_bp.route('/teacher-overview', methods=['GET'])
@system_admin_required
def teacher_overview():
    """
    Privacy-compliant admin overview showing only aggregated student counts.

    System admins can view:
    - Teacher public ID/display name
    - Total student count per admin
    - Student counts by period/block
    - Last login date
    - Teacher public IDs/display names and aggregate roster state only

    System admins CANNOT view:
    - Individual student names
    - Individual student details
    """
    admins = User.query.filter(User.user_role == UserRole.TEACHER).order_by(User.id.asc()).all()
    
    # Define inactivity threshold (6 months)
    inactivity_threshold = utc_now() - timedelta(days=INACTIVITY_THRESHOLD_DAYS)

    user_ids_by_admin_id = {
        admin.id: admin.id
        for admin in admins
    }
    user_student_counts, user_periods = _user_student_counts(list(user_ids_by_admin_id.values()))

    admin_pending_requests = {}

    # Now build the admin_data list using the batched data
    admin_data = []
    for admin in admins:
        # Get data from batched queries
        user_id = user_ids_by_admin_id.get(admin.id)
        total_students = user_student_counts.get(user_id, 0) if user_id else 0
        periods = user_periods.get(user_id, {}) if user_id else {}
        pending_requests = admin_pending_requests.get(admin.id, [])

        # Check if admin is inactive
        is_inactive = False
        if admin.last_login:
            # Ensure last_login is timezone-aware
            last_login = admin.last_login
            last_login = ensure_utc(last_login)
            is_inactive = last_login < inactivity_threshold
        else:
            # Never logged in - consider inactive
            is_inactive = True

        admin_data.append({
            'id': admin.id,
            'username': admin.get_display_username(),
            'total_students': total_students,
            'periods': periods,
            'last_login': admin.last_login,
            'is_inactive': is_inactive,
            'pending_requests': pending_requests,
            'can_delete_account': False,
        })

    return render_template(
        "system_admin_teacher_overview.html",
        teachers=admin_data,
        current_page="teacher_overview",
        inactivity_threshold_days=INACTIVITY_THRESHOLD_DAYS
    )


@sysadmin_bp.route('/delete-period/<int:user_id>/<string:period>', methods=['POST'])
@system_admin_required
def delete_period(user_id, period):
    flash("Teacher account deletions are self-managed. System admins cannot delete classes.", "error")
    return redirect(url_for('sysadmin.manage_teachers'))


@sysadmin_bp.route('/manage-teachers/delete/<int:user_id>', methods=['POST'])
@system_admin_required
def delete_teacher(user_id):
    flash("Teacher account deletions are self-managed. System admins cannot delete admin accounts.", "error")
    return redirect(url_for('sysadmin.manage_teachers'))


# -------------------- SUPPORT TICKETS (COMBINED VIEW) --------------------

def _resolve_issue_id_from_ref(issue_ref: str) -> int | None:
    return resolve_opaque_ref('issue', issue_ref)


def _resolve_report_id_from_ref(report_ref: str) -> int | None:
    return resolve_opaque_ref('report', report_ref)

@sysadmin_bp.route('/support')
@system_admin_required
def support_tickets():
    """
    Unified support ticket dashboard combining admin issues and escalated student issues.
    Tab 1: Teacher issues (teacher-submitted support tickets)
    Tab 2: Escalated Issues (student-escalated issues awaiting developer review)
    """
    active_tab = request.args.get('tab', 'reports')

    # ── Teacher Issues (Tab 1) ──
    status_filter = request.args.get('status', 'all')
    report_type_filter = request.args.get('type', 'all')
    report_query = Issue.query.filter(Issue.issue_type == 'general')
    if status_filter != 'all':
        report_query = report_query.filter(Issue.status == status_filter.upper())
    reports = [
        SimpleNamespace(
            id=issue.id,
            status=issue.status,
            report_type=issue.category_id,
            submitted_at=issue.submitted_at,
            title=issue.student_expected_outcome or "Support issue",
            description=issue.student_explanation,
            anonymous_code=issue.actor_public_id,
            class_id=issue.class_public_id,
        )
        for issue in report_query.order_by(Issue.submitted_at.desc()).all()
    ]

    from sqlalchemy import func as sqlfunc
    status_counts = dict(
        db.session.query(Issue.status, sqlfunc.count(Issue.id))
        .filter(Issue.issue_type == 'general')
        .group_by(Issue.status).all()
    )
    new_reports = status_counts.get('new', 0)
    reviewed_reports = status_counts.get('reviewed', 0)

    # ── Escalated Issues (Tab 2) ──
    all_issues = Issue.query.filter(
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            Issue.STATUS_DEV_RESOLVED,
            'elevated',
            'developer_review',
            'developer_resolved',
        ])
    ).order_by(Issue.escalated_at.desc()).all()
    issues_pending = [
        i for i in all_issues
        if i.status in [Issue.STATUS_ESCALATED_TO_DEV, 'elevated']
    ]
    issues_in_review = [i for i in all_issues if i.status == 'developer_review']
    issues_resolved = [i for i in all_issues if i.status in [Issue.STATUS_DEV_RESOLVED, 'developer_resolved']]

    return render_template(
        'sysadmin_support_tickets.html',
        current_page='support_tickets',
        active_tab=active_tab,
        # Teacher issues
        reports=reports,
        status_filter=status_filter,
        report_type_filter=report_type_filter,
        new_reports=new_reports,
        reviewed_reports=reviewed_reports,
        issue_ref_for=lambda issue_id: make_opaque_ref('issue', issue_id),
        report_ref_for=lambda report_id: make_opaque_ref('report', report_id),
        # Escalated issues
        issues_pending=issues_pending,
        issues_in_review=issues_in_review,
        issues_resolved=issues_resolved,
        pending_issues=len(issues_pending),
        in_review_issues=len(issues_in_review),
    )


# -------------------- USER REPORTS --------------------

@sysadmin_bp.route('/user-reports')
@system_admin_required
def user_reports():
    """View admin-submitted support issues with filtering."""
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    report_type_filter = request.args.get('type', 'all')
    
    # Build query
    query = Issue.query.filter(Issue.issue_type == 'general')
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter(Issue.status == status_filter.upper())
    if report_type_filter != 'all':
        query = query.filter(Issue.category_id == int(report_type_filter) if report_type_filter.isdigit() else True)

    reports = [
        SimpleNamespace(
            id=issue.id,
            status=issue.status,
            report_type=issue.category_id,
            submitted_at=issue.submitted_at,
            title=issue.student_expected_outcome or "Support issue",
            description=issue.student_explanation,
            anonymous_code=issue.actor_public_id,
            class_id=issue.class_public_id,
        )
        for issue in query.order_by(Issue.submitted_at.desc()).all()
    ]
    from sqlalchemy import func
    status_counts = dict(
        db.session.query(Issue.status, func.count(Issue.id))
        .filter(Issue.issue_type == 'general')
        .group_by(Issue.status)
        .all()
    )
    new_count = status_counts.get('new', 0)
    reviewed_count = status_counts.get('reviewed', 0)
    closed_count = status_counts.get('closed', 0)
    
    return render_template(
        'sysadmin_user_reports.html',
        current_page='user_reports',
        page_title='Teacher Issues',
        reports=reports,
        new_count=new_count,
        reviewed_count=reviewed_count,
        closed_count=closed_count,
        status_filter=status_filter,
        report_type_filter=report_type_filter,
        report_ref_for=lambda report_id: make_opaque_ref('report', report_id),
    )


@sysadmin_bp.route('/user-reports/<report_ref>')
@system_admin_required
def view_user_report(report_ref):
    """View details of a specific admin issue report."""
    report_id = _resolve_report_id_from_ref(report_ref)
    if report_id is None:
        raise NotFound("Report not found")
    report = db.session.get(Issue, report_id)
    if not report:
        raise NotFound("Report not found")
    
    return render_template(
        'sysadmin_user_report_detail.html',
        current_page='user_reports',
        page_title=f'Report #{report_id}',
        report=report,
        report_ref=make_opaque_ref('report', report.id),
    )


@sysadmin_bp.route('/user-reports/<report_ref>/update', methods=['POST'])
@system_admin_required
def update_user_report(report_ref):
    """Update the status and notes of a user report."""
    report_id = _resolve_report_id_from_ref(report_ref)
    if report_id is None:
        raise NotFound("Report not found")
    report = db.session.get(Issue, report_id)
    if not report:
        raise NotFound("Report not found")
    
    # Get form data
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '').strip()
    
    # Validate status
    valid_statuses = ['new', 'reviewed', 'closed', 'spam']
    if new_status not in valid_statuses:
        flash("Invalid status selected.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_ref=make_opaque_ref('report', report.id)))
    
    # Update report
    report.status = new_status
    report.admin_notes = admin_notes if admin_notes else None
    report.reviewed_at = utc_now()
    report.reviewed_by_sysadmin_id = g.canonical_context.user_id
    
    try:
        flash(f"Report #{report_id} updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating report {report_id}: {str(e)}")
        flash("Error updating report. Please try again.", "error")
    
    return redirect(url_for('sysadmin.view_user_report', report_ref=make_opaque_ref('report', report.id)))


@sysadmin_bp.route('/grafana/auth-check', methods=['GET'])
@limiter.exempt
def grafana_auth_check():
    """
    Auth check endpoint for nginx auth_request.

    Returns 200 with X-Auth-User header if authenticated, 401 if not.
    Exempt from rate limiting to prevent blocking Grafana's multiple auth checks per page.
    """
    from flask import Response
    from app.services.context_resolver import (
        resolve_canonical_context, BoundaryContext,
        ContextNotEstablished, ContextMismatch, ContextForbidden,
    )
    try:
        ctx = resolve_canonical_context(require_class=False)
    except (ContextNotEstablished, ContextMismatch, ContextForbidden):
        return Response('Unauthorized', 401)
    if not isinstance(ctx, BoundaryContext) or ctx.actor_role != 'sysadmin':
        return Response('Unauthorized', 401)

    # Check session timeout
    last_activity_str = session.get("last_activity")
    if last_activity_str:
        last_activity = datetime.fromisoformat(last_activity_str)
        last_activity = ensure_utc(last_activity)
        if _system_admin_timeout_expired(last_activity):
            _expire_system_admin_session()
            return Response('Unauthorized: Session expired', 401)

    # Update activity to keep session alive
    session["last_activity"] = utc_now().isoformat()

    # Sanitize username for header (prevent response splitting)
    raw_username = session.get("sysadmin_auth_username") or f"sysadmin_{ctx.user_id}"
    username = raw_username.replace('\n', '').replace('\r', '') if raw_username else ''

    response = Response('OK', 200)
    response.headers['X-Auth-User'] = username
    return response


@sysadmin_bp.route('/grafana', methods=['GET'], defaults={'path': ''})
@sysadmin_bp.route('/grafana/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@system_admin_required
@limiter.exempt
def grafana_proxy(path):
    """
    Proxy requests to Grafana dashboard.

    This route forwards all requests to the Grafana service running on localhost:3000
    (or configured GRAFANA_URL) while maintaining system admin authentication.

    The route is exempt from rate limiting to allow smooth dashboard operation.
    """
    # Validate the requested Grafana path to prevent proxying to arbitrary URLs
    # Disallow absolute or protocol-relative URLs and restrict to known Grafana prefixes.
    normalized_path = path or ''
    # Normalize path to a safe form to avoid header/response splitting issues.
    normalized_path = normalized_path.replace('\r', '').replace('\n', '')
    if normalized_path.startswith(('http://', 'https://', '//')):
        current_app.logger.warning(f"Rejected unsafe Grafana proxy path: {normalized_path}")
        raise BadRequest("Invalid Grafana path.")

    allowed_prefixes = (
        '',                 # root
        'd/',               # dashboard URLs
        'dashboard/',
        'dashboards/',      # dashboards listing
        'api/',             # Grafana API
        'public/',          # public assets
        'avatar/',          # user avatars
        'static/',          # static content
        'login',            # login page
        'logout',           # logout
    )
    if normalized_path and not normalized_path.startswith(allowed_prefixes):
        current_app.logger.warning(f"Rejected disallowed Grafana proxy path: {normalized_path}")
        raise BadRequest("Invalid Grafana path.")

    # Get Grafana URL from environment or use default
    grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')

    # Build the target URL
    target_url = f"{grafana_url}/{normalized_path}"
    if request.query_string:
        target_url = f"{target_url}?{request.query_string.decode('utf-8')}"

    try:
        # Forward the request to Grafana
        headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'connection']}

        # Add the authenticated user header for Grafana
        # Fetch admin to get username (Grafana auth proxy expects username, not ID)
        ctx = g.canonical_context
        if not ctx or ctx.actor_role != 'sysadmin':
            flash("Authentication failed: user not found.", "error")
            return redirect(url_for('sysadmin.dashboard'))
        headers['X-WEBAUTH-USER'] = session.get("sysadmin_auth_username") or f"sysadmin_{ctx.user_id}"

        # Make the request to Grafana
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=30,
            stream=True
        )

        # Before streaming, check content type to avoid reflecting potentially unsafe content
        # that could contain XSS payloads. Use case-insensitive comparison since MIME types
        # are case-insensitive per RFC 2045.
        content_type = resp.headers.get('Content-Type', '').lower().strip()

        # Split on semicolon to handle parameters like "application/json; charset=utf-8"
        mime_type = content_type.split(';')[0].strip() if content_type else ''

        # Explicitly block SVG first - SVG can contain embedded JavaScript and poses XSS risks
        if mime_type == 'image/svg+xml':
            current_app.logger.warning(
                f"Blocked proxied Grafana response with dangerous content type: {content_type} "
                f"for path: {normalized_path}"
            )
            return Response(
                "Unable to display this Grafana content via proxy due to security restrictions. "
                "Please access the Grafana dashboard directly.",
                status=502,
                mimetype='text/plain'
            )

        # Allowlist of safe MIME type prefixes that are permitted to be streamed.
        # Everything else (including HTML/XML or missing/unknown types) is blocked.
        # Note: image/svg+xml is explicitly blocked above before this check.
        javascript_mime_types = (
            'application/javascript',
            'text/javascript',
        )
        safe_mime_prefixes = (
            'image/',              # images (png, jpeg, gif, etc.) - SVG blocked above
            'text/plain',          # plain text
            'text/css',            # stylesheets
            'application/json',    # JSON APIs
            *javascript_mime_types,
            'application/octet-stream',
            'application/pdf',
            'text/csv',
        )

        # Block if Content-Type is missing or not in the allowlist of safe prefixes
        if not mime_type or not any(mime_type.startswith(prefix) for prefix in safe_mime_prefixes):
            current_app.logger.warning(
                f"Blocked proxied Grafana response with potentially unsafe content type: {content_type or 'none'} "
                f"for path: {normalized_path}"
            )
            # Avoid returning upstream content directly to prevent reflected XSS
            return Response(
                "Unable to display this Grafana content via proxy due to security restrictions. "
                "Please access the Grafana dashboard directly.",
                status=502,
                mimetype='text/plain'
            )

        # Restrict executable JavaScript responses to static asset paths only.
        # This preserves Grafana front-end assets while reducing script-reflection risk.
        if (
            mime_type in javascript_mime_types
            and not normalized_path.startswith(('public/', 'static/'))
        ):
            current_app.logger.warning(
                f"Blocked proxied Grafana JavaScript response for non-static path: {normalized_path}"
            )
            return Response(
                "Unable to display this Grafana content via proxy due to security restrictions. "
                "Please access the Grafana dashboard directly.",
                status=502,
                mimetype='text/plain'
            )

        # Create streaming response for allowed content types
        # Security: Use allowlist for headers instead of blocklist to prevent XSS via reflected headers
        # Only pass through specific, known-safe headers that are necessary for proper content delivery
        allowed_headers = {
            'content-type',          # Required for browser to interpret content correctly
            'content-disposition',   # For file downloads
            'cache-control',         # Caching behavior
            'expires',               # Cache expiration
            'last-modified',         # Conditional requests
            'etag',                  # Conditional requests
            'content-security-policy',  # Security policy (if Grafana sets it)
        }

        response_headers = [
            (name, value) for name, value in resp.raw.headers.items()
            if name.lower() in allowed_headers
        ]

        # Restrict which content types are rendered inline to reduce XSS risk from proxied content.
        content_type = resp.headers.get('Content-Type', '')
        safe_inline_types = (
            'image/',
            'text/css',
            'text/plain',
            'application/json',
            'application/javascript',
            'text/javascript',
        )
        is_safe_inline = any(
            content_type.startswith(prefix) if prefix.endswith('/') else content_type.split(';', 1)[0].strip() == prefix
            for prefix in safe_inline_types
        )

        if not is_safe_inline:
            # Force potentially unsafe content (e.g., HTML) to be downloaded instead of rendered.
            # This keeps functionality (content still accessible) while preventing script execution in-page.
            # Override Content-Type and add a safe Content-Disposition header.
            response_headers = [
                (name, value)
                for name, value in response_headers
                if name.lower() not in ('content-type', 'content-disposition')
            ]
            response_headers.append(('Content-Type', 'application/octet-stream'))
            response_headers.append(('Content-Disposition', 'attachment; filename="grafana-content"'))

        response = Response(resp.iter_content(chunk_size=8192), resp.status_code, response_headers)
        # Prevent MIME sniffing to reduce the chance of script execution from mislabeled payloads.
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    except requests.exceptions.ConnectionError:
        current_app.logger.error(f"Failed to connect to Grafana at {grafana_url}")
        flash("Grafana service is not available. Please contact the system administrator.", "error")
        return redirect(url_for('sysadmin.dashboard'))
    except requests.exceptions.Timeout:
        current_app.logger.error(f"Timeout connecting to Grafana at {grafana_url}")
        flash("Grafana service timed out. Please try again later.", "error")
        return redirect(url_for('sysadmin.dashboard'))
    except Exception as e:
        current_app.logger.error(f"Error proxying request to Grafana: {str(e)}")
        flash("An error occurred while accessing Grafana.", "error")
        return redirect(url_for('sysadmin.dashboard'))


# -------------------- SYSTEM ADMIN ANNOUNCEMENTS --------------------

@sysadmin_bp.route('/announcements')
@system_admin_required
def announcements():
    """
    System admin announcement management.

    View and manage system-wide announcements.
    System admins cannot see teacher-created class announcements.
    """
    from app.models import Announcement

    # Get only system admin announcements (not teacher announcements)
    announcements_list = Announcement.query.filter(
        Announcement.system_admin_id != None
    ).order_by(Announcement.created_at.desc()).all()

    # Get list of teachers for display
    admins_dict = {admin.id: admin for admin in User.query.filter(User.user_role == UserRole.TEACHER).all()}

    # Attach audience info to each announcement
    for announcement in announcements_list:
        if announcement.audience_type == 'teacher_all_classes' and announcement.target_teacher_id:
            teacher_admin = admins_dict.get(announcement.target_teacher_id)
            announcement.audience_display = f"All classes of {teacher_admin.get_display_username() if teacher_admin else 'Unknown teacher'}"
        else:
            announcement.audience_display = announcement.get_audience_label()

    return render_template(
        'sysadmin_announcements.html',
        announcements=announcements_list
    )


@sysadmin_bp.route('/announcements/create', methods=['GET', 'POST'])
@system_admin_required
@feat_shell("FEAT-OPS-001")
def announcement_create():
    """Create a new system-wide announcement."""
    from app.forms import SystemAdminAnnouncementForm
    from app.models import Announcement

    sysadmin_user_id = g.canonical_context.user_id

    form = SystemAdminAnnouncementForm()

    # Populate teacher choices
    teacher_admins = User.query.filter(User.user_role == UserRole.TEACHER).order_by(User.id.asc()).all()
    form.target_teacher.choices = [('', '-- Select Teacher --')] + [
        (teacher_admin.id, teacher_admin.get_display_username())
        for teacher_admin in teacher_admins
    ]

    if form.validate_on_submit():
        try:
            # Validate target admin requirement
            if form.audience_type.data == 'teacher_all_classes':
                if not form.target_teacher.data:
                    flash('Please select a target teacher for "All Classes of Specific Teacher" audience.', 'danger')
                    return render_template('sysadmin_announcement_form.html', form=form, action='Create')

            announcement = create_system_announcement(
                system_admin_id=sysadmin_user_id,
                audience_type=form.audience_type.data,
                target_teacher_id=form.target_teacher.data if form.audience_type.data == 'teacher_all_classes' else None,
                title=form.title.data,
                message=form.message.data,
                priority=form.priority.data,
                is_active=form.is_active.data,
                expires_at=form.expires_at.data,
            )

            flash(f'System announcement "{announcement.title}" created successfully!', 'success')
            return redirect(url_for('sysadmin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating system announcement: {e}")
            flash('An error occurred while creating the announcement.', 'danger')

    return render_template('sysadmin_announcement_form.html', form=form, action='Create')


@sysadmin_bp.route('/announcements/edit/<int:announcement_id>', methods=['GET', 'POST'])
@system_admin_required
def announcement_edit(announcement_id):
    """Edit an existing system announcement."""
    from app.forms import SystemAdminAnnouncementForm
    from app.models import Announcement

    # sysadmin_user_id not needed here — announcement ownership verified by is_system_admin_announcement()

    # Get announcement and verify it's a system admin announcement
    announcement = Announcement.query.filter_by(id=announcement_id).first()

    if not announcement or not announcement.is_system_admin_announcement():
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('sysadmin.announcements'))

    form = SystemAdminAnnouncementForm(obj=announcement)

    # Populate teacher choices
    teacher_admins = User.query.filter(User.user_role == UserRole.TEACHER).order_by(User.id.asc()).all()
    form.target_teacher.choices = [('', '-- Select Teacher --')] + [
        (teacher_admin.id, teacher_admin.get_display_username())
        for teacher_admin in teacher_admins
    ]

    if form.validate_on_submit():
        try:
            # Validate target admin requirement
            if form.audience_type.data == 'teacher_all_classes':
                if not form.target_teacher.data:
                    flash('Please select a target teacher for "All Classes of Specific Teacher" audience.', 'danger')
                    return render_template('sysadmin_announcement_form.html', form=form, announcement=announcement, action='Edit')

            update_system_announcement(
                announcement,
                audience_type=form.audience_type.data,
                target_teacher_id=form.target_teacher.data if form.audience_type.data == 'teacher_all_classes' else None,
                title=form.title.data,
                message=form.message.data,
                priority=form.priority.data,
                is_active=form.is_active.data,
                expires_at=form.expires_at.data,
            )

            flash(f'System announcement "{announcement.title}" updated successfully!', 'success')
            return redirect(url_for('sysadmin.announcements'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating system announcement: {e}")
            flash('An error occurred while updating the announcement.', 'danger')

    return render_template('sysadmin_announcement_form.html', form=form, announcement=announcement, action='Edit')


@sysadmin_bp.route('/announcements/delete/<int:announcement_id>', methods=['POST'])
@system_admin_required
def announcement_delete(announcement_id):
    """Delete a system announcement."""
    from app.models import Announcement

    # Get announcement and verify it's a system admin announcement
    announcement = Announcement.query.filter_by(id=announcement_id).first()

    if not announcement or not announcement.is_system_admin_announcement():
        flash('Announcement not found or access denied.', 'danger')
        return redirect(url_for('sysadmin.announcements'))

    try:
        title = announcement.title
        delete_system_announcement(announcement)

        flash(f'System announcement "{title}" deleted successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting system announcement: {e}")
        flash('An error occurred while deleting the announcement.', 'danger')

    return redirect(url_for('sysadmin.announcements'))


@sysadmin_bp.route('/announcements/toggle/<int:announcement_id>', methods=['POST'])
@system_admin_required
def announcement_toggle(announcement_id):
    """Toggle system announcement active status."""
    from app.models import Announcement

    # Get announcement and verify it's a system admin announcement
    announcement = Announcement.query.filter_by(id=announcement_id).first()

    if not announcement or not announcement.is_system_admin_announcement():
        return jsonify({'status': 'error', 'message': 'Announcement not found'}), 404

    try:
        announcement.is_active = not announcement.is_active
        announcement.updated_at = utc_now()

        return jsonify({
            'status': 'success',
            'is_active': announcement.is_active,
            'message': f'Announcement {"activated" if announcement.is_active else "deactivated"}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling system announcement: {e}")
        return jsonify({'status': 'error', 'message': 'An internal error occurred while updating the announcement.'}), 500


# ================== ESCALATED ISSUES ==================

@sysadmin_bp.route('/issues')
@system_admin_required
def escalated_issues():
    """
    System admin view of all escalated issues from teacher users.
    Shows issues that have been escalated for developer/sysadmin review.
    """
    # Get all escalated issues.
    issues = Issue.query.filter(
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            Issue.STATUS_DEV_RESOLVED,
            'elevated',
            'developer_review',
            'developer_resolved',
        ])
    ).order_by(Issue.escalated_at.desc()).all()

    # Separate by status
    pending_issues = [i for i in issues if i.status in [Issue.STATUS_ESCALATED_TO_DEV, 'elevated']]
    in_review_issues = [i for i in issues if i.status == 'developer_review']
    resolved_issues = [i for i in issues if i.status in [Issue.STATUS_DEV_RESOLVED, 'developer_resolved']]

    return render_template('sysadmin_escalated_issues.html',
                         current_page='issues',
                         page_title='Escalated Issues',
                         pending_issues=pending_issues,
                         in_review_issues=in_review_issues,
                         resolved_issues=resolved_issues,
                         issue_ref_for=lambda issue_id: make_opaque_ref('issue', issue_id),
                         format_utc_iso=format_utc_iso)


@sysadmin_bp.route('/issues/<issue_ref>')
@system_admin_required
def view_escalated_issue(issue_ref):
    """View detailed information about a specific escalated issue."""
    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        raise NotFound("Issue not found")
    # Get the issue and verify it's escalated
    issue = Issue.query.filter(
        Issue.id == issue_id,
        Issue.status.in_([
            Issue.STATUS_ESCALATED_TO_DEV,
            Issue.STATUS_DEV_RESOLVED,
            'elevated',
            'developer_review',
            'developer_resolved',
        ])
    ).first_or_404()

    # Get status history
    history = IssueStatusHistory.query.filter_by(
        issue_id=issue.id
    ).order_by(IssueStatusHistory.changed_at.desc()).all()

    return render_template('sysadmin_view_escalated_issue.html',
                         current_page='issues',
        page_title=f'Issue #{issue.id}',
        issue=issue,
        issue_ref=make_opaque_ref('issue', issue.id),
        report_ref_for=lambda report_id: make_opaque_ref('report', report_id),
        correlation_pack=issue.correlation_pack,
        history=history,
        format_utc_iso=format_utc_iso)


@sysadmin_bp.route('/issues/<issue_ref>/start-review', methods=['POST'])
@system_admin_required
def start_review_escalated_issue(issue_ref):
    """Start review for an escalated issue record."""
    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        raise NotFound("Issue not found")
    issue = Issue.query.filter(
        Issue.id == issue_id,
        Issue.status.in_([Issue.STATUS_ESCALATED_TO_DEV, 'elevated', 'developer_review'])
    ).first_or_404()

    flash("Status remains Escalated to Developer until technical resolution is recorded.", "info")
    return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))


@sysadmin_bp.route('/issues/<issue_ref>/resolve', methods=['POST'])
@feat_shell("FEAT-OPS-001")
@system_admin_required
def resolve_escalated_issue(issue_ref):
    """Mark technical fix complete, optionally issue bug bounty, then return to teacher-admin final review."""
    issue_id = _resolve_issue_id_from_ref(issue_ref)
    if issue_id is None:
        raise NotFound("Issue not found")
    issue = Issue.query.filter(
        Issue.id == issue_id,
        Issue.status.in_([Issue.STATUS_ESCALATED_TO_DEV, 'elevated', 'developer_review'])
    ).first_or_404()

    resolution_note = request.form.get('resolution_note', '').strip()
    eligible_for_reward = request.form.get('eligible_for_reward') == 'on'
    reward_amount_raw = request.form.get('reward_amount', '').strip()
    sysadmin_user_id = g.canonical_context.user_id

    if not sysadmin_user_id:
        flash("System admin session is invalid. Please log in again.", "error")
        return redirect(url_for('sysadmin.login', next=request.path))

    if not resolution_note:
        flash("Resolution notes are required.", "error")
        return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))

    try:
        reward_amount_value = None
        if eligible_for_reward:
            if not reward_amount_raw:
                flash("Reward amount is required when bug bounty is selected.", "error")
                return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))
            try:
                from app.models import _quantize_currency
                reward_amount_value = _quantize_currency(reward_amount_raw)
            except (ValueError, TypeError, InvalidOperation):
                flash("Invalid reward amount.", "error")
                return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))
            if reward_amount_value <= Decimal('0'):
                flash("Reward amount must be greater than 0.", "error")
                return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))

        old_status = issue.status
        issue.status = Issue.STATUS_DEV_RESOLVED
        issue.sysadmin_resolved_at = utc_now()
        issue.sysadmin_notes = resolution_note
        issue.sysadmin_id = sysadmin_user_id
        issue.eligible_for_reward = eligible_for_reward

        if reward_amount_value is not None:
            # Resolve internal identity from external-facing public IDs.
            reward_seat = Seat.query.filter_by(public_id=issue.actor_public_id).first()
            if not reward_seat:
                flash("Cannot issue reward: actor seat not found.", "error")
                return redirect(url_for('system_admin.view_issue', issue_id=issue.id))
            reward_class = ClassEconomy.query.filter_by(class_public_id=issue.class_public_id).first()
            reward_transaction = ledger_service.create_pending_transaction(
                seat_id=reward_seat.id,
                class_id=reward_class.class_id if reward_class else None,
                target_seat_id=reward_seat.id,
                actor_seat_id=reward_seat.id,
                mechanism="system",
                user_id=reward_seat.user_id,
                amount=reward_amount_value,
                account_type='checking',
                description=f"Bug Reward (Issue #{issue.id})",
                type='bug_reward',
            )

            record_resolution_action(
                issue,
                action_type='bug_reward_issued',
                performed_by_type='sysadmin',
                performed_by_public_id=None,
                action_description=f"Issued bug reward while resolving issue #{issue.id}",
                related_transaction_id=reward_transaction.id,
                amount_changed=float(reward_amount_value),
                before_value='0.00',
                after_value=str(reward_amount_value),
            )

        # Record status change
        from app.utils.issue_helpers import record_status_change
        reward_note = (
            f" | Bug reward: ${reward_amount_value:.2f}"
            if reward_amount_value is not None
            else ""
        )
        record_status_change(
            issue,
            old_status,
            Issue.STATUS_DEV_RESOLVED,
            'sysadmin',
            None,  # sysadmin acts outside class scope; identified by issue.sysadmin_id
            notes=f"{resolution_note}{reward_note}",
        )
        if reward_amount_value is not None:
            flash(
                f"Technical fix recorded, bug reward of ${reward_amount_value:.2f} issued, and ticket returned to teacher review.",
                "success",
            )
        else:
            flash("Technical fix recorded. Ticket returned to the teacher for final review.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolving escalated issue {issue_id}: {e}")
        flash("An error occurred while resolving the issue.", "error")

    return redirect(url_for('sysadmin.view_escalated_issue', issue_ref=make_opaque_ref('issue', issue.id)))
