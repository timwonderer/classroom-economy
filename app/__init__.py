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

from flask import Flask, request, render_template, session
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
        return {
            "message": os.getenv(
                "MAINTENANCE_MESSAGE",
                "We're performing scheduled maintenance to keep Classroom Economy running smoothly.",
            ),
            "expected_back": os.getenv("MAINTENANCE_EXPECTED_END", ""),
            "contact_email": os.getenv("MAINTENANCE_CONTACT", os.getenv("SUPPORT_EMAIL", "")),
        }

    @app.before_request
    def show_maintenance_page():
        """Display a friendly maintenance page when maintenance mode is on."""
        if not is_maintenance_mode_enabled():
            return None

        if request.endpoint in {"main.health_check"}:
            return None

        if request.path.startswith("/static/"):
            return None

        return render_template("maintenance.html", **maintenance_context()), 503

    # -------------------- CONTEXT PROCESSORS --------------------
    @app.context_processor
    def inject_global_settings():
        """Inject global settings into all templates."""
        if is_maintenance_mode_enabled():
            return {
                'global_rent_enabled': False,
                'turnstile_site_key': app.config.get('TURNSTILE_SITE_KEY')
            }

        # Note: Rent settings are now per-teacher, so there's no global rent enabled flag
        # Templates should check rent settings for the specific teacher context
        return {
            'global_rent_enabled': False,  # Deprecated: rent is now per-teacher
            'turnstile_site_key': app.config.get('TURNSTILE_SITE_KEY')
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
