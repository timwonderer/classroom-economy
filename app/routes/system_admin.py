"""
System Admin routes for Classroom Token Hub.

High-level system administration including teacher management, invite codes,
system logs, error monitoring, and debug/testing tools.
"""

import os
import re
import secrets
import io
import base64
import qrcode
import requests
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app, jsonify, Response
from sqlalchemy import delete, or_, case
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden, NotFound, ServiceUnavailable
import pyotp

from app.extensions import db, limiter
from app.models import (
    SystemAdmin, SystemAdminCredential, Admin, Student, AdminInviteCode, ErrorLog,
    Transaction, TapEvent, HallPassLog, StudentItem, RentPayment,
    StudentInsurance, InsuranceClaim, StudentTeacher, DeletionRequest,
    DeletionRequestType, DeletionRequestStatus, TeacherBlock, StudentBlock, UserReport,
    FeatureSettings, TeacherOnboarding, RentSettings, BankingSettings,
    DemoStudent, HallPassSettings, PayrollFine, PayrollReward,
    PayrollSettings, StoreItem
)
from app.auth import system_admin_required, SESSION_TIMEOUT_MINUTES
from forms import SystemAdminLoginForm, SystemAdminInviteForm

# Import utility functions
from app.utils.helpers import is_safe_url
from app.utils.passwordless_client import get_passwordless_client, decode_credential_id
from app.utils.encryption import encrypt_totp, decrypt_totp

# Create blueprint
sysadmin_bp = Blueprint('sysadmin', __name__, url_prefix='/sysadmin')

# Constants
INACTIVITY_THRESHOLD_DAYS = 180  # Number of days of inactivity before allowing deletion without request


def _get_teacher_student_count(teacher_id: int) -> int:
    """
    Get the count of students associated with a specific teacher.
    
    Counts students that are either:
    1. Linked via student_teachers table (many-to-many relationship), OR
    2. Have teacher_id set (legacy primary ownership during migration)
    
    Uses UNION to avoid double-counting students that appear in both.
    Optimized to count in database without loading student IDs.
    """
    # Get student IDs from student_teachers links
    linked_ids = db.session.query(StudentTeacher.student_id).filter(
        StudentTeacher.admin_id == teacher_id
    ).distinct()
    
    # Get student IDs from legacy teacher_id column
    legacy_ids = db.session.query(Student.id).filter(
        Student.teacher_id == teacher_id
    ).distinct()
    
    # Union the two queries and count - database does the work
    count = linked_ids.union(legacy_ids).count()
    
    return count


def _check_deletion_authorization(admin, request_type=None, period=None):
    """
    Check if system admin is authorized to delete for this teacher.
    
    Authorization is granted if:
    1. Teacher has a pending deletion request matching the criteria, OR
    2. Teacher has been inactive for INACTIVITY_THRESHOLD_DAYS or more
    
    Args:
        admin: The Admin object to check authorization for
        request_type: Optional request type filter ('period' or 'account')
        period: Optional period filter (for period-specific requests)
    
    Returns:
        tuple: (authorized: bool, pending_request: DeletionRequest or None)
    """
    # Check for pending request
    query = DeletionRequest.query.filter_by(
        admin_id=admin.id,
        status=DeletionRequestStatus.PENDING
    )
    if request_type:
        # Convert string to enum if needed
        if isinstance(request_type, str):
            request_type = DeletionRequestType.from_string(request_type)
        query = query.filter_by(request_type=request_type)
    if period:
        query = query.filter_by(period=period)
    pending_request = query.first()
    
    # Check inactivity
    inactivity_threshold = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_THRESHOLD_DAYS)
    is_inactive = False
    if admin.last_login:
        last_login = admin.last_login
        if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=timezone.utc)
        is_inactive = last_login < inactivity_threshold
    else:
        is_inactive = True
    
    authorized = (pending_request is not None) or is_inactive
    return authorized, pending_request


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
    if not session.get("is_system_admin") or session.get("sysadmin_id") is None:
        raise Unauthorized("System admin authentication required")

    # Enforce session timeout for security, consistent with other decorators.
    last_activity_str = session.get("last_activity")
    if last_activity_str:
        last_activity = datetime.fromisoformat(last_activity_str)
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            session.pop("is_system_admin", None)
            session.pop("sysadmin_id", None)
            session.pop("last_activity", None)
            raise Unauthorized("Session expired")

    # Update activity to keep session alive.
    session["last_activity"] = datetime.now(timezone.utc).isoformat()
    return ("", 204)

@sysadmin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """System admin login with TOTP authentication."""
    session.pop("is_system_admin", None)
    session.pop("sysadmin_id", None)
    session.pop("last_activity", None)
    form = SystemAdminLoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        totp_code = form.totp_code.data.strip()
        admin = SystemAdmin.query.filter_by(username=username).first()
        if admin:
            # Decrypt TOTP secret (handles both encrypted and legacy plaintext)
            decrypted_secret = decrypt_totp(admin.totp_secret)
            totp = pyotp.TOTP(decrypted_secret)
            if totp.verify(totp_code, valid_window=1):
                session["is_system_admin"] = True
                session["sysadmin_id"] = admin.id
                session['last_activity'] = datetime.now(timezone.utc).isoformat()
                # Establish global maintenance bypass for subsequent role testing.
                session['maintenance_global_bypass'] = True
                flash("System admin login successful.")
                next_url = request.args.get("next")
                if not is_safe_url(next_url):
                    return redirect(url_for("sysadmin.dashboard"))
                return redirect(next_url or url_for("sysadmin.dashboard"))
        flash("Invalid credentials or TOTP.", "error")
        return redirect(url_for("sysadmin.login"))
    return render_template("system_admin_login.html", form=form)


@sysadmin_bp.route('/logout')
def logout():
    """System admin logout."""
    session.pop("is_system_admin", None)
    session.pop("sysadmin_id", None)
    session.pop("last_activity", None)
    # Intentionally DO NOT remove maintenance_global_bypass so admin can test other roles.
    flash("Logged out.")
    return redirect(url_for("sysadmin.login"))


# -------------------- PASSKEY AUTHENTICATION --------------------

@sysadmin_bp.route('/passkey/register/start', methods=['POST'])
@system_admin_required
@limiter.limit("10 per minute")
def passkey_register_start():
    """
    Start passkey registration for the currently logged-in system admin.

    This endpoint generates a registration token from passwordless.dev
    that the frontend will use to initiate the WebAuthn credential creation ceremony.

    Returns:
        JSON response with registration token and public key
    """
    try:
        sysadmin_id = session.get("sysadmin_id")
        if not sysadmin_id:
            return jsonify({"error": "Not authenticated"}), 401

        admin = SystemAdmin.query.get_or_404(sysadmin_id)

        # Get passwordless.dev client
        client = get_passwordless_client()

        # Generate registration token
        # Use "sysadmin_{id}" as userId for passwordless.dev
        user_id = f"sysadmin_{admin.id}"
        token = client.register_token(
            user_id=user_id,
            username=admin.username,
            displayname=f"System Admin: {admin.username}"
        )

        return jsonify({
            "token": token,
            "apiKey": client.get_public_key()
        }), 200

    except ValueError as e:
        # API keys not configured
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
    Finish passkey registration and store the credential.

    After the frontend completes the WebAuthn ceremony, this endpoint
    receives the credential details and stores them in the database.

    Expected JSON payload:
        {
            "credentialId": "base64url-encoded credential ID",
            "authenticatorName": "User-friendly name (optional)"
        }

    Returns:
        JSON response indicating success or failure
    """
    try:
        sysadmin_id = session.get("sysadmin_id")
        if not sysadmin_id:
            return jsonify({"error": "Not authenticated"}), 401

        data = request.get_json()
        if not data or 'credentialId' not in data:
            return jsonify({"error": "Missing credential ID"}), 400

        credential_id_b64 = data['credentialId']
        authenticator_name = data.get('authenticatorName', 'Unnamed Passkey')

        # Decode credential ID from base64url
        credential_id = decode_credential_id(credential_id_b64)

        # Check if this credential already exists
        existing = SystemAdminCredential.query.filter_by(credential_id=credential_id).first()
        if existing:
            return jsonify({"error": "This credential is already registered"}), 409

        # Create new credential record
        # Note: With passwordless.dev, we don't store the public key locally
        # The public key is stored in their service. For self-hosted migration,
        # we would store it here.
        credential = SystemAdminCredential(
            sysadmin_id=sysadmin_id,
            credential_id=credential_id,
            public_key=b'',  # Empty for passwordless.dev; populated for self-hosted
            sign_count=0,
            authenticator_name=authenticator_name
            # created_at is set automatically by the model default
        )

        db.session.add(credential)
        db.session.commit()

        flash("Passkey registered successfully!", "success")
        return jsonify({"success": True, "message": "Passkey registered"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error finishing passkey registration: {e}")
        return jsonify({"error": "Failed to register passkey"}), 500


@sysadmin_bp.route('/passkey/auth/start', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_start():
    """
    Start passkey authentication.

    This endpoint returns the public API key needed for the frontend
    to initiate the WebAuthn authentication ceremony.

    Expected JSON payload:
        {
            "username": "sysadmin_username"
        }

    Returns:
        JSON response with public API key
    """
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"error": "Missing username"}), 400

        username = data['username'].strip()

        # Verify user exists
        admin = SystemAdmin.query.filter_by(username=username).first()
        if not admin:
            # Don't reveal if user exists
            return jsonify({"error": "Invalid credentials"}), 401

        # Check if user has any passkeys registered
        has_passkeys = SystemAdminCredential.query.filter_by(sysadmin_id=admin.id).first() is not None
        if not has_passkeys:
            return jsonify({"error": "No passkeys registered for this account"}), 401

        # Get passwordless.dev client
        client = get_passwordless_client()

        return jsonify({
            "apiKey": client.get_public_key(),
            "userId": f"sysadmin_{admin.id}"
        }), 200

    except ValueError as e:
        current_app.logger.error(f"Passwordless.dev configuration error: {e}")
        return jsonify({"error": "Passkey service not configured"}), 503

    except Exception as e:
        current_app.logger.error(f"Error starting passkey authentication: {e}")
        return jsonify({"error": "Authentication failed"}), 500


@sysadmin_bp.route('/passkey/auth/finish', methods=['POST'])
@limiter.limit("20 per minute")
def passkey_auth_finish():
    """
    Finish passkey authentication and create session.

    After the frontend completes the WebAuthn ceremony, this endpoint
    verifies the authentication token with passwordless.dev and creates
    a session for the system admin.

    Expected JSON payload:
        {
            "token": "token from passwordless.dev frontend"
        }

    Returns:
        JSON response with redirect URL or error
    """
    try:
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({"error": "Missing token"}), 400

        token = data['token']

        # Verify token with passwordless.dev
        client = get_passwordless_client()
        verification = client.verify_signin(token)

        if not verification.get('success'):
            return jsonify({"error": "Authentication failed"}), 401

        # Extract user ID (format: "sysadmin_{id}")
        user_id = verification.get('userId')
        if not user_id or not user_id.startswith('sysadmin_'):
            return jsonify({"error": "Invalid user ID"}), 401

        # Parse sysadmin ID with error handling for malformed IDs
        try:
            sysadmin_id = int(user_id.replace('sysadmin_', ''))
        except ValueError:
            current_app.logger.error(f"Invalid userId format from passwordless.dev: {user_id}")
            return jsonify({"error": "Invalid user ID format"}), 401

        # Verify system admin exists
        admin = SystemAdmin.query.get(sysadmin_id)
        if not admin:
            return jsonify({"error": "Admin not found"}), 401

        # Update credential last_used timestamp
        credential_id_b64 = verification.get('credentialId')
        if credential_id_b64:
            credential_id = decode_credential_id(credential_id_b64)
            credential = SystemAdminCredential.query.filter_by(
                credential_id=credential_id
            ).first()
            if credential:
                credential.last_used = datetime.now(timezone.utc)
                db.session.commit()

        # Create session (same as TOTP login)
        session["is_system_admin"] = True
        session["sysadmin_id"] = admin.id
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
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
    """
    List all passkeys registered for the current system admin.

    Returns:
        JSON array of passkey credentials
    """
    try:
        sysadmin_id = session.get("sysadmin_id")
        if not sysadmin_id:
            return jsonify({"error": "Not authenticated"}), 401

        credentials = SystemAdminCredential.query.filter_by(
            sysadmin_id=sysadmin_id
        ).order_by(SystemAdminCredential.created_at.desc()).all()

        return jsonify([{
            "id": cred.id,
            "name": cred.authenticator_name,
            "created_at": cred.created_at.isoformat(),
            "last_used": cred.last_used.isoformat() if cred.last_used else None,
            "transports": cred.transports
        } for cred in credentials]), 200

    except Exception as e:
        current_app.logger.error(f"Error listing passkeys: {e}")
        return jsonify({"error": "Failed to list passkeys"}), 500


@sysadmin_bp.route('/passkey/<int:credential_id>/delete', methods=['POST'])
@system_admin_required
@limiter.limit("10 per minute")
def passkey_delete(credential_id):
    """
    Delete a passkey credential.

    Args:
        credential_id: The database ID of the credential to delete

    Returns:
        JSON response indicating success or failure
    """
    try:
        sysadmin_id = session.get("sysadmin_id")
        if not sysadmin_id:
            return jsonify({"error": "Not authenticated"}), 401

        # Find the credential
        credential = SystemAdminCredential.query.filter_by(
            id=credential_id,
            sysadmin_id=sysadmin_id
        ).first_or_404()

        # Check if this is the last passkey
        total_passkeys = SystemAdminCredential.query.filter_by(
            sysadmin_id=sysadmin_id
        ).count()

        # Always allow deletion during migration period (TOTP is still available)
        # In the future, after TOTP removal, we may want to require at least 1 passkey

        # Delete from database
        db.session.delete(credential)
        db.session.commit()

        flash("Passkey deleted successfully.", "success")
        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting passkey: {e}")
        return jsonify({"error": "Failed to delete passkey"}), 500


@sysadmin_bp.route('/passkey/settings', methods=['GET'])
@system_admin_required
def passkey_settings():
    """
    Passkey management page for system admin.

    Displays registered passkeys and allows registration of new passkeys.
    """
    sysadmin_id = session.get("sysadmin_id")
    if not sysadmin_id:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("sysadmin.login"))

    # Get current admin info
    admin = SystemAdmin.query.get_or_404(sysadmin_id)

    # Get all passkeys for this admin
    credentials = SystemAdminCredential.query.filter_by(
        sysadmin_id=sysadmin_id
    ).order_by(SystemAdminCredential.created_at.desc()).all()

    return render_template(
        "system_admin_passkey_settings.html",
        admin=admin,
        credentials=credentials
    )


# -------------------- DASHBOARD --------------------

@sysadmin_bp.route('/dashboard', methods=['GET', 'POST'])
@system_admin_required
def dashboard():
    """
    System admin dashboard with unified statistics and quick actions.
    Shows teacher count, student count, active invites, recent teachers, and recent errors.
    """
    # Gather statistics
    total_teachers = Admin.query.count()
    total_students = Student.query.count()
    active_invites = AdminInviteCode.query.filter_by(used=False).count()
    system_admin_count = SystemAdmin.query.count()

    # Recent teachers (last 5)
    recent_teachers = Admin.query.order_by(Admin.created_at.desc()).limit(5).all()

    # Recent errors (last 5)
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(5).all()

    # System admins
    system_admins = SystemAdmin.query.order_by(SystemAdmin.username.asc()).all()

    return render_template(
        "system_admin_dashboard.html",
        total_teachers=total_teachers,
        total_students=total_students,
        active_invites=active_invites,
        system_admin_count=system_admin_count,
        recent_teachers=recent_teachers,
        recent_errors=recent_errors,
        system_admins=system_admins
    )


# -------------------- LOGGING AND MONITORING --------------------

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

    query = ErrorLog.query

    if error_type_filter:
        query = query.filter(ErrorLog.error_type == error_type_filter)

    # Paginate and order by most recent first
    pagination = query.order_by(ErrorLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    error_logs_data = pagination.items

    # Get distinct error types for filter dropdown
    error_types = db.session.query(ErrorLog.error_type).distinct().all()
    error_types = [et[0] for et in error_types if et[0]]

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
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(50).all()

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
    query = ErrorLog.query

    if ip_filter:
        query = query.filter(ErrorLog.ip_address == ip_filter)

    # Paginate and order by most recent first
    pagination = query.order_by(ErrorLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    network_logs = pagination.items

    # Get distinct IP addresses for filter dropdown
    ip_addresses = db.session.query(ErrorLog.ip_address).distinct().all()
    ip_addresses = [ip[0] for ip in ip_addresses if ip[0]]

    # Get statistics
    total_requests = ErrorLog.query.count()
    unique_ips = db.session.query(ErrorLog.ip_address).distinct().count()

    # Group by error type for stats
    error_type_stats = db.session.query(
        ErrorLog.error_type,
        db.func.count(ErrorLog.id).label('count')
    ).group_by(ErrorLog.error_type).all()

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


# -------------------- ADMIN (TEACHER) MANAGEMENT --------------------

@sysadmin_bp.route('/admins')
@system_admin_required
def manage_admins():
    """
    View and manage all admin (teacher) accounts.
    Shows admin details, student counts per teacher, signup date, and last login.
    
    Note: System admins see teacher info and student counts only, not individual student details.
    """
    # Get all admins with student counts
    admins = Admin.query.all()
    admin_data = []

    for admin in admins:
        # Count students associated with this specific teacher
        # Uses both student_teachers links and legacy teacher_id for accuracy
        student_count = _get_teacher_student_count(admin.id)

        admin_data.append({
            'id': admin.id,
            'username': admin.username,
            'student_count': student_count,
            'created_at': admin.created_at,
            'last_login': admin.last_login
        })

    return render_template(
        'system_admin_manage_admins.html',
        admins=admin_data,
        current_page='sysadmin_admins'
    )


@sysadmin_bp.route('/admins/<int:admin_id>/reset-totp', methods=['POST'])
@system_admin_required
def reset_teacher_totp(admin_id):
    """
    Reset a teacher's TOTP secret and return the new setup details (JSON).
    This allows recovery of lost accounts.
    """
    admin = Admin.query.get_or_404(admin_id)

    try:
        # Generate new secret
        new_secret = pyotp.random_base32()
        admin.totp_secret = encrypt_totp(new_secret)  # Encrypt before storing
        db.session.commit()

        # Generate QR code
        totp_uri = pyotp.totp.TOTP(new_secret).provisioning_uri(
            name=admin.username,
            issuer_name="Classroom Economy Admin"
        )

        img = qrcode.make(totp_uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        qr_b64 = base64.b64encode(buf.read()).decode('utf-8')

        return jsonify({
            "status": "success",
            "message": f"TOTP secret reset for {admin.username}",
            "totp_secret": new_secret,
            "qr_code": qr_b64,
            "username": admin.username
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resetting TOTP for admin {admin_id}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@sysadmin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@system_admin_required
def delete_admin(admin_id):
    """
    Delete an admin account and all students created under that teacher.
    This is a permanent action that cascades to all student data.
    """
    admin = Admin.query.get_or_404(admin_id)

    try:
        # SECURITY FIX: Only use StudentTeacher table, NOT deprecated teacher_id
        # Get all students linked to this teacher via StudentTeacher table
        linked_student_ids = [
            st.student_id for st in StudentTeacher.query.filter_by(admin_id=admin.id)
        ]

        candidate_student_ids = set(linked_student_ids)

        # Find students that are shared with other teachers
        shared_student_ids = set()
        if candidate_student_ids:
            shared_student_ids = set(
                sid for (sid,) in db.session.query(StudentTeacher.student_id)
                .filter(
                    StudentTeacher.student_id.in_(candidate_student_ids),
                    StudentTeacher.admin_id != admin.id,
                )
            )

        exclusive_student_ids = candidate_student_ids - shared_student_ids

        if shared_student_ids:
            StudentTeacher.query.filter(
                StudentTeacher.admin_id == admin.id,
                StudentTeacher.student_id.in_(shared_student_ids),
            ).delete(synchronize_session=False)
            Student.query.filter(
                Student.id.in_(shared_student_ids),
                Student.teacher_id == admin.id,
            ).update({Student.teacher_id: None}, synchronize_session=False)

        if exclusive_student_ids:
            Transaction.query.filter(Transaction.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            TapEvent.query.filter(TapEvent.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            HallPassLog.query.filter(HallPassLog.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            StudentItem.query.filter(StudentItem.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            RentPayment.query.filter(RentPayment.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            db.session.execute(delete(StudentInsurance).where(StudentInsurance.student_id.in_(exclusive_student_ids)))
            InsuranceClaim.query.filter(InsuranceClaim.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            StudentTeacher.query.filter(StudentTeacher.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            StudentBlock.query.filter(StudentBlock.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            TeacherBlock.query.filter(TeacherBlock.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            Student.query.filter(Student.id.in_(exclusive_student_ids)).delete(synchronize_session=False)

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        shared_notice = ""
        if shared_student_ids:
            shared_notice = f" Detached {len(shared_student_ids)} shared students without deleting their records."

        flash(
            f"Admin '{admin_username}' deleted. Removed {len(exclusive_student_ids)} exclusively-owned students.{shared_notice}",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting admin {admin_id}")
        flash(f"Error deleting admin: {str(e)}", "error")

    return redirect(url_for('sysadmin.manage_admins'))


@sysadmin_bp.route('/manage-teachers', methods=['GET', 'POST'])
@system_admin_required
def manage_teachers():
    """
    Combined page for teacher management and invite codes.
    Allows creation of invite codes and viewing all teachers.
    """
    # Handle invite code form submission
    form = SystemAdminInviteForm()
    if form.validate_on_submit():
        code = form.code.data or secrets.token_urlsafe(8)
        expiry_days = request.form.get('expiry_days', 30, type=int)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        invite = AdminInviteCode(code=code, expires_at=expires_at)
        db.session.add(invite)
        db.session.commit()
        flash(f"✅ Invite code '{code}' created successfully.", "success")
        return redirect(url_for("sysadmin.manage_teachers") + "#invite-codes")

    # Get all invite codes
    invites = AdminInviteCode.query.order_by(AdminInviteCode.created_at.desc()).all()

    # Get all teachers
    teachers = Admin.query.order_by(Admin.created_at.desc()).all()

    return render_template(
        "system_admin_manage_teachers.html",
        form=form,
        invites=invites,
        teachers=teachers
    )


@sysadmin_bp.route('/teacher-overview', methods=['GET'])
@system_admin_required
def teacher_overview():
    """
    Privacy-compliant teacher overview showing only aggregated student counts.

    System admins can view:
    - Teacher username
    - Total student count per teacher
    - Student counts by period/block
    - Last login date
    - Pending deletion requests

    System admins CANNOT view:
    - Individual student names
    - Individual student details
    """
    teachers = Admin.query.order_by(Admin.username.asc()).all()
    
    # Define inactivity threshold (6 months)
    inactivity_threshold = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_THRESHOLD_DAYS)

    # Batch query: Get all teacher-student relationships in one query
    # Build two queries: one for direct teacher_id, one for StudentTeacher.admin_id
    # Then UNION them to handle both sources correctly without double-counting
    direct_students_q = db.session.query(
        Student.teacher_id.label('teacher_id'),
        Student.id.label('student_id'),
        Student.block.label('block')
    ).filter(
        Student.teacher_id.in_([t.id for t in teachers])
    )

    indirect_students_q = db.session.query(
        StudentTeacher.admin_id.label('teacher_id'),
        Student.id.label('student_id'),
        Student.block.label('block')
    ).join(
        Student, Student.id == StudentTeacher.student_id
    ).filter(
        StudentTeacher.admin_id.in_([t.id for t in teachers])
    )

    teacher_students = direct_students_q.union(indirect_students_q).subquery()

    # Get total student counts per teacher in a single query
    teacher_student_count_rows = db.session.query(
        teacher_students.c.teacher_id,
        db.func.count(teacher_students.c.student_id).label('count')
    ).group_by(teacher_students.c.teacher_id).all()
    teacher_student_counts = {row.teacher_id: row.count for row in teacher_student_count_rows}

    # Get period counts per teacher in a single query
    period_counts_query = db.session.query(
        teacher_students.c.teacher_id,
        teacher_students.c.block,
        db.func.count(teacher_students.c.student_id).label('count')
    ).group_by(
        teacher_students.c.teacher_id,
        teacher_students.c.block
    ).all()

    # Organize period counts by teacher
    teacher_periods = {}
    for teacher_id, block, count in period_counts_query:
        if teacher_id not in teacher_periods:
            teacher_periods[teacher_id] = {}
        teacher_periods[teacher_id][block] = count

    # Batch query: Get all pending deletion requests for all teachers
    all_pending_requests = DeletionRequest.query.filter(
        DeletionRequest.admin_id.in_([t.id for t in teachers]),
        DeletionRequest.status == DeletionRequestStatus.PENDING
    ).all()

    # Organize pending requests by teacher
    teacher_pending_requests = {}
    for req in all_pending_requests:
        if req.admin_id not in teacher_pending_requests:
            teacher_pending_requests[req.admin_id] = []
        teacher_pending_requests[req.admin_id].append(req)

    # Now build the teacher_data list using the batched data
    teacher_data = []
    for teacher in teachers:
        # Get data from batched queries
        total_students = teacher_student_counts.get(teacher.id, 0)
        periods = teacher_periods.get(teacher.id, {})
        pending_requests = teacher_pending_requests.get(teacher.id, [])

        # Check if teacher is inactive
        is_inactive = False
        if teacher.last_login:
            # Ensure last_login is timezone-aware
            last_login = teacher.last_login
            if last_login.tzinfo is None:
                last_login = last_login.replace(tzinfo=timezone.utc)
            is_inactive = last_login < inactivity_threshold
        else:
            # Never logged in - consider inactive
            is_inactive = True

        # Check authorization for account deletion
        has_account_request = any(
            req.request_type == DeletionRequestType.ACCOUNT 
            for req in pending_requests
        )
        can_delete_account = has_account_request or is_inactive
        
        # Check authorization for each period deletion
        # A period can be deleted if there's a specific request for it OR an account deletion request OR teacher is inactive
        authorized_periods = set()
        if can_delete_account:
            # Account deletion request or inactivity authorizes all period deletions
            authorized_periods = set(periods.keys())
        else:
            # Check for period-specific requests
            for req in pending_requests:
                if req.request_type == DeletionRequestType.PERIOD and req.period:
                    authorized_periods.add(req.period)
        
        teacher_data.append({
            'id': teacher.id,
            'username': teacher.username,
            'total_students': total_students,
            'periods': periods,
            'last_login': teacher.last_login,
            'is_inactive': is_inactive,
            'pending_requests': pending_requests,
            'can_delete_account': can_delete_account,
            'authorized_periods': authorized_periods
        })

    return render_template(
        "system_admin_teacher_overview.html",
        teachers=teacher_data,
        current_page="teacher_overview",
        inactivity_threshold_days=INACTIVITY_THRESHOLD_DAYS
    )


@sysadmin_bp.route('/delete-period/<int:admin_id>/<string:period>', methods=['POST'])
@system_admin_required
def delete_period(admin_id, period):
    """
    Delete a specific period/block for a teacher with authorization check.

    Authorization required:
    1. Teacher has a pending deletion request for this period, OR
    2. Teacher has been inactive for 6+ months
    """
    # Validate period parameter
    if not period or len(period) > 10:
        flash("❌ Invalid period parameter", "error")
        return redirect(url_for('sysadmin.teacher_overview'))
    
    # Sanitize period to prevent SQL injection (allow only alphanumeric, spaces, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', period):
        flash("❌ Invalid period format", "error")
        return redirect(url_for('sysadmin.teacher_overview'))
    
    admin = Admin.query.get_or_404(admin_id)

    # Check authorization using helper function
    authorized, pending_request = _check_deletion_authorization(admin, 'period', period)
    
    if not authorized:
        flash(
            f"❌ Unauthorized: Cannot delete period '{period}' for teacher '{admin.username}'. "
            f"Teacher must request deletion or be inactive for 6+ months.",
            "error"
        )
        return redirect(url_for('sysadmin.teacher_overview'))

    try:
        # Get students in this period linked to this teacher
        # Must check BOTH student_teachers join table AND legacy teacher_id column
        students_via_link = db.session.query(Student).join(
            StudentTeacher,
            Student.id == StudentTeacher.student_id
        ).filter(
            StudentTeacher.admin_id == admin.id,
            Student.block == period
        ).all()

        # Also get students linked via legacy teacher_id column
        students_via_legacy = Student.query.filter(
            Student.teacher_id == admin.id,
            Student.block == period
        ).all()

        # Combine both sets (use dict to deduplicate by student ID)
        all_students = {s.id: s for s in students_via_link + students_via_legacy}
        students_in_period = list(all_students.values())

        removed_count = 0
        for student in students_in_period:
            # If this was the primary teacher, reassign to another linked teacher BEFORE deleting
            if student.teacher_id == admin.id:
                fallback = StudentTeacher.query.filter(
                    StudentTeacher.student_id == student.id,
                    StudentTeacher.admin_id != admin.id
                ).order_by(StudentTeacher.created_at.asc()).first()
                student.teacher_id = fallback.admin_id if fallback else None

            # Remove the teacher-student link after reassignment
            # Only remove the StudentTeacher link if the student is not taught by this teacher in any other period
            other_periods = Student.query.filter(
                Student.id == student.id,
                Student.teacher_id == admin.id,
                Student.block != period
            ).count()
            other_links = StudentTeacher.query.filter(
                StudentTeacher.student_id == student.id,
                StudentTeacher.admin_id == admin.id
            ).join(Student, Student.id == StudentTeacher.student_id).filter(
                Student.block != period
            ).count()
            if other_periods == 0 and other_links == 0:
                StudentTeacher.query.filter_by(
                    student_id=student.id,
                    admin_id=admin.id
                ).delete()

            removed_count += 1

        # Delete TeacherBlock entries for this period
        # This is critical - without it, the period still appears in the UI
        TeacherBlock.query.filter_by(
            teacher_id=admin.id,
            block=period
        ).delete()

        # Mark any pending deletion requests for this period as approved
        if pending_request:
            pending_request.status = DeletionRequestStatus.APPROVED
            pending_request.resolved_at = datetime.now(timezone.utc)
            pending_request.resolved_by = session.get('sysadmin_id')

        db.session.commit()

        flash(
            f"✅ Period '{period}' deleted for teacher '{admin.username}'. "
            f"Removed {removed_count} student links. Students maintain access to other classes.",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting period {period} for teacher {admin_id}")
        flash(f"❌ Error deleting period: {str(e)}", "error")

    return redirect(url_for('sysadmin.teacher_overview'))


@sysadmin_bp.route('/manage-teachers/delete/<int:admin_id>', methods=['POST'])
@system_admin_required
def delete_teacher(admin_id):
    """
    Delete a teacher account with authorization check.

    Authorization required:
    1. Teacher has a pending deletion request for their account, OR
    2. Teacher has been inactive for 6+ months

    Students maintain access unless they have no other teachers.
    """
    admin = Admin.query.get_or_404(admin_id)

    # Check authorization using helper function
    authorized, pending_request = _check_deletion_authorization(admin, 'account', None)
    
    if not authorized:
        flash(
            f"❌ Unauthorized: Cannot delete teacher '{admin.username}'. "
            f"Teacher must request deletion or be inactive for 6+ months.",
            "error"
        )
        return redirect(url_for('sysadmin.teacher_overview'))

    try:
        linked_student_ids = (
            db.session.query(StudentTeacher.student_id)
            .filter(StudentTeacher.admin_id == admin.id)
            .subquery()
        )

        affected_students = Student.query.filter(
            or_(Student.teacher_id == admin.id, Student.id.in_(linked_student_ids))
        ).all()
        student_count = len(affected_students)

        for student in affected_students:
            # Remove the teacher-student link
            StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).delete()

            # If this was the primary teacher, reassign to another linked teacher
            if student.teacher_id == admin.id:
                fallback = (
                    StudentTeacher.query
                    .filter(StudentTeacher.student_id == student.id)
                    .order_by(StudentTeacher.created_at.asc())
                    .first()
                )
                student.teacher_id = fallback.admin_id if fallback else None

        # Delete all deletion requests for this teacher to prevent NOT NULL violations.
        # Explicit deletion needed because SQLAlchemy flush might try to nullify the FK
        # before database CASCADE can execute, despite FK having ondelete='CASCADE'.
        DeletionRequest.query.filter_by(admin_id=admin.id).delete()

        # Delete all TeacherBlock entries for this teacher
        # This cleans up roster seats associated with the teacher
        TeacherBlock.query.filter_by(teacher_id=admin.id).delete()

        # Systematically delete all dependent records to prevent IntegrityError due to NOT NULL constraints.
        # Many of these models have a non-nullable teacher_id without a DB-level ON DELETE CASCADE.
        BankingSettings.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        DemoStudent.query.filter_by(admin_id=admin.id).delete(synchronize_session=False)
        FeatureSettings.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        HallPassSettings.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        PayrollFine.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        PayrollReward.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        PayrollSettings.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        RentSettings.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        # Delete StudentItem records for items owned by this teacher
        StudentItem.query.filter(
            StudentItem.store_item_id.in_(
                db.session.query(StoreItem.id).filter_by(teacher_id=admin.id)
            )
        ).delete(synchronize_session=False)
        
        # Delete StudentItem records for items owned by this teacher
        # Must be done before deleting StoreItem to avoid FK constraint violations
        StudentItem.query.filter(
            StudentItem.store_item_id.in_(
                db.session.query(StoreItem.id).filter_by(teacher_id=admin.id)
            )
        ).delete(synchronize_session=False)
        
        StoreItem.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)
        TeacherOnboarding.query.filter_by(teacher_id=admin.id).delete(synchronize_session=False)

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        flash(
            f"✅ Teacher '{admin_username}' deleted. Updated {student_count} student ownership records. "
            f"Students maintain access unless they have no other teachers.",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting teacher {admin_id}")
        flash(f"❌ Error deleting teacher: {str(e)}", "error")

    return redirect(url_for('sysadmin.teacher_overview'))


# -------------------- USER REPORTS --------------------

@sysadmin_bp.route('/user-reports')
@system_admin_required
def user_reports():
    """View all user-submitted bug reports with filtering."""
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    report_type_filter = request.args.get('type', 'all')
    
    # Build query
    query = UserReport.query
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter(UserReport.status == status_filter)
    if report_type_filter != 'all':
        query = query.filter(UserReport.report_type == report_type_filter)
    
    # Get all reports ordered by newest first
    reports = query.order_by(UserReport.submitted_at.desc()).all()
    
    # Count by status - optimized to use single query
    from sqlalchemy import func
    status_counts = dict(db.session.query(UserReport.status, func.count(UserReport.id)).group_by(UserReport.status).all())
    new_count = status_counts.get('new', 0)
    reviewed_count = status_counts.get('reviewed', 0)
    rewarded_count = status_counts.get('rewarded', 0)
    
    return render_template(
        'sysadmin_user_reports.html',
        current_page='user_reports',
        page_title='User Reports',
        reports=reports,
        new_count=new_count,
        reviewed_count=reviewed_count,
        rewarded_count=rewarded_count,
        status_filter=status_filter,
        report_type_filter=report_type_filter
    )


@sysadmin_bp.route('/user-reports/<int:report_id>')
@system_admin_required
def view_user_report(report_id):
    """View details of a specific user report."""
    report = UserReport.query.get_or_404(report_id)
    
    return render_template(
        'sysadmin_user_report_detail.html',
        current_page='user_reports',
        page_title=f'Report #{report_id}',
        report=report
    )


@sysadmin_bp.route('/user-reports/<int:report_id>/update', methods=['POST'])
@system_admin_required
def update_user_report(report_id):
    """Update the status and notes of a user report."""
    report = UserReport.query.get_or_404(report_id)
    
    # Get form data
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes', '').strip()
    
    # Validate status
    valid_statuses = ['new', 'reviewed', 'rewarded', 'closed', 'spam']
    if new_status not in valid_statuses:
        flash("Invalid status selected.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    
    # Update report
    report.status = new_status
    report.admin_notes = admin_notes if admin_notes else None
    report.reviewed_at = datetime.now(timezone.utc)
    report.reviewed_by_sysadmin_id = session.get('sysadmin_id')
    
    try:
        db.session.commit()
        flash(f"Report #{report_id} updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating report {report_id}: {str(e)}")
        flash("Error updating report. Please try again.", "error")
    
    return redirect(url_for('sysadmin.view_user_report', report_id=report_id))


@sysadmin_bp.route('/user-reports/<int:report_id>/send-reward', methods=['POST'])
@system_admin_required
def send_reward_to_reporter(report_id):
    """Send a reward to a student who submitted a bug report."""
    report = UserReport.query.get_or_404(report_id)
    
    # Verify this is a student report with a linked student
    if report.user_type != 'student' or not report._student_id:
        flash("Rewards can only be sent to student reports.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    
    # Check if reward already sent
    if report.reward_sent_at is not None:
        flash("A reward has already been sent for this report.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    
    # Get reward amount
    try:
        reward_amount = float(request.form.get('reward_amount', 0))
        if reward_amount <= 0:
            flash("Reward amount must be greater than 0.", "error")
            return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    except (ValueError, TypeError):
        flash("Invalid reward amount.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    
    # Get the student
    student = Student.query.get(report._student_id)
    if not student:
        flash("Student not found. Cannot send reward.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
    
    # Get student's primary teacher for the transaction
    # Try to get from teacher_id first, otherwise from student_teachers
    teacher_id = student.teacher_id
    if not teacher_id:
        # Get first associated teacher
        first_link = StudentTeacher.query.filter_by(student_id=student.id).first()
        if first_link:
            teacher_id = first_link.admin_id
    
    if not teacher_id:
        flash("Cannot determine student's teacher. Reward not sent.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))

    # Get join_code for this student-teacher pair
    # Query TeacherBlock to find the join_code for multi-tenancy isolation
    teacher_block = TeacherBlock.query.filter_by(
        student_id=student.id,
        teacher_id=teacher_id,
        is_claimed=True
    ).first()

    if not teacher_block or not teacher_block.join_code:
        flash("Cannot determine student's class period. Reward not sent.", "error")
        return redirect(url_for('sysadmin.view_user_report', report_id=report_id))

    join_code = teacher_block.join_code

    try:
        # CRITICAL FIX: Add join_code to bug report reward transaction
        transaction = Transaction(
            student_id=student.id,
            teacher_id=teacher_id,
            join_code=join_code,  # CRITICAL: Add join_code for period isolation
            amount=reward_amount,
            account_type='checking',
            description=f"Bug Report Reward (Report #{report_id})",
            timestamp=datetime.now(timezone.utc),
            is_void=False
        )
        db.session.add(transaction)
        
        # Update report
        report.reward_amount = reward_amount
        report.reward_sent_at = datetime.now(timezone.utc)
        report.status = 'rewarded'
        report.reviewed_at = datetime.now(timezone.utc)
        report.reviewed_by_sysadmin_id = session.get('sysadmin_id')
        
        db.session.commit()
        
        flash(f"Reward of ${reward_amount:.2f} sent successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending reward for report {report_id}: {str(e)}")
        flash("Error sending reward. Please try again.", "error")

    return redirect(url_for('sysadmin.view_user_report', report_id=report_id))


@sysadmin_bp.route('/grafana/auth-check', methods=['GET'])
@limiter.exempt
def grafana_auth_check():
    """
    Auth check endpoint for nginx auth_request.

    Returns 200 with X-Auth-User header if authenticated, 401 if not.
    Exempt from rate limiting to prevent blocking Grafana's multiple auth checks per page.
    """
    from flask import Response
    from datetime import datetime, timedelta, timezone
    from app.auth import SESSION_TIMEOUT_MINUTES
    from app.models import SystemAdmin

    # Check if user is logged in as system admin
    if not session.get("is_system_admin") or not session.get("sysadmin_id"):
        return Response('Unauthorized', 401)

    # Check session timeout
    last_activity_str = session.get("last_activity")
    if last_activity_str:
        last_activity = datetime.fromisoformat(last_activity_str)
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            session.clear()
            return Response('Unauthorized: Session expired', 401)

    # Update activity to keep session alive
    session["last_activity"] = datetime.now(timezone.utc).isoformat()

    # Verify the sysadmin still exists
    sysadmin = SystemAdmin.query.get(session.get('sysadmin_id'))
    if not sysadmin:
        # Admin was deleted but session still exists
        session.clear()
        return Response('Unauthorized', 401)

    # Sanitize username for header (prevent response splitting)
    username = sysadmin.username.replace('\n', '').replace('\r', '') if sysadmin.username else ''

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
    if normalized_path.startswith(('http://', 'https://', '//')):
        current_app.logger.warning(f"Rejected unsafe Grafana proxy path: {normalized_path}")
        raise BadRequest("Invalid Grafana path.")

    allowed_prefixes = (
        '',                 # root
        'd/',               # dashboard URLs
        'dashboard/',       # legacy dashboard URLs
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
        admin = SystemAdmin.query.get(session.get('sysadmin_id'))
        if not admin:
            # Stale session - admin was deleted
            flash("Authentication failed: user not found.", "error")
            return redirect(url_for('sysadmin.dashboard'))
        headers['X-WEBAUTH-USER'] = admin.username

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

        # Create streaming response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                           if name.lower() not in excluded_headers]

        response = Response(resp.iter_content(chunk_size=8192), resp.status_code, response_headers)
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
