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
from urllib.parse import urlparse, urljoin

from flask import Flask, request, session
from dotenv import load_dotenv
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet

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

class PIIEncryptedType(TypeDecorator):
    """Custom AES encryption for PII fields using Fernet."""
    impl = LargeBinary

    def __init__(self, key_env_var, *args, **kwargs):
        key = os.getenv(key_env_var)
        if not key:
            raise RuntimeError(f"Missing required environment variable: {key_env_var}")
        self.fernet = Fernet(key)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode('utf-8')
        return self.fernet.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self.fernet.decrypt(value)
        return decrypted.decode('utf-8')


def format_utc_iso(dt):
    """Return a UTC ISO-8601 string (with trailing Z) for a datetime or None."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def is_safe_url(target):
    """
    Ensure a redirect URL is safe by checking if it's on the same domain.
    """
    # Allow empty targets
    if not target:
        return True
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


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
    app = Flask(__name__)

    # -------------------- CONFIGURATION --------------------
    app.config.from_mapping(
        DEBUG=False,
        ENV=os.environ["FLASK_ENV"],
        SECRET_KEY=os.environ["SECRET_KEY"],
        SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        TEMPLATES_AUTO_RELOAD=True,
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

    # Add built-in functions to Jinja2 globals
    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max

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

    return app
