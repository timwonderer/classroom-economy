"""
Application factory for Classroom Token Hub.

This module provides create_app() which initializes Flask, extensions,
logging, Jinja filters, and registers blueprints.
"""

import os
import logging
import urllib.parse
import pytz
from datetime import datetime, date, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, request, render_template, session, g
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = ["SECRET_KEY", "DATABASE_URL", "FLASK_ENV", "ENCRYPTION_KEY", "PEPPER_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_vars)
    )


# -------------------- UTILITIES --------------------
from app.utils.encryption import PIIEncryptedType
from app.utils.helpers import format_utc_iso, is_safe_url, render_markdown
from app.utils.constants import THEME_PROMPTS


def url_encode_filter(s):
    """URL-encode a string for use in URLs."""
    return urllib.parse.quote_plus(s)


def format_datetime(value, fmt='%Y-%m-%d %I:%M %p'):
    """
    Convert a UTC datetime to the user's timezone (from session) and format it.
    Defaults to Pacific Time if no timezone is set in the session.
    Handles both datetime and date objects.
    """
    if not value:
        return ''

    # Get user's timezone from session, default to Los Angeles
    tz_name = session.get('timezone', 'America/Los_Angeles')
    try:
        target_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        # Use current_app.logger if available, otherwise print warning
        try:
            from flask import current_app
            current_app.logger.warning(f"Invalid timezone '{tz_name}' in session, defaulting to LA.")
        except RuntimeError:
            print(f"WARNING: Invalid timezone '{tz_name}' in session, defaulting to LA.")
        target_tz = pytz.timezone('America/Los_Angeles')

    utc = pytz.utc

    # Convert date objects to datetime objects at midnight
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())

    # Localize naive datetimes as UTC before converting
    dt = value if getattr(value, 'tzinfo', None) else utc.localize(value)

    local_dt = dt.astimezone(target_tz)
    return local_dt.strftime(fmt)


# -------------------- APPLICATION FACTORY --------------------

def create_app():
    """
    Application factory function.

    Creates and configures the Flask application, initializes extensions,
    sets up logging, registers Jinja filters, and registers blueprints.

    Returns:
        Flask: Configured Flask application instance
    """
    # Get the parent directory of the app package (project root)
    # This is needed because templates/ and static/ are at project root, not in app/
    import os as _os
    basedir = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..'))

    app = Flask(__name__,
                template_folder=_os.path.join(basedir, 'templates'),
                static_folder=_os.path.join(basedir, 'static'))

    # -------------------- CONFIGURATION --------------------
    app.config.from_mapping(
        DEBUG=False,
        ENV=os.environ["FLASK_ENV"],
        SECRET_KEY=os.environ["SECRET_KEY"],
        SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        TEMPLATES_AUTO_RELOAD=True,
        TURNSTILE_SITE_KEY=os.getenv("TURNSTILE_SITE_KEY"),
        TURNSTILE_SECRET_KEY=os.getenv("TURNSTILE_SECRET_KEY"),
    )

    # Enable Jinja2 template hot reloading without server restart
    app.jinja_env.auto_reload = True

    # -------------------- EXTENSIONS --------------------
    from app.extensions import db, migrate, csrf

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # -------------------- LOGGING --------------------
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = os.getenv(
        "LOG_FORMAT",
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(logging.Formatter(log_format))

    app.logger.setLevel(log_level)
    # Prevent duplicate log entries by clearing handlers first
    app.logger.handlers.clear()
    app.logger.addHandler(stream_handler)

    if os.getenv("FLASK_ENV", app.config.get("ENV")) == "production":
        log_file = os.getenv("LOG_FILE", "app.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        app.logger.addHandler(file_handler)

    # -------------------- JINJA2 FILTERS AND GLOBALS --------------------
    app.jinja_env.filters['url_encode'] = url_encode_filter
    app.jinja_env.filters['urlencode'] = url_encode_filter
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['markdown'] = render_markdown

    # Add built-in functions to Jinja2 globals
    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max

    def is_maintenance_mode_enabled():
        """Return True when maintenance mode is enabled via environment variable."""
        return os.getenv("MAINTENANCE_MODE", "").lower() in {"1", "true", "yes", "on"}

    def maintenance_context():
        """Context for the maintenance page, sourced from environment variables."""
        badge_type = os.getenv("MAINTENANCE_BADGE_TYPE", "maintenance")
        badge_meta = {
            "maintenance": ("construction", "Scheduled Maintenance"),
            "bug": ("bug_report", "Bug Fix In Progress"),
            "security": ("shield", "Security Patch"),
            "update": ("system_update", "System Update"),
            "feature": ("new_releases", "New Feature Deployment"),
            "unavailable": ("cloud_off", "Server Unavailable"),
            "error": ("error", "Unexpected Error"),
        }
        badge_icon, badge_text = badge_meta.get(badge_type, badge_meta["maintenance"])

        return {
            "message": os.getenv(
                "MAINTENANCE_MESSAGE",
                "We're performing scheduled maintenance to keep Classroom Economy running smoothly.",
            ),
            "expected_back": os.getenv("MAINTENANCE_EXPECTED_END", ""),
            "contact_email": os.getenv("MAINTENANCE_CONTACT", os.getenv("SUPPORT_EMAIL", "")),
            "badge_type": badge_type,
            "badge_icon": badge_icon,
            "badge_text": badge_text,
            "status_description": os.getenv(
                "MAINTENANCE_STATUS_DESCRIPTION",
                "Unavailable"
            ),
        }

    @app.before_request
    def show_maintenance_page():
        """Display a friendly maintenance page when maintenance mode is on."""
        # If maintenance is not enabled, proceed normally.
        if not is_maintenance_mode_enabled():
            return None

        # Always allow health check and static assets.
        if request.endpoint in {"main.health_check"}:
            return None
        if request.path.startswith("/static/"):
            return None

        # Allow system admin login/logout routes so admins can establish a bypass session.
        if request.endpoint in {"sysadmin.login", "sysadmin.logout"}:
            return None

        # --- Bypass Logic --------------------------------------------------
        # Provide controlled access for sysadmin or via a token when maintenance
        # mode is active, so production can be validated while end users see
        # the maintenance page.
        #
        # Environment variables:
        #   MAINTENANCE_SYSADMIN_BYPASS= true|1|yes|on   (allow system admin session)
        #   MAINTENANCE_BYPASS_TOKEN= <string>           (query param maintenance_bypass=<token>)
        #
        # System admin detection relies on session['is_system_admin'] being set
        # by authentication logic elsewhere.
        sysadmin_bypass_enabled = os.getenv("MAINTENANCE_SYSADMIN_BYPASS", "").lower() in {"1","true","yes","on"}
        bypass_token = os.getenv("MAINTENANCE_BYPASS_TOKEN", "")
        provided_token = request.args.get("maintenance_bypass")

        # Persistent session bypass for admin-enabled testing across other roles.
        global_bypass = session.get("maintenance_global_bypass") is True
        is_sysadmin = session.get("is_system_admin") is True
        token_valid = bool(bypass_token and provided_token and provided_token == bypass_token)

        # Allow if sysadmin bypass on and user is sysadmin
        if sysadmin_bypass_enabled and is_sysadmin:
            app.logger.debug("Maintenance bypass granted (sysadmin).")
            # Promote to global bypass so teacher/student logins in same session do not need query param.
            session.setdefault("maintenance_global_bypass", True)
            g.maintenance_bypass_active = True
            return None

        # Allow if a prior sysadmin granted global bypass (sticky across role changes)
        if global_bypass:
            app.logger.debug("Maintenance bypass granted (global session).")
            g.maintenance_bypass_active = True
            return None

        # Allow if valid token provided (works for any authenticated role once past initial page)
        if token_valid:
            app.logger.debug("Maintenance bypass granted (token).")
            # Persist for remainder of session
            session.setdefault("maintenance_global_bypass", True)
            g.maintenance_bypass_active = True
            return None

        # Otherwise show maintenance page.
        return render_template("maintenance.html", **maintenance_context()), 503

    @app.before_request
    def set_rls_tenant_context():
        """
        Set PostgreSQL Row-Level Security tenant context for multi-tenancy isolation.

        This sets the app.current_teacher_id session variable that RLS policies use
        to filter database queries. This ensures teachers can only see/modify their
        own data at the database level, even if application code has bugs.

        This follows industry best practices from AWS, Azure, and major SaaS providers.
        """
        # Skip for static files, health checks, and public routes
        if request.path.startswith("/static/"):
            return None
        if request.endpoint in {"main.health_check"}:
            return None

        # Set tenant context for both admin and student sessions
        teacher_id = None
        
        # Check if admin is logged in
        admin_id = session.get('admin_id')
        if admin_id:
            teacher_id = admin_id
        else:
            # Check if student is logged in and has a current teacher
            # Students query teacher-scoped tables (StoreItem, RentSettings, etc.)
            # so we need to set RLS context for them too
            student_id = session.get('student_id')
            if student_id:
                # Get the student's current teacher context
                # This uses the multi-period support system
                current_teacher_id = session.get('current_teacher_id')
                if current_teacher_id:
                    teacher_id = current_teacher_id
        
        if teacher_id:
            try:
                from sqlalchemy import text
                from app.extensions import db

                # SET LOCAL only affects the current transaction
                # This is automatically reset after each request
                db.session.execute(
                    text("SET LOCAL app.current_teacher_id = :teacher_id"),
                    {"teacher_id": teacher_id}
                )
                app.logger.debug(f"RLS context set for teacher_id={teacher_id}")
            except Exception as e:
                # Log but don't fail the request - RLS will just filter to empty results
                app.logger.error(f"Failed to set RLS tenant context: {str(e)}")

        return None

    @app.before_request
    def log_cloudflare_status():
        """
        Log warnings when requests don't come through Cloudflare proxy.

        This helps monitor whether the DigitalOcean firewall is properly
        configured to only accept traffic from Cloudflare IPs.
        """
        # Skip for static files and health checks
        if request.path.startswith("/static/"):
            return None
        if request.endpoint in {"main.health_check", "main.health_check_deep"}:
            return None

        # Only check in production
        if app.config.get('ENV') == 'production':
            from app.utils.ip_handler import validate_cloudflare_request, get_real_ip

            if not validate_cloudflare_request():
                real_ip = get_real_ip()
                app.logger.warning(
                    f"Request not from Cloudflare IP: {request.remote_addr} "
                    f"(real_ip: {real_ip}, path: {request.path}, method: {request.method})"
                )

        return None

    # -------------------- CONTEXT PROCESSORS --------------------
    @app.context_processor
    def inject_global_settings():
        """Inject global settings into all templates."""
        bypass_flag = getattr(g, 'maintenance_bypass_active', False)
        if is_maintenance_mode_enabled() and not bypass_flag:
            return {
                'global_rent_enabled': False,
                'turnstile_site_key': app.config.get('TURNSTILE_SITE_KEY'),
                'maintenance_bypass_active': False,
            }

        # Note: Rent settings are now per-teacher, so there's no global rent enabled flag
        # Templates should check rent settings for the specific teacher context
        return {
            'global_rent_enabled': False,  # Deprecated: rent is now per-teacher
            'turnstile_site_key': app.config.get('TURNSTILE_SITE_KEY'),
            'maintenance_bypass_active': bypass_flag,
        }

    @app.context_processor
    def inject_view_as_student_status():
        """Inject view-as-student mode status into all templates."""
        from app.auth import is_viewing_as_student
        return {
            'is_viewing_as_student': is_viewing_as_student()
        }

    # -------------------- REGISTER BLUEPRINTS --------------------
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    from app.routes.system_admin import sysadmin_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(sysadmin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # -------------------- CLI COMMANDS --------------------
    from app import cli_commands
    cli_commands.init_app(app)

    # -------------------- SCHEDULED TASKS --------------------
    if not app.config.get("TESTING") and app.config.get("ENV") != "testing":
        from app.scheduled_tasks import init_scheduled_tasks
        init_scheduled_tasks(app)

    return app


# Create a default application instance for compatibility with legacy imports
app = create_app()

# Re-export commonly used objects for convenience/legacy support
from app.extensions import db  # noqa: E402
from app.models import Student, TapEvent, Transaction  # noqa: E402
from app.routes.student import apply_savings_interest  # noqa: E402

__all__ = [
    "app",
    "create_app",
    "db",
    "Student",
    "TapEvent",
    "Transaction",
    "apply_savings_interest",
]
