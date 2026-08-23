"""
Root application module for Classroom Token Hub.

This module serves as the WSGI entry point. All routes have been modularized
into blueprints.

For gunicorn: wsgi:app
"""

# Set timezone to UTC to ensure all datetime operations use UTC
import os
import sys
import time
import platform
from pathlib import Path
from dotenv import load_dotenv

# Load .env defaults before importing the app, but preserve explicitly provided
# environment variables (e.g., DATABASE_URL overrides for migration/test gates).
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

os.environ['TZ'] = 'UTC'

# tzset() is not available on Windows
if platform.system() != 'Windows':
    time.tzset()  # Apply timezone change

from flask import has_request_context, render_template, request, session
from datetime import datetime, timedelta, timezone
import traceback
import collections

# -------------------- APPLICATION FACTORY --------------------
# Import and create the Flask application using the factory pattern
from app import app
from app.extensions import db, migrate, csrf
from app.feats.base import FEATContext


def maintenance_mode_enabled():
    """Return True when maintenance mode is enabled via environment variable."""
    return os.getenv("MAINTENANCE_MODE", "").lower() in {"1", "true", "yes", "on"}


def get_validated_status_page_url():
    """
    Return the STATUS_PAGE_URL if it's valid, otherwise None.
    
    Validates that the URL starts with an expected domain to prevent
    potential phishing attacks if an attacker controls the environment variable.
    
    Currently only allows UptimeRobot status pages. To support other status
    page providers, add their specific domain patterns to the validation.
    """
    url = os.getenv('STATUS_PAGE_URL')
    if url and url.startswith('https://stats.uptimerobot.com/'):
        return url
    return None


# -------------------- APPLICATION IMPORTS --------------------
# Models
from app.models import (
    Transaction,
    # TapEvent removed — tap_events unauthorized; use attendance_sessions (DOM-ATT-001)
    HallPassLog,
    StoreItem,
    # StudentItem removed — student_items unauthorized; use store_purchases + redemption_events (DOM-STORE-001)
    RentSettings,
    User,
    UserRole,
    PayrollSettings,
)

# Auth utilities (Stage 3)
from app.auth import (
    SESSION_TIMEOUT_MINUTES,
    login_required,
    admin_required,
    system_admin_required,
)

# Utilities (Stage 5)
from app.utils.helpers import format_utc_iso, is_safe_url
from app.utils.encryption import PIIEncryptedType
from app.utils.constants import THEME_PROMPTS


# NOTE: The ``create-sysadmin`` CLI command lives in ``app/cli_commands.py`` and
# is registered on every app instance via ``init_app`` (app/__init__.py). It is
# intentionally NOT defined here so it is discoverable by the test runner and
# any entrypoint, not just this WSGI module.



# -------------------- APPLICATION HOOKS --------------------
# Automatically create the default admin before the application starts serving
# requests in case migrations ran but the CLI command was not executed
# (e.g. on Azure). Use ``before_serving`` when available (Flask >=2.3),
# otherwise fall back to ``before_first_request`` for older Flask versions.

_admin_checked = False





if hasattr(app, "before_serving"):
    @app.before_serving
    def create_default_admin_if_needed():
        pass
elif hasattr(app, "before_first_request"):
    @app.before_first_request
    def create_default_admin_if_needed():
        pass
else:
    @app.before_request
    def create_default_admin_if_needed():
        pass


# -------------------- CONTEXT PROCESSORS --------------------

@app.context_processor
def inject_payroll_status():
    """Make payroll settings status available in all templates."""
    if maintenance_mode_enabled():
        return dict(has_payroll_settings=False)

    # Context processors must be read-only; never trigger autoflush from pending session state.
    with db.session.no_autoflush:
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
        in_request_context = has_request_context()

        # Never persist noisy static asset misses.
        if in_request_context and request.path in {"/favicon.ico", "/sw.js"}:
            return None

        # FEAT constitutional rule: no ORM writes outside FEAT context.
        from app.feats.base import is_feat_active
        if not is_feat_active():
            app.logger.warning(
                "Skipping DB error log outside FEAT context: %s %s",
                error_type or "unknown",
                request.path if in_request_context else "-",
            )
            return None

        # Get request information if available
        request_path = request.path if in_request_context else None
        request_method = request.method if in_request_context else None
        user_agent = request.headers.get('User-Agent', None) if in_request_context else None

        # Get real IP (handles Cloudflare proxy)
        ip_address = None
        if in_request_context:
            try:
                from app.utils.ip_handler import get_real_ip
                ip_address = get_real_ip()
            except Exception:
                # Fallback to remote_addr if import fails
                ip_address = request.remote_addr

        # Get log output
        if log_output is None:
            log_output = get_last_log_lines(50)

        # Legacy database error logging has been removed.
        return None
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
    current_time = datetime.now(timezone.utc)
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
# - app/routes/admin.py: teacher-facing admin routes (/admin)
# - app/routes/system_admin.py: System admin routes (/sysadmin)
