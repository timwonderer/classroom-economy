"""
Common utility functions for Classroom Economy application.

This module provides reusable helper functions for:
- Date/time formatting (ISO-8601 with UTC)
- URL safety validation for redirects
"""

from datetime import timezone
from urllib.parse import urlparse, urljoin
from flask import request


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
