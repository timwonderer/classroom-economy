"""Rent schedule producer — Rent lifecycle schedule intent → resolved instants.

This module is the boundary between two DIFFERENT LAYERS:

  1. Schedule INTENT lives on ``RentSettings`` (frequency, due day, grace period).
     It is mutable policy configuration; it says *when rent is meant to recur*.

  2. Resolved concrete INSTANTS live on ``BillCycle`` (``cycle_boundary_at``,
     ``next_assessment_at``, ``grace_boundary_at``). They are materialized ONCE at
     cycle creation and never re-derived, so a later settings change cannot
     retroactively move an already-materialized cycle's boundaries
     (INV-CORE-000 non-retroactivity).

The producer performs ALL calendar arithmetic in class-local *dates* (plain
``date`` math — calendar months, weeks, days). It uses the canonical temporal
resolver for ONE thing only: the lawful, DST-correct class-local-date → UTC
materialization. It never invents a "current time" for business decisions and
never converts timezones by hand.

Three boundaries are resolved per cycle, all as start-of-class-local-date UTC:

  - ``cycle_boundary_at``  = the cycle's own due date D
  - ``next_assessment_at`` = the SUCCESSOR cycle's due date D' (guaranteed > D)
  - ``grace_boundary_at``  = D + ``grace_period_days`` (late-penalty boundary)
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    ensure_utc,
    CLASS_LEVEL_EVALUATION,
)


@dataclass(frozen=True)
class ResolvedCycleSchedule:
    """The three resolved UTC boundaries for a single rent cycle."""
    due_local_date: date
    next_due_local_date: date
    cycle_boundary_at: datetime
    next_assessment_at: datetime
    grace_boundary_at: datetime | None


# --------------------------------------------------------------------------- #
# Class-local date <-> UTC materialization (resolver-backed; the ONLY temporal
# authority this module leans on).
# --------------------------------------------------------------------------- #

def local_date_of_instant(context, instant_utc: datetime) -> date:
    """Class-local (CLE) calendar date of a UTC instant."""
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="current_evaluation_day",
        reference_time_utc=ensure_utc(instant_utc),
    )
    return evaluation.evaluation_date


def current_local_date(context, reference_time_utc: datetime) -> date:
    """Class-local calendar date for 'now' (``reference_time_utc``)."""
    return local_date_of_instant(context, reference_time_utc)


def start_of_local_date_utc(context, local_date: date) -> datetime:
    """UTC instant at the START (00:00 class-local) of ``local_date``.

    DST-correct: the resolver localizes ``datetime.combine(D, time.min)`` in the
    class timezone before converting to UTC.
    """
    boundaries = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=context,
        primitive="evaluation_day_boundaries",
        evaluation_date=local_date,
    )
    return boundaries.boundary_start_utc


# --------------------------------------------------------------------------- #
# Pure calendar arithmetic on class-local dates.
# --------------------------------------------------------------------------- #

def _add_one_calendar_month(d: date) -> date:
    """Class-local calendar-month step, clamping the day to the target month end."""
    if d.month == 12:
        year, month = d.year + 1, 1
    else:
        year, month = d.year, d.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _add_calendar_months(d: date, months: int) -> date:
    result = d
    for _ in range(months):
        result = _add_one_calendar_month(result)
    return result


def _clamp_day_of_month(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def advance_due_date(settings, due_local_date: date) -> date:
    """Return the SUCCESSOR cycle's due local date, one period after ``due_local_date``.

    Frequency intent is read from RentSettings:
      - ``monthly``: +1 calendar month, re-anchored to ``due_day_of_month``.
      - ``weekly``:  +7 days.
      - ``daily``:   +1 day.
      - ``custom``:  ``custom_frequency_value`` × ``custom_frequency_unit``.
    """
    frequency = (settings.frequency_type or "monthly").strip().lower()

    if frequency == "daily":
        return due_local_date + timedelta(days=1)
    if frequency == "weekly":
        return due_local_date + timedelta(weeks=1)
    if frequency == "monthly":
        nxt = _add_one_calendar_month(due_local_date)
        # Re-anchor to the configured due day (clamped to the month end) so a
        # month-end clamp in one cycle does not permanently drift the day.
        anchor_day = settings.due_day_of_month or due_local_date.day
        return _clamp_day_of_month(nxt.year, nxt.month, anchor_day)
    if frequency == "custom":
        value = settings.custom_frequency_value
        unit = (settings.custom_frequency_unit or "days").strip().lower()
        if not value or value <= 0:
            raise ValueError("custom frequency requires a positive custom_frequency_value")
        if unit == "days":
            return due_local_date + timedelta(days=value)
        if unit == "weeks":
            return due_local_date + timedelta(weeks=value)
        if unit == "months":
            return _add_calendar_months(due_local_date, value)
        raise ValueError(f"unsupported custom_frequency_unit: {settings.custom_frequency_unit!r}")

    raise ValueError(f"unsupported frequency_type: {settings.frequency_type!r}")


def first_due_local_date(settings, *, context, reference_time_utc: datetime) -> date:
    """Class-local due date of the FIRST rent cycle (cycle_number == 1).

    If ``first_rent_due_date`` is configured, its class-local date is authoritative.
    Otherwise the first due date defaults to the current class-local date (the
    day reconciliation first materializes rent), anchored to ``due_day_of_month``
    for monthly frequency.
    """
    if settings.first_rent_due_date is not None:
        return local_date_of_instant(context, settings.first_rent_due_date)

    today = current_local_date(context, reference_time_utc)
    frequency = (settings.frequency_type or "monthly").strip().lower()
    if frequency == "monthly" and settings.due_day_of_month:
        return _clamp_day_of_month(today.year, today.month, settings.due_day_of_month)
    return today


# --------------------------------------------------------------------------- #
# The producer: resolve one cycle's three boundaries.
# --------------------------------------------------------------------------- #

def resolve_cycle_schedule(settings, *, due_local_date: date, context) -> ResolvedCycleSchedule:
    """Resolve the three concrete UTC boundaries for a cycle due on ``due_local_date``.

    All three are start-of-class-local-date UTC instants:
      - ``cycle_boundary_at``  = start of D
      - ``next_assessment_at`` = start of the successor due date D'  (D' > D ⇒ ordered)
      - ``grace_boundary_at``  = start of (D + grace_period_days), or None if no grace
    """
    next_due_local_date = advance_due_date(settings, due_local_date)

    cycle_boundary_at = start_of_local_date_utc(context, due_local_date)
    next_assessment_at = start_of_local_date_utc(context, next_due_local_date)

    grace_days = settings.grace_period_days
    if grace_days is None or grace_days < 0:
        grace_boundary_at = None
    else:
        grace_local_date = due_local_date + timedelta(days=grace_days)
        grace_boundary_at = start_of_local_date_utc(context, grace_local_date)

    return ResolvedCycleSchedule(
        due_local_date=due_local_date,
        next_due_local_date=next_due_local_date,
        cycle_boundary_at=cycle_boundary_at,
        next_assessment_at=next_assessment_at,
        grace_boundary_at=grace_boundary_at,
    )
