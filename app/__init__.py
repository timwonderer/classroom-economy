"""
Application factory for Classroom Token Hub.

This module provides create_app() which initializes Flask, extensions,
logging, Jinja filters, and registers blueprints.
"""

import os
import logging
import urllib.parse
import uuid
import pytz
import sqlalchemy as sa
from datetime import datetime, date, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, request, render_template, session, g, url_for, has_request_context
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from project root
# Explicitly specify path to ensure .env is found regardless of working directory
project_root = Path(__file__).parent.parent
dotenv_path = project_root / '.env'
# Load defaults from .env, but never override variables explicitly provided by
# the caller (for example `DATABASE_URL=... flask db ...` in migration gates).
#
# This preserves deterministic CLI behavior across dev/test environments while
# still allowing local defaults when env vars are absent.
load_dotenv(dotenv_path=dotenv_path, override=False)

# Validate required environment variables
required_env_vars = ["SECRET_KEY", "DATABASE_URL", "FLASK_ENV", "ENCRYPTION_KEY", "PEPPER_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_vars)
    )


# -------------------- UTILITIES --------------------
from app.utils.encryption import PIIEncryptedType
from app.utils.helpers import format_utc_iso, is_safe_url, render_markdown, docs_url_for
from app.utils.constants import THEME_PROMPTS


def url_encode_filter(s):
    """URL-encode a string for use in URLs."""
    return urllib.parse.quote_plus(s)


def nl2br_filter(s):
    """Convert newlines to <br> tags for HTML display."""
    # TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:
    # - soft_str and soft_unicode removed (deprecated since 2.0)
    # - Markup.striptags() behavior may differ
    # - Review Jinja2 compatibility before upgrading from 2.1.5 to 3.0.3
    from markupsafe import Markup
    if s is None:
        return ''
    # Replace \n with <br> and return as safe HTML
    return Markup(str(s).replace('\n', '<br>\n'))


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

REQUEST_ID_HEADERS = ("X-Request-Id", "X-Correlation-Id")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        context = getattr(g, "correlation_context", None) if has_request_context() else None
        if not hasattr(record, "request_id"):
            if has_request_context():
                record.request_id = getattr(g, "request_id", "-")
            else:
                record.request_id = "-"
        if not hasattr(record, "actor_type"):
            record.actor_type = context.get("actor_type", "-") if context else "-"
        if not hasattr(record, "actor_public_id"):
            record.actor_public_id = context.get("actor_public_id", "-") if context else "-"
        if not hasattr(record, "class_id"):
            record.class_id = context.get("class_id", "-") if context else "-"
        if not hasattr(record, "endpoint"):
            if has_request_context():
                if request.url_rule and request.url_rule.rule:
                    record.endpoint = request.url_rule.rule
                else:
                    record.endpoint = request.path
            else:
                record.endpoint = "-"
        if not hasattr(record, "method"):
            record.method = request.method if has_request_context() else "-"
        if not hasattr(record, "error_class"):
            record.error_class = "-"
        if not hasattr(record, "error_message"):
            record.error_message = "-"
        if not hasattr(record, "correlation_version"):
            record.correlation_version = 1
        return True


def _get_request_id():
    for header in REQUEST_ID_HEADERS:
        header_value = request.headers.get(header)
        if not header_value:
            continue
        header_value = header_value.strip()
        if 0 < len(header_value) <= 128:
            return header_value
    return uuid.uuid4().hex


def register_error_handlers(app):
    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        if isinstance(e, HTTPException):
            return e

        from app.extensions import db
        from app.services.tlcp import CORRELATION_VERSION, save_error_event

        context = getattr(g, "correlation_context", None) or {}
        endpoint = request.url_rule.rule if request.url_rule and request.url_rule.rule else request.path
        sanitized_message = " ".join(str(e).split())[:500]
        app.logger.exception(
            "Unhandled exception",
            extra={
                "route": request.path,
                "method": request.method,
                "request_id": getattr(g, "request_id", None),
                "actor_type": context.get("actor_type"),
                "actor_public_id": context.get("actor_public_id"),
                "class_id": context.get("class_id"),
                "endpoint": endpoint,
                "error_class": e.__class__.__name__,
                "error_message": sanitized_message,
                "correlation_version": CORRELATION_VERSION,
            },
        )

        try:
            # Roll back any partial view state so it is not accidentally committed,
            # then persist the TLCP error event in a fresh, independent transaction.
            db.session.rollback()
            with db.engine.begin() as conn:
                from app.models import ErrorEvent
                from app.utils.time import utc_now
                if context.get("actor_type") and context.get("actor_public_id"):
                    from app.services.tlcp import _sanitize_error_message
                    conn.execute(
                        sa.text(
                            """
                            INSERT INTO error_events
                                (request_id, actor_type, actor_public_id, class_id,
                                 endpoint, method, error_class, error_message,
                                 correlation_version, created_at)
                            VALUES
                                (:request_id, :actor_type, :actor_public_id, :class_id,
                                 :endpoint, :method, :error_class, :error_message,
                                 :correlation_version, :created_at)
                            """
                        ),
                        {
                            "request_id": getattr(g, "request_id", None),
                            "actor_type": context.get("actor_type"),
                            "actor_public_id": context.get("actor_public_id"),
                            "class_id": context.get("class_id"),
                            "endpoint": endpoint,
                            "method": request.method,
                            "error_class": e.__class__.__name__,
                            "error_message": _sanitize_error_message(sanitized_message),
                            "correlation_version": CORRELATION_VERSION,
                            "created_at": utc_now(),
                        },
                    )
        except Exception:
            app.logger.warning("Failed to persist TLCP error event", exc_info=True)

        # Content-aware error response
        if request.accept_mimetypes.best == "application/json":
            return {"error": "Internal Server Error"}, 500

        # Just in case rendering the template fails
        try:
            return render_template("error_500.html"), 500
        except Exception:
            return "Internal Server Error", 500


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
    flask_env = os.environ["FLASK_ENV"]
    dev_rate_limit_enabled = os.getenv("DEV_ENABLE_RATELIMIT", "").lower() in {"1", "true", "yes", "on"}

    app.config.from_mapping(
        DEBUG=False,
        ENV=flask_env,
        SECRET_KEY=os.environ["SECRET_KEY"],
        SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SECURE=flask_env == "production",  # Only require HTTPS in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_PATH="/",
        TEMPLATES_AUTO_RELOAD=True,
        TURNSTILE_SITE_KEY=os.getenv("TURNSTILE_SITE_KEY"),
        TURNSTILE_SECRET_KEY=os.getenv("TURNSTILE_SECRET_KEY"),
        EXTERNAL_DOCS_BASE_URL=os.getenv("EXTERNAL_DOCS_BASE_URL", "").strip() or None,
        # Dev ergonomics: disable limiter in local development unless explicitly re-enabled.
        RATELIMIT_ENABLED=(flask_env != "development") or dev_rate_limit_enabled,
    )

    # Enable Jinja2 template hot reloading without server restart
    app.jinja_env.auto_reload = True
    app.jinja_env.globals.setdefault("docs_url_for", docs_url_for)

    # -------------------- EXTENSIONS --------------------
    from app.extensions import db, migrate, csrf, limiter
    from app.feats.base import init_feat_enforcement

    db.init_app(app)
    init_feat_enforcement(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # -------------------- LOGGING --------------------
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = os.getenv(
        "LOG_FORMAT",
        "[%(asctime)s] %(levelname)s in %(module)s [%(request_id)s] "
        "[actor=%(actor_type)s:%(actor_public_id)s class_id=%(class_id)s] "
        "[endpoint=%(endpoint)s method=%(method)s] "
        "[error_class=%(error_class)s correlation_version=%(correlation_version)s]: %(message)s",
    )
    if log_format.strip().lower() == "json":
        log_format = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","module":"%(module)s",'
            '"request_id":"%(request_id)s","actor":"%(actor_type)s:%(actor_public_id)s",'
            '"class_id":"%(class_id)s","endpoint":"%(endpoint)s","method":"%(method)s",'
            '"error_class":"%(error_class)s","correlation_version":"%(correlation_version)s",'
            '"message":"%(message)s"}'
        )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(logging.Formatter(log_format))
    stream_handler.addFilter(RequestIdFilter())

    app.logger.setLevel(log_level)
    # Prevent duplicate log entries by clearing handlers first
    app.logger.handlers.clear()
    app.logger.addHandler(stream_handler)

    if os.getenv("FLASK_ENV", app.config.get("ENV")) == "production":
        log_file = os.getenv("LOG_FILE", "app.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        file_handler.addFilter(RequestIdFilter())
        app.logger.addHandler(file_handler)

    # -------------------- DATABASE SAFETY GUARDS --------------------
    # Prevent accidental connection to the wrong database environment
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    normalized_db_url = db_url.lower()
    env = app.config.get("ENV")

    # Guard 1: CRITICAL - Prevent running TESTS against Production/Dev DB
    # If we are in testing mode, we MUST be using a test database (or in-memory sqlite)
    if env == "testing":
        is_test_db = "test" in normalized_db_url or ":memory:" in normalized_db_url
        if not is_test_db:
            error_msg = f"🚨 CRITICAL SAFETY GUARD: Attempting to run TESTS against PRODUCTION/DEV database! ({db_url}) 🚨"
            app.logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Guard 2: WARNING - Warn if running DEVELOPMENT against Test DB
    if env == "development" and "test" in normalized_db_url:
        app.logger.warning(f"🚨 CONFIGURATION WARNING: Using TEST database ({db_url}) in DEVELOPMENT mode! 🚨")

    # -------------------- REQUEST CONTEXT --------------------
    @app.before_request
    def ensure_request_id():
        g.request_id = _get_request_id()

    @app.before_request
    def capture_correlation_context():
        from app.services.tlcp import resolve_actor_context

        g.correlation_context = resolve_actor_context()

    @app.after_request
    def attach_request_id_header(response):
        from app.services.tlcp import persist_request_trace
        from sqlalchemy.orm import Session

        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers.setdefault("X-Request-Id", request_id)
        if app.config.get("TESTING"):
            # Test fixtures wrap each test in transactions; the independent TLCP
            # writer can otherwise contend with teardown deletes.
            return response
        context = getattr(g, "correlation_context", None)
        if context:
            try:
                with Session(db.engine) as tlcp_session:
                    with tlcp_session.begin():
                        persist_request_trace(
                            context=context,
                            request_id=request_id,
                            status_code=response.status_code,
                            _session=tlcp_session,
                        )
            except Exception:
                app.logger.warning("Failed to persist TLCP request trace", exc_info=True)
        return response

    # -------------------- ERROR HANDLERS --------------------
    register_error_handlers(app)

    # -------------------- JINJA2 FILTERS AND GLOBALS --------------------
    app.jinja_env.filters['url_encode'] = url_encode_filter
    app.jinja_env.filters['urlencode'] = url_encode_filter
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['markdown'] = render_markdown
    app.jinja_env.filters['nl2br'] = nl2br_filter

    # Add built-in functions to Jinja2 globals
    app.jinja_env.globals['min'] = min
    app.jinja_env.globals['max'] = max
    app.jinja_env.globals['format_utc_iso'] = format_utc_iso
    
    from app.utils.join_code import get_display_join_code
    app.jinja_env.globals['get_display_join_code'] = get_display_join_code

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
        if request.endpoint in {
            "sysadmin.login",
            "sysadmin.logout",
            "sysadmin.passkey_auth_start",
            "sysadmin.passkey_auth_finish"
        }:
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
        # System admin detection is resolver-backed so session flags alone are not
        # treated as authoritative.
        sysadmin_bypass_enabled = os.getenv("MAINTENANCE_SYSADMIN_BYPASS", "").lower() in {"1","true","yes","on"}
        bypass_token = os.getenv("MAINTENANCE_BYPASS_TOKEN", "")
        provided_token = request.args.get("maintenance_bypass")

        # Persistent session bypass for admin-enabled testing across other roles.
        global_bypass = session.get("maintenance_global_bypass") is True
        try:
            from app.auth import get_current_system_admin

            is_sysadmin = get_current_system_admin() is not None
        except Exception:
            is_sysadmin = False
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
        try:
            from app.auth import get_current_seat, get_current_class_id, get_current_user
            from app.models import ClassEconomy

            # Canonical path for student-scoped requests: class_id -> teacher_id
            current_seat = get_current_seat()
            current_class_id = get_current_class_id()
            if current_seat and current_class_id:
                class_row = ClassEconomy.query.filter_by(class_id=current_class_id).first()
                if class_row and class_row.teacher_id:
                    teacher_id = class_row.teacher_id

            # Canonical user currently has no teacher-role mapping in this phase.
            # Keep this lookup to centralize identity dependency for future phases.
            if teacher_id is None:
                _ = get_current_user()
        except Exception:
            # Keep request resilient; legacy fallbacks below preserve behavior.
            teacher_id = None

        # Legacy fallback path (required until admin identity cutover).
        if teacher_id is None:
            admin_id = session.get('admin_id')
            if admin_id:
                teacher_id = admin_id

        # Legacy student teacher-context fallback.
        if teacher_id is None:
            current_teacher_id = session.get('current_teacher_id')
            if current_teacher_id:
                teacher_id = current_teacher_id
        
        if teacher_id:
            try:
                from sqlalchemy import text
                from app.extensions import db

                # SET LOCAL only affects the current transaction
                # This is automatically reset after each request
                if db.engine.dialect.name != 'sqlite':
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
            try:
                from app.utils.ip_handler import validate_cloudflare_request, get_real_ip

                if not validate_cloudflare_request():
                    real_ip = get_real_ip()
                    app.logger.warning(
                        f"Request not from Cloudflare IP: {request.remote_addr} "
                        f"(real_ip: {real_ip}, path: {request.path}, method: {request.method})"
                    )
            except Exception as e:
                # Don't break requests if Cloudflare monitoring fails
                app.logger.error(f"Error in Cloudflare monitoring: {e}")

        return None

    def build_static_url(filename: str):
        """Return static asset URLs with a cache-busting query parameter."""
        if not filename:
            return url_for('static', filename=filename)

        file_path = os.path.join(app.static_folder, filename)
        try:
            version = int(os.stat(file_path).st_mtime)
            return url_for('static', filename=filename, v=version)
        except (OSError, TypeError) as exc:
            app.logger.debug(f"Could not add cache buster for {filename}: {exc}")
            return url_for('static', filename=filename)

    # Make the helper available even in contexts where context processors
    # might not run (e.g., background tasks rendering templates).
    app.jinja_env.globals['static_url'] = build_static_url

    @app.context_processor
    def inject_static_url():
        """Ensure static_url helper is always available in templates."""
        return {'static_url': build_static_url}

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

    @app.context_processor
    def inject_feature_settings():
        """Inject feature settings into all templates."""
        try:
            # Imports are here to avoid circular dependencies
            from app.models import FeatureSettings
            from app.routes.student import get_feature_settings_for_student
            return {'feature_settings': get_feature_settings_for_student()}
        except Exception as e:
            # This can happen during `flask db` commands before the table exists.
            # Fallback to defaults to avoid breaking CLI commands.
            app.logger.warning(f"Could not load feature settings, falling back to defaults: {e}")
            from app.models import FeatureSettings
            return {'feature_settings': FeatureSettings.get_defaults()}

    @app.context_processor
    def inject_admin_feature_settings():
        """Inject class-scoped admin feature settings into all templates."""
        try:
            from app.auth import get_current_class_id, get_current_user
            from app.models import FeatureSettings
            from app.routes.admin import get_admin_feature_settings_for_join_code

            # Canonical helper-first resolution (legacy fallback retained below).
            _ = get_current_user()
            admin_id = session.get('admin_id')
            join_code = session.get('current_join_code')
            if not join_code:
                current_class_id = get_current_class_id()
                if current_class_id:
                    from app.models import ClassEconomy
                    class_row = ClassEconomy.query.filter_by(class_id=current_class_id).first()
                    join_code = class_row.join_code if class_row else None
            if not admin_id:
                return {'admin_feature_settings': FeatureSettings.get_defaults()}
            return {
                'admin_feature_settings': get_admin_feature_settings_for_join_code(
                    admin_id,
                    join_code=join_code,
                )
            }
        except Exception as e:
            app.logger.warning(f"Could not load admin feature settings, falling back to defaults: {e}")
            from app.models import FeatureSettings
            return {'admin_feature_settings': FeatureSettings.get_defaults()}

    @app.context_processor
    def inject_class_context():
        """Inject current class context and available classes for student navigation."""
        try:
            from app.auth import get_logged_in_student, get_current_seat, get_current_class_id, get_current_user
            from app.models import Seat, Admin, ClassEconomy
            from flask import session
            from app.utils.display_name_session import (
                get_teacher_display_name_cache,
                upsert_teacher_display_name_cache,
            )

            current_seat_ctx = get_current_seat()
            _ = get_current_user()
            student_id = current_seat_ctx.student_id if current_seat_ctx and current_seat_ctx.student_id else None
            if student_id is None:
                # Legacy fallback until all student routes/session anchors are migrated.
                student = get_logged_in_student()
                student_id = student.id if student else None
            if not student_id:
                return {'current_class_context': None, 'available_classes': []}

            # Get all claimed seats for this student
            claimed_seats = (
                Seat.query
                .filter_by(student_id=student_id)
                .filter(Seat.claimed_at.isnot(None))
                .order_by(Seat.class_id, Seat.block)
                .all()
            )

            if not claimed_seats:
                return {'current_class_context': None, 'available_classes': []}

            claimed_class_ids = {seat.class_id for seat in claimed_seats if seat.class_id}
            requested_class_id = (session.get('current_class_id') or '').strip()
            resolved_class_id = (
                requested_class_id
                or get_current_class_id()
            )
            if resolved_class_id not in claimed_class_ids:
                resolved_class_id = None

            # Class context is required whenever the student has at least one claimed seat.
            current_seat = next(
                (seat for seat in claimed_seats if seat.class_id == resolved_class_id),
                claimed_seats[0]
            )

            # Keep session context aligned with canonical current seat scope.
            session['current_seat_id'] = current_seat.id
            session['seat_id'] = current_seat.id
            session['current_class_id'] = current_seat.class_id
            session['class_id'] = current_seat.class_id
            session['current_join_code'] = current_seat.join_code

            class_rows_by_class_id = {
                row.class_id: row
                for row in ClassEconomy.query.filter(
                    ClassEconomy.class_id.in_([seat.class_id for seat in claimed_seats if seat.class_id])
                ).all()
            }

            # Build list of available classes with teacher names.
            # teacher_id is on ClassEconomy, not on Seat.
            teacher_ids = sorted({row.teacher_id for row in class_rows_by_class_id.values() if row.teacher_id})
            teacher_name_cache = get_teacher_display_name_cache()
            missing_ids = [tid for tid in teacher_ids if str(tid) not in teacher_name_cache]
            if missing_ids:
                cache_updates = {}
                for teacher in Admin.query.filter(Admin.id.in_(missing_ids)).all():
                    cache_updates[str(teacher.id)] = teacher.get_display_name()
                if cache_updates:
                    upsert_teacher_display_name_cache(cache_updates)
                    teacher_name_cache.update(cache_updates)

            available_classes = []
            for seat in claimed_seats:
                class_row = class_rows_by_class_id.get(seat.class_id)
                row_teacher_id = getattr(class_row, 'teacher_id', None)
                teacher_name = teacher_name_cache.get(str(row_teacher_id), 'Unknown') if row_teacher_id else 'Unknown'
                class_label = (class_row.display_name if class_row and class_row.display_name else None) or seat.join_code
                available_classes.append({
                    'join_code': seat.join_code,
                    'class_id': getattr(class_row, 'class_id', None),
                    'class_identifier': class_label,
                    'class_timezone': getattr(class_row, 'class_timezone', None),
                    'teacher_name': teacher_name,
                    'block': seat.block,
                    'block_display': class_label,
                    'is_current': seat.class_id == current_seat.class_id
                })

            # Build current class context from cache.
            current_class_row = class_rows_by_class_id.get(current_seat.class_id)
            current_teacher_id = getattr(current_class_row, 'teacher_id', None)
            current_class_label = (
                current_class_row.display_name
                if current_class_row and current_class_row.display_name
                else current_seat.join_code
            )
            current_class_context = {
                'join_code': current_seat.join_code,
                'class_id': getattr(current_class_row, 'class_id', None),
                'class_identifier': current_class_label,
                'class_timezone': getattr(current_class_row, 'class_timezone', None),
                'teacher_name': teacher_name_cache.get(str(current_teacher_id), 'Unknown') if current_teacher_id else 'Unknown',
                'teacher_id': current_teacher_id,
                'block': current_seat.block,
                'block_display': current_class_label,
                'student_full_name': current_seat.identity_profile.full_name if current_seat.identity_profile else "",
            }

            return {
                'current_class_context': current_class_context,
                'available_classes': available_classes,
                'current_seat': current_seat  # Add seat object for template access
            }
        except Exception as e:
            app.logger.warning(f"Could not load class context: {e}")
            return {'current_class_context': None, 'available_classes': []}

    @app.context_processor
    def inject_admin_class_context():
        """Inject current class context and available classes for admin navigation."""
        try:
            from flask import session
            from app.models import ClassEconomy
            from app.routes.admin import _resolve_admin_class_context
            from app.auth import get_current_user, get_current_class_id

            _ = get_current_user()
            admin_id = session.get('admin_id')
            if not admin_id or not session.get('is_admin'):
                return {'admin_current_class_context': None, 'admin_available_classes': []}

            class_rows = (
                ClassEconomy.query
                .filter(ClassEconomy.teacher_id == admin_id)
                .order_by(ClassEconomy.display_name.asc(), ClassEconomy.join_code.asc())
                .all()
            )
            if not class_rows:
                return {'admin_current_class_context': None, 'admin_available_classes': []}

            admin_available_classes = []
            for class_row in class_rows:
                if not class_row.join_code:
                    continue
                class_label = class_row.display_name or class_row.join_code
                admin_available_classes.append({
                    'join_code': class_row.join_code,
                    'class_id': class_row.class_id,
                    'class_identifier': class_label,
                    'class_timezone': class_row.class_timezone,
                    'block': class_row.section,
                    'block_display': class_label,
                })

            if not admin_available_classes:
                return {'admin_current_class_context': None, 'admin_available_classes': []}

            resolved_context = _resolve_admin_class_context(admin_id)
            resolved_class_id = get_current_class_id() or (resolved_context.get('class_id') if resolved_context else None)
            current_class = next(
                (item for item in admin_available_classes if item['class_id'] == resolved_class_id),
                admin_available_classes[0],
            )

            admin_current_class_context = {
                'join_code': current_class['join_code'],
                'class_id': current_class['class_id'],
                'class_identifier': current_class['class_identifier'],
                'class_timezone': current_class['class_timezone'],
                'block': current_class['block'],
                'block_display': current_class['block_display'],
            }

            for class_option in admin_available_classes:
                class_option['is_current'] = class_option['class_id'] == admin_current_class_context['class_id']

            return {
                'admin_current_class_context': admin_current_class_context,
                'admin_available_classes': admin_available_classes,
            }
        except Exception as e:
            app.logger.warning(f"Could not load admin class context: {e}")
            return {'admin_current_class_context': None, 'admin_available_classes': []}

    @app.context_processor
    def inject_current_admin():
        """Inject current admin object into all templates."""
        try:
            from app.auth import get_current_user, get_current_admin
            from app.utils.display_name_session import (
                get_admin_display_name_cache,
                set_admin_display_name_cache,
            )

            _ = get_current_user()
            admin = get_current_admin()
            if admin:
                cached_name = get_admin_display_name_cache(admin_id=admin.id)
                if not cached_name:
                    cached_name = admin.get_display_name()
                    set_admin_display_name_cache(admin_id=admin.id, display_name=cached_name)
                return {'current_admin': admin, 'current_admin_display_name': cached_name}
            return {'current_admin': None, 'current_admin_display_name': None}
        except Exception as e:
            app.logger.warning(f"Could not load current admin: {e}")
            return {'current_admin': None, 'current_admin_display_name': None}

    @app.context_processor
    def inject_current_sysadmin():
        """Inject current system admin object into all templates."""
        try:
            from app.auth import get_current_system_admin

            sysadmin = get_current_system_admin()
            if sysadmin:
                return {'current_sysadmin': sysadmin}
            return {'current_sysadmin': None}
        except Exception as e:
            app.logger.warning(f"Could not load current system admin: {e}")
            return {'current_sysadmin': None}

    @app.context_processor
    def inject_docs_helpers():
        """Expose docs URL helpers to templates."""
        return {"docs_url_for": docs_url_for}

    # -------------------- REGISTER BLUEPRINTS --------------------
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    from app.routes.system_admin import sysadmin_bp
    from app.routes.student import student_bp
    from app.routes.admin import admin_bp
    from app.routes.docs import docs_bp
    from app.routes.analytics import analytics_bp
    from app.routes.recovery import recovery_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(sysadmin_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(recovery_bp)

    # -------------------- SECURITY HEADERS --------------------
    @app.after_request
    def set_security_headers(response):
        """
        Add security headers to all HTTP responses.

        These headers protect against common web vulnerabilities:
        - HSTS: Force HTTPS connections
        - X-Frame-Options: Prevent clickjacking
        - X-Content-Type-Options: Prevent MIME sniffing attacks
        - CSP: Mitigate XSS attacks
        - Referrer-Policy: Control referrer information leakage

        See: https://owasp.org/www-project-secure-headers/
        """
        # Skip for static files (already have caching headers)
        if request.path.startswith('/static/'):
            return response

        # Public embeddable pages
        # Only the office verification page is embeddable.
        is_embeddable = request.path.startswith('/verify/hallpass/')

        # HTTPS Enforcement (HSTS)
        # Forces browsers to use HTTPS for 1 year, including subdomains
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # Clickjacking Protection
        # Allow framing for public embeddable pages, restrict for everything else
        if not is_embeddable:
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        # MIME Sniffing Protection
        # Prevents browsers from interpreting files as a different MIME type
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Referrer Policy
        # Only send full URL to same origin, origin only to other HTTPS sites
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Content Security Policy (CSP)
        # Restricts resource loading to prevent XSS attacks
        # Adjusted for Google Fonts, Material Icons, Cloudflare Turnstile, jsdelivr CDN, Font Awesome, and Passwordless.dev
        passwordless_script_src = "https://cdn.passwordless.dev"
        passwordless_connect_src = "https://cdn.passwordless.dev https://v4.passwordless.dev"
        csp_directives = [
            "default-src 'self'",
            (
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://challenges.cloudflare.com https://cdn.jsdelivr.net "
                "https://static.cloudflareinsights.com "
                f"{passwordless_script_src}"
            ),
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "img-src 'self' data: https:",
            (
                "connect-src 'self' https://challenges.cloudflare.com "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
                "https://static.cloudflareinsights.com "
                f"{passwordless_connect_src}"
            ),
            "frame-src https://challenges.cloudflare.com",
            "worker-src 'self' blob:",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        # Allow embedding for public hall pass display pages
        if is_embeddable:
            csp_directives.append("frame-ancestors *")
        else:
            csp_directives.append("frame-ancestors 'self'")

        response.headers['Content-Security-Policy'] = "; ".join(csp_directives)

        # Permissions Policy (formerly Feature-Policy)
        # Disable browser features not needed by the application
        permissions = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
        ]
        response.headers['Permissions-Policy'] = ", ".join(permissions)

        return response

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
from app.models import Student, AttendanceSession, Transaction  # noqa: E402
from app.routes.student import apply_savings_interest  # noqa: E402

__all__ = [
    "app",
    "create_app",
    "db",
    "Student",
    "AttendanceSession",
    "Transaction",
    "apply_savings_interest",
]
