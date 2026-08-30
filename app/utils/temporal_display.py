"""
SPEC-TIME-001 / MAP-UI-002 compliant display formatting for timestamps.

Display timezone authority comes from the Temporal Context layer:
  - In templates: injected as `display_timezone` by the context processor
  - In API routes: resolved via `resolve_display_timezone(ctx)`

Core functions (plain Python, usable anywhere):
    format_timestamp  — "Dec 3, 2025, 2:30 PM PST"
    format_date       — "Dec 3, 2025"
    format_compact_date — "Dec 3"
    format_time       — "2:30 PM PST"
    resolve_display_timezone — resolve from CanonicalContext

Jinja filters (registered via register_temporal_filters):
    fmt_timestamp, fmt_date, fmt_compact_date, fmt_time
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytz
from jinja2 import pass_context
from markupsafe import Markup


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _localize(dt: datetime, tz_name: str) -> datetime:
    tz = pytz.timezone(tz_name)
    return _ensure_aware(dt).astimezone(tz)


def _tz_abbrev(dt_local: datetime) -> str:
    abbrev = dt_local.strftime("%Z")
    return abbrev if abbrev else ""


def _format_month_day(dt_local: datetime) -> str:
    return f"{dt_local.strftime('%b')} {dt_local.day}"


def _format_clock_time(dt_local: datetime) -> str:
    return dt_local.strftime("%I:%M %p").lstrip("0")


# ---------------------------------------------------------------------------
# Temporal Context resolver (for API routes)
# ---------------------------------------------------------------------------

def resolve_display_timezone(ctx) -> str:
    """Resolve display timezone from a CanonicalContext. Returns IANA tz name or 'UTC'."""
    class_id = getattr(ctx, "class_id", None) if ctx else None
    if not class_id:
        return "UTC"
    from app.models import ClassEconomy
    from app.extensions import db
    economy = db.session.get(ClassEconomy, class_id)
    if economy and economy.class_timezone:
        return economy.class_timezone
    return "UTC"


# ---------------------------------------------------------------------------
# Core formatting functions (plain Python, no Jinja dependency)
# ---------------------------------------------------------------------------

def format_timestamp(dt, tz_name: str = "UTC") -> str:
    if not dt:
        return "—"
    local = _localize(dt, tz_name)
    formatted = f"{_format_month_day(local)}, {local.year}, {_format_clock_time(local)}"
    abbrev = _tz_abbrev(local)
    return f"{formatted} {abbrev}".strip()


def format_date(dt, tz_name: str = "UTC") -> str:
    if not dt:
        return "—"
    local = _localize(dt, tz_name)
    return f"{_format_month_day(local)}, {local.year}"


def format_compact_date(dt, tz_name: str = "UTC") -> str:
    if not dt:
        return "—"
    local = _localize(dt, tz_name)
    return _format_month_day(local)


def format_time(dt, tz_name: str = "UTC") -> str:
    if not dt:
        return "—"
    local = _localize(dt, tz_name)
    formatted = _format_clock_time(local)
    abbrev = _tz_abbrev(local)
    return f"{formatted} {abbrev}".strip()


# ---------------------------------------------------------------------------
# Jinja2 filters (delegate to core functions, read tz from template context)
# ---------------------------------------------------------------------------

@pass_context
def fmt_timestamp(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_timestamp(dt, ctx.get("display_timezone", "UTC"))


@pass_context
def fmt_date(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_date(dt, ctx.get("display_timezone", "UTC"))


@pass_context
def fmt_compact_date(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_compact_date(dt, ctx.get("display_timezone", "UTC"))


@pass_context
def fmt_time(ctx, dt):
    if not dt:
        return Markup("&mdash;")
    return format_time(dt, ctx.get("display_timezone", "UTC"))


def register_temporal_filters(app):
    app.jinja_env.filters["fmt_timestamp"] = fmt_timestamp
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["fmt_compact_date"] = fmt_compact_date
    app.jinja_env.filters["fmt_time"] = fmt_time
