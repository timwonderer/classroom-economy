"""
Root application module for Classroom Token Hub.

This module serves as the WSGI entry point and provides backward compatibility
imports. All routes have been modularized into blueprints (Stages 4-5).

For gunicorn: wsgi:app
"""

from flask import render_template, request, session
from datetime import datetime, timedelta
import traceback
import collections
import os

# -------------------- APPLICATION FACTORY --------------------
# Import and create the Flask application using the factory pattern
from app import app
from app.extensions import db, migrate, csrf


def maintenance_mode_enabled():
    """Return True when maintenance mode is enabled via environment variable."""
    return os.getenv("MAINTENANCE_MODE", "").lower() in {"1", "true", "yes", "on"}


def get_validated_status_page_url():
    """
    Return the STATUS_PAGE_URL if it's valid, otherwise None.
    
    Validates that the URL starts with an expected domain to prevent
    potential phishing attacks if an attacker controls the environment variable.
    """
    url = os.getenv('STATUS_PAGE_URL')
    if url and (url.startswith('https://stats.uptimerobot.com/') or 
                url.startswith('https://status.')):
        return url
    return None


# -------------------- BACKWARD COMPATIBILITY IMPORTS --------------------
# Models (Stage 2)
from app.models import (
    Student,
    AdminInviteCode,
    SystemAdmin,
    Transaction,
    TapEvent,
    HallPassLog,
    StoreItem,
    StudentItem,
    RentSettings,
    RentPayment,
    InsurancePolicy,
    StudentInsurance,
    InsuranceClaim,
    ErrorLog,
    Admin,
    PayrollSettings,
    PayrollReward,
    PayrollFine
)

# Auth utilities (Stage 3)
from app.auth import (
    SESSION_TIMEOUT_MINUTES,
    login_required,
    admin_required,
    system_admin_required,
    get_logged_in_student
)

# Utilities (Stage 5)
from app.utils.helpers import format_utc_iso, is_safe_url
from app.utils.encryption import PIIEncryptedType
from app.utils.constants import THEME_PROMPTS


# -------------------- FLASK CLI COMMANDS --------------------
from flask.cli import with_appcontext


def ensure_default_admin():
    """Placeholder: No default admin created for TOTP-only auth."""
    app.logger.info("🛡️ ensure_default_admin: TOTP-only mode, no default admin created.")


@app.cli.command("ensure-admin")
@with_appcontext
def ensure_admin_command():
    """Create the default admin user if credentials are provided."""
    with app.app_context():
        ensure_default_admin()


@app.cli.command("create-sysadmin")
@with_appcontext
def create_sysadmin():
    """Create initial system admin account interactively."""
    import pyotp
    username = input("Enter system admin username: ").strip()
    if not username:
        print("Username is required.")
        return
    existing = SystemAdmin.query.filter_by(username=username).first()
    if existing:
        print(f"System admin '{username}' already exists.")
        return
    totp_secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username=username, totp_secret=totp_secret)
    db.session.add(sysadmin)
    db.session.commit()
    print(f"✅ System admin '{username}' created successfully.")
    print(f"🔑 TOTP secret for authenticator app: {totp_secret}")
    uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy SysAdmin")
    print(f"📱 QR Code URI: {uri}")


# -------------------- APPLICATION HOOKS --------------------
# Automatically create the default admin before the application starts serving
# requests in case migrations ran but the CLI command was not executed
# (e.g. on Azure). Use ``before_serving`` when available (Flask >=2.3),
# otherwise fall back to ``before_first_request`` for older Flask versions.

_admin_checked = False


def _run_admin_check():
    """Ensure the default admin exists but only run once."""
    global _admin_checked
    if not _admin_checked:
        ensure_default_admin()
        _admin_checked = True


if hasattr(app, "before_serving"):
    @app.before_serving
    def create_default_admin_if_needed():
        _run_admin_check()
elif hasattr(app, "before_first_request"):
    @app.before_first_request
    def create_default_admin_if_needed():
        _run_admin_check()
else:
    @app.before_request
    def create_default_admin_if_needed():
        _run_admin_check()


# -------------------- CONTEXT PROCESSORS --------------------

@app.context_processor
def inject_payroll_status():
    """Make payroll settings status available in all templates."""
    if maintenance_mode_enabled():
        return dict(has_payroll_settings=False)

    has_payroll_settings = PayrollSettings.query.first() is not None
    return dict(has_payroll_settings=has_payroll_settings)


# -------------------- ERROR LOGGING UTILITIES --------------------

def get_last_log_lines(num_lines=50):
    """
    Get the last N lines from the log file.
    Returns a string with the last N lines, or an error message if the log file cannot be read.
    """
    log_file_path = os.getenv("LOG_FILE", "app.log")

    # For non-production environments (no log file), return recent logs from memory
    if os.getenv("FLASK_ENV", app.config.get("ENV")) != "production":
        return "[Log file only available in production mode]"

    try:
        if not os.path.exists(log_file_path):
            return f"[Log file not found at {log_file_path}]"

        # Use deque for efficient tail operation
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            last_lines = collections.deque(f, maxlen=num_lines)

        return ''.join(last_lines)
    except Exception as e:
        return f"[Error reading log file: {str(e)}]"


def log_error_to_db(error_type=None, error_message=None, stack_trace=None, log_output=None):
    """
    Save error information to the database for later review.
    This function should not raise exceptions to avoid recursive error loops.
    """
    try:
        # Get request information if available
        request_path = request.path if request else None
        request_method = request.method if request else None
        user_agent = request.headers.get('User-Agent', None) if request else None
        ip_address = request.remote_addr if request else None

        # Get log output
        if log_output is None:
            log_output = get_last_log_lines(50)

        # Create error log entry
        error_log = ErrorLog(
            timestamp=datetime.utcnow(),
            error_type=error_type,
            error_message=error_message,
            request_path=request_path,
            request_method=request_method,
            user_agent=user_agent,
            ip_address=ip_address,
            log_output=log_output,
            stack_trace=stack_trace
        )

        db.session.add(error_log)
        db.session.commit()

        return error_log.id
    except Exception as e:
        # Log to app logger but don't raise - we don't want error logging to cause more errors
        app.logger.error(f"Failed to log error to database: {str(e)}")
        return None


# -------------------- ERROR HANDLERS --------------------

@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 Internal Server Error.
    Logs the error to the database and displays a user-friendly error page.
    """
    # Get error details
    error_type = type(error).__name__
    error_message = str(error)
    stack_trace = traceback.format_exc()

    # Log to app logger
    app.logger.exception("500 Internal Server Error occurred")

    # Save to database
    error_id = log_error_to_db(
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack_trace
    )

    # Rollback any pending database changes
    db.session.rollback()

    # Get log output for display
    log_output = get_last_log_lines(50)

    # Render error page
    return render_template(
        'error_500.html',
        error_id=error_id,
        error_type=error_type,
        error_message=error_message,
        log_output=log_output,
        support_email='timothy.cs.chang@gmail.com',
        status_page_url=get_validated_status_page_url()
    ), 500


@app.errorhandler(404)
def not_found_error(error):
    """
    Handle 404 Not Found Error.
    Displays a user-friendly page with navigation help.
    Rate-limited database logging to prevent spam from bots/typos.
    """
    app.logger.warning(f"404 Not Found: {request.url}")

    # Rate-limited logging: only log unique 404s once per hour
    cache_key = f"404_{request.path}"
    if not hasattr(app, '_404_cache'):
        app._404_cache = {}

    # Clean old entries (older than 1 hour)
    current_time = datetime.utcnow()
    app._404_cache = {k: v for k, v in app._404_cache.items()
                      if (current_time - v).total_seconds() < 3600}

    # Log to database if not recently logged
    if cache_key not in app._404_cache:
        log_error_to_db(
            error_type='404 Not Found',
            error_message=f"Page not found: {request.path}",
            stack_trace=None
        )
        app._404_cache[cache_key] = current_time

    return render_template(
        'error_404.html',
        request_url=request.url
    ), 404


@app.errorhandler(403)
def forbidden_error(error):
    """
    Handle 403 Forbidden Error.
    Displays a user-friendly page with permission troubleshooting.
    Logs to database to track potential security issues.
    """
    app.logger.warning(f"403 Forbidden: {request.url}")

    # Log to database - permission errors could indicate security issues
    log_error_to_db(
        error_type='403 Forbidden',
        error_message=f"Access forbidden: {request.path}",
        stack_trace=None
    )

    return render_template('error_403.html'), 403


@app.errorhandler(401)
def unauthorized_error(error):
    """
    Handle 401 Unauthorized Error.
    Displays a user-friendly page with login guidance.
    Logs to database to track authentication issues.
    """
    app.logger.warning(f"401 Unauthorized: {request.url}")

    # Log to database - authentication errors help identify session/auth issues
    log_error_to_db(
        error_type='401 Unauthorized',
        error_message=f"Authentication required: {request.path}",
        stack_trace=None
    )

    return render_template('error_401.html'), 401


@app.errorhandler(400)
def bad_request_error(error):
    """
    Handle 400 Bad Request Error.
    Displays a user-friendly page with input validation help.
    Logs to database to identify UX/validation issues.
    """
    error_msg = str(error.description) if hasattr(error, 'description') else str(error)
    app.logger.warning(f"400 Bad Request: {request.url} - {error_msg}")

    # Log to database - validation errors help identify UX issues
    log_error_to_db(
        error_type='400 Bad Request',
        error_message=f"Bad request on {request.path}: {error_msg}",
        stack_trace=None
    )

    return render_template(
        'error_400.html',
        error_message=error_msg
    ), 400


@app.errorhandler(503)
def service_unavailable_error(error):
    """
    Handle 503 Service Unavailable Error.
    Displays a user-friendly page for maintenance/downtime.
    Logs to database for service availability tracking.
    """
    app.logger.error(f"503 Service Unavailable: {request.url}")

    # Log to database - service availability is critical to track
    log_error_to_db(
        error_type='503 Service Unavailable',
        error_message=f"Service unavailable: {request.path}",
        stack_trace=None
    )

    return render_template(
        'error_503.html',
        status_page_url=get_validated_status_page_url()
    ), 503


# -------------------- ROUTES --------------------
# All routes have been moved to blueprints in app/routes/ (Stage 4)
# - app/routes/main.py: Landing page, terms, privacy (no prefix)
# - app/routes/api.py: API endpoints (/api)
# - app/routes/student.py: Student routes (/student)
# - app/routes/admin.py: Admin routes (/admin)
# - app/routes/system_admin.py: System admin routes (/sysadmin)
