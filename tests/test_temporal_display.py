"""Regression tests for portable temporal display formatting."""

from datetime import datetime, timezone

from app.utils.temporal_display import (
    format_compact_date,
    format_date,
    format_time,
    format_timestamp,
)


def test_temporal_formatters_are_portable_and_timezone_aware():
    """Display formatting avoids platform-specific strftime directives."""
    value = datetime(2026, 1, 3, 18, 5, tzinfo=timezone.utc)

    assert format_timestamp(value, "America/New_York") == "Jan 3, 2026, 1:05 PM EST"
    assert format_date(value, "America/New_York") == "Jan 3, 2026"
    assert format_compact_date(value, "America/New_York") == "Jan 3"
    assert format_time(value, "America/New_York") == "1:05 PM EST"