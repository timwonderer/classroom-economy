"""
Common utility functions for Classroom Economy application.

This module provides reusable helper functions for:
- Date/time formatting (ISO-8601 with UTC)
- URL safety validation for redirects
- Markdown to HTML conversion with sanitization
"""

from datetime import timezone
from urllib.parse import urlparse, urljoin
import hashlib
import hmac
from flask import request, current_app
from markupsafe import Markup
import markdown
import bleach


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
    sanitized_html = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=allowed_protocols,
        strip=True
    )

    # Return as Markup so Jinja2 doesn't double-escape it
    return Markup(sanitized_html)


def generate_anonymous_code(user_identifier: str) -> str:
    """Return an HMAC-based anonymous code for the given user identifier."""

    secret = current_app.config.get("USER_REPORT_SECRET") or current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("USER_REPORT_SECRET or SECRET_KEY must be configured for anonymous reporting")

    secret_bytes = secret if isinstance(secret, (bytes, bytearray)) else str(secret).encode()
    return hmac.new(secret_bytes, user_identifier.encode(), hashlib.sha256).hexdigest()
