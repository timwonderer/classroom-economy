"""
Common utility functions for Classroom Economy application.

This module provides reusable helper functions for:
- Date/time formatting (ISO-8601 with UTC)
- URL safety validation for redirects
- Markdown to HTML conversion with sanitization
- Documentation URL routing for in-app and external docs surfaces
"""

from datetime import timezone
from urllib.parse import urlparse, urljoin
import hashlib
import hmac
import json
import os
from pathlib import Path

from flask import request, current_app, g, session, render_template, url_for
# TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:
# - soft_str and soft_unicode removed (deprecated since 2.0)
# - Markup.striptags() behavior may differ
# - Review Jinja2 compatibility before upgrading from 2.1.5 to 3.0.3
from markupsafe import Markup
import markdown
import bleach


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROUTE_MAP_PATH = _PROJECT_ROOT / "docs-site" / "route-map.json"


def _load_external_docs_route_map():
    """Load the public-doc migration map shared with the Docusaurus site."""
    try:
        return json.loads(_DOCS_ROUTE_MAP_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


EXTERNAL_DOCS_ROUTE_MAP = _load_external_docs_route_map()


def render_template_with_fallback(template_name, **context):
    """
    Renders a template with static_url helper available.

    Note: Mobile-specific templates have been removed. The responsive design
    now uses CSS media queries and adaptive layouts instead.
    """
    # Ensure static_url helper is always available even if Jinja globals/context processors are missing
    static_url_func = current_app.jinja_env.globals.get('static_url')

    if not static_url_func:
        current_app.logger.warning("static_url missing from Jinja globals; using fallback with cache-busting")

        def _fallback_static_url(filename: str):
            if not filename:
                return url_for('static', filename=filename)

            file_path = os.path.join(current_app.static_folder, filename)
            try:
                version = int(os.stat(file_path).st_mtime)
                return url_for('static', filename=filename, v=version)
            except (OSError, TypeError) as exc:
                current_app.logger.debug(f"Could not add cache buster for {filename}: {exc}")
                return url_for('static', filename=filename)

        static_url_func = _fallback_static_url

    context.setdefault('static_url', static_url_func)
    context.setdefault('docs_url_for', docs_url_for)

    return render_template(template_name, **context)


def has_internal_docs_session():
    """Return True when docs should stay inside the Flask app shell."""
    from app.auth import get_current_seat, get_current_user

    return bool(
        get_current_seat() is not None
        or get_current_user() is not None
        or getattr(getattr(g, 'canonical_context', None), 'actor_role', None) == 'sysadmin'
    )


def get_external_docs_base_url():
    """Return a normalized external docs origin/path or None if unset/invalid."""
    base_url = (current_app.config.get("EXTERNAL_DOCS_BASE_URL") or "").strip()
    if not base_url:
        return None

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        current_app.logger.warning("Ignoring invalid EXTERNAL_DOCS_BASE_URL: %r", base_url)
        return None

    return base_url.rstrip("/")


def get_external_docs_target(doc_path=None):
    """Return an external docs target path for a migrated route, or None."""
    raw_doc_path = (doc_path or "").strip()
    if not raw_doc_path:
        return ""

    base_path = raw_doc_path.partition("#")[0].strip("/")
    return EXTERNAL_DOCS_ROUTE_MAP.get(base_path)


def docs_url_for(doc_path=None, prefer_external=None):
    """
    Build a docs URL that can target either the in-app Flask docs renderer
    or the external Docusaurus site during the migration.
    """
    raw_doc_path = (doc_path or "").strip()
    base_path, _, anchor = raw_doc_path.partition("#")
    normalized_doc_path = base_path.strip("/")
    normalized_anchor = f"#{anchor}" if anchor else ""

    if prefer_external is None:
        prefer_external = not has_internal_docs_session()

    external_base = get_external_docs_base_url()
    external_target = get_external_docs_target(normalized_doc_path)
    if prefer_external and external_base and external_target is not None:
        normalized_target = external_target.strip("/")
        if normalized_target:
            return f"{external_base}/{normalized_target}{normalized_anchor}"
        return f"{external_base}/{normalized_anchor}".rstrip("/")

    if normalized_doc_path:
        return f"{url_for('docs.view_doc', doc_path=normalized_doc_path)}{normalized_anchor}"
    return url_for("docs.index")


def should_redirect_public_docs(doc_path=None):
    """Return True when unauthenticated docs traffic should use the external site."""
    return (
        bool(get_external_docs_base_url())
        and not has_internal_docs_session()
        and get_external_docs_target(doc_path) is not None
    )


def format_utc_iso(dt):
    """Return a UTC ISO-8601 string (with trailing Z) for a datetime or None."""
    if not dt:
        return None
    from app.utils.canonical_temporal_resolver import ensure_utc
    dt = ensure_utc(dt)
    return dt.isoformat().replace("+00:00", "Z")


def is_safe_url(target, host_url=None):
    """
    Ensure a redirect URL is safe by checking if it's on the same domain.
    
    Args:
        target: The URL to validate
        host_url: Optional host URL to validate against. If not provided, uses request.host_url
    """
    # Allow empty targets
    if not target:
        return True
    # Use provided host_url or fall back to request.host_url
    if host_url is None:
        host_url = request.host_url
    ref_url = urlparse(host_url)
    test_url = urlparse(urljoin(host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def render_markdown(text):
    """
    Convert Markdown text to sanitized HTML.

    Supports GitHub Flavored Markdown features including:
    - Headers, bold, italic, strikethrough
    - Lists (ordered and unordered)
    - Links and images
    - Code blocks and inline code
    - Tables
    - Blockquotes

    Args:
        text: Markdown formatted text string

    Returns:
        Markup object containing sanitized HTML (safe for rendering in templates)
    """
    if not text:
        return Markup('')

    # Configure markdown with GitHub Flavored Markdown extensions
    md = markdown.Markdown(extensions=[
        'extra',          # Tables, fenced code blocks, footnotes, abbreviations, attr_list, def_list
        'nl2br',          # Convert newlines to <br> tags
        'sane_lists',     # Better list handling
        'codehilite',     # Code syntax highlighting
        'tables',         # GitHub-style tables (redundant with extra, but explicit)
    ])

    # Convert markdown to HTML
    html = md.convert(text)

    # Define allowed HTML tags and attributes for sanitization
    allowed_tags = [
        'p', 'br', 'span', 'div',                          # Basic text
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',               # Headers
        'strong', 'em', 'u', 's', 'del', 'code', 'pre',   # Formatting
        'ul', 'ol', 'li',                                  # Lists
        'a',                                               # Links
        'img',                                             # Images
        'table', 'thead', 'tbody', 'tr', 'th', 'td',      # Tables
        'blockquote',                                      # Quotes
        'hr',                                              # Horizontal rule
    ]

    allowed_attributes = {
        'a': ['href', 'title', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],  # For syntax highlighting
        'pre': ['class'],   # For code blocks
        'th': ['align'],    # For table alignment
        'td': ['align'],    # For table alignment
    }

    allowed_protocols = ['http', 'https', 'mailto']

    # Sanitize HTML to prevent XSS attacks
    cleaner = bleach.Cleaner(
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=allowed_protocols,
        strip=True,
        strip_comments=True,
    )
    sanitized_html = cleaner.clean(html)

    # Return as Markup so Jinja2 doesn't double-escape it
    return Markup(sanitized_html)


def generate_anonymous_code(user_identifier: str) -> str:
    """Return an HMAC-based anonymous code for the given user identifier."""

    secret = current_app.config.get("USER_REPORT_SECRET") or current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("USER_REPORT_SECRET or SECRET_KEY must be configured for anonymous reporting")

    secret_bytes = secret if isinstance(secret, (bytes, bytearray)) else str(secret).encode()
    return hmac.new(secret_bytes, user_identifier.encode(), hashlib.sha256).hexdigest()
