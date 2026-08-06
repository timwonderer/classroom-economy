"""Time utilities for the classroom economy application.

WARNING: THIS MODULE HAS BEEN DEPRECATED. DO NOT USE THIS IN LIVE CODE. IF YOU ARE READING THIS THAT MEANS YOU HAVE REVIVED A DEPRECATED MODULE BRUH. ONLY USE CANONICAL TEMPORAL RESOLVER. FOR MORE INFORMATION, PLEASE READ SPEC-TIME-001.

"""


from datetime import datetime, timezone, timedelta, MINYEAR, MAXYEAR
from typing import Optional, Tuple
import pytz

# UTC constants
UTC_MIN = datetime.min.replace(tzinfo=timezone.utc)
UTC_MAX = datetime.max.replace(tzinfo=timezone.utc)


def utc_now() -> datetime:
    """Return current time in UTC as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is in UTC timezone.

    If naive, assumes UTC. If aware but not UTC, converts to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime, assume UTC
        return dt.replace(tzinfo=timezone.utc)
    # Convert to UTC
    return dt.astimezone(timezone.utc)


def get_class_now(tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """Get current time in the specified timezone (or UTC if None)."""
    if tz is None:
        return utc_now()
    return datetime.now(tz)


def _get_class_timezone(class_id: str) -> pytz.BaseTzInfo:
    """Get timezone for a class (currently hardcoded to US/Central).

    TODO: Make this configurable per class.
    """
    return pytz.timezone('US/Central')


def to_class_time(dt: datetime, tz: pytz.BaseTzInfo) -> datetime:
    """Convert UTC datetime to class timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def day_bounds_utc(target_date: datetime) -> Tuple[datetime, datetime]:
    """Return start and end of day in UTC for the given date.

    Args:
        target_date: Any datetime (date part is used)

    Returns:
        Tuple of (start_of_day_utc, end_of_day_utc)
    """
    # Ensure we're working with UTC
    target_date = ensure_utc(target_date)

    # Start of day (00:00:00 UTC)
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # End of day (23:59:59.999999 UTC)
    end = start + timedelta(days=1) - timedelta(microseconds=1)

    return start, end


def get_class_cycle_start_utc(cycle_start_class_date: datetime, class_tz: pytz.BaseTzInfo) -> datetime:
    """Get UTC time for cycle start given a class-local date.

    Args:
        cycle_start_class_date: Date when cycle starts (in class timezone)
        class_tz: The class's timezone

    Returns:
        The UTC datetime for the start of that day in the class timezone
    """
    # Convert class date to class timezone aware datetime at midnight
    class_start = class_tz.localize(datetime.combine(cycle_start_class_date.date(), datetime.min.time()))

    # Convert to UTC
    return class_start.astimezone(timezone.utc)


def get_class_month_start_utc(month: int, year: int, class_tz: pytz.BaseTzInfo) -> datetime:
    """Get UTC time for start of month in class timezone.

    Args:
        month: Month (1-12)
        year: Year
        class_tz: The class's timezone

    Returns:
        UTC datetime for start of that month (00:00:00) in class timezone
    """
    # Create date at start of month
    month_start_date = datetime(year, month, 1)

    # Localize to class timezone
    month_start = class_tz.localize(datetime.combine(month_start_date.date(), datetime.min.time()))

    # Convert to UTC
    return month_start.astimezone(timezone.utc)


def normalize_for_db(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetime for database storage (ensure UTC timezone)."""
    if dt is None:
        return None
    return ensure_utc(dt)


def get_timezone(tz_name: str) -> pytz.BaseTzInfo:
    """Get timezone by name (e.g. 'US/Central')."""
    return pytz.timezone(tz_name)


def class_date(dt: datetime, class_tz: pytz.BaseTzInfo) -> datetime:
    """Get the date portion of a datetime in class timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    class_dt = dt.astimezone(class_tz)
    return class_dt.date()


def claim_period_bounds_utc(start_date: datetime, end_date: datetime) -> Tuple[datetime, datetime]:
    """Get UTC bounds for a claim period (inclusive)."""
    # Ensure dates are UTC
    start = ensure_utc(start_date)
    end = ensure_utc(end_date)

    # Start of start day
    start_bound = start.replace(hour=0, minute=0, second=0, microsecond=0)

    # End of end day
    end_bound = end.replace(hour=23, minute=59, second=59, microsecond=999999)

    return start_bound, end_bound


def get_class_week_range_utc(target_date: datetime, class_tz: pytz.BaseTzInfo) -> Tuple[datetime, datetime]:
    """Get UTC bounds for the week containing target_date.

    Week starts Monday, ends Sunday.
    """
    # Convert to class timezone
    if target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=timezone.utc)
    class_dt = target_date.astimezone(class_tz)

    # Find Monday of this week (weekday() returns 0 for Monday)
    days_since_monday = class_dt.weekday()
    monday = class_dt - timedelta(days=days_since_monday)

    # Find Sunday (6 days after Monday)
    sunday = monday + timedelta(days=6)

    # Localize to midnight in class timezone
    monday_midnight = class_tz.localize(datetime.combine(monday.date(), datetime.min.time()))
    sunday_midnight = class_tz.localize(datetime.combine(sunday.date(), datetime.min.time()))

    # Convert back to UTC
    monday_utc = monday_midnight.astimezone(timezone.utc)
    sunday_end_utc = sunday_midnight.astimezone(timezone.utc) + timedelta(days=1)

    return monday_utc, sunday_end_utc


def local_date_end_utc(target_date: datetime, tz: pytz.BaseTzInfo) -> datetime:
    """Get UTC time for end of day in local timezone."""
    # Ensure we have a date
    if hasattr(target_date, 'date'):
        date = target_date.date()
    else:
        date = target_date

    # Localize to end of day in local timezone
    end_of_day = tz.localize(datetime.combine(date, datetime.max.time()))

    # Convert to UTC
    return end_of_day.astimezone(timezone.utc)


def local_date_bounds_utc(target_date: datetime, tz: pytz.BaseTzInfo) -> Tuple[datetime, datetime]:
    """Get UTC bounds for a day in local timezone."""
    # Ensure we have a date
    if hasattr(target_date, 'date'):
        date = target_date.date()
    else:
        date = target_date

    # Get start and end of day in local timezone
    start_of_day = tz.localize(datetime.combine(date, datetime.min.time()))
    end_of_day = tz.localize(datetime.combine(date, datetime.max.time()))

    # Convert to UTC
    return start_of_day.astimezone(timezone.utc), end_of_day.astimezone(timezone.utc)
