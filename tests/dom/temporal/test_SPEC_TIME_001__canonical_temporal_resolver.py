"""
Tests for SPEC-TIME-001: Canonical Temporal Resolver.

Covers the required assertions from §XIV of the spec.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytz

from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    CanonicalTemporalEvaluation,
    TemporalResolutionError,
    canonical_temporal_resolver,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


class FakeContext:
    def __init__(self, class_id):
        self.class_id = class_id


EASTERN = "America/New_York"
PACIFIC = "America/Los_Angeles"
REF = _utc(2026, 7, 20, 18, 30, 0)  # 18:30 UTC


@pytest.fixture(autouse=True)
def _patch_class_timezone():
    """All CLE tests use America/New_York unless overridden."""
    with patch(
        "app.utils.canonical_temporal_resolver.get_class_timezone",
        return_value=EASTERN,
    ):
        yield


# ---------------------------------------------------------------------------
# §XIV-1: SLE resolves to UTC
# ---------------------------------------------------------------------------

def test_sle_resolves_to_utc():
    ev = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
        reference_time_utc=REF,
    )
    assert ev.temporal_authority == "UTC"
    assert ev.class_id is None


# ---------------------------------------------------------------------------
# §XIV-2: CLE resolves to Canonical Class Timezone
# ---------------------------------------------------------------------------

def test_cle_resolves_to_class_timezone():
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="current_time",
        reference_time_utc=REF,
    )
    assert ev.temporal_authority == EASTERN
    assert ev.class_id == "cls-1"


# ---------------------------------------------------------------------------
# §XIV-3: CLE fails closed without class context
# ---------------------------------------------------------------------------

def test_cle_fails_without_context():
    with pytest.raises(TemporalResolutionError, match="class_id"):
        canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            primitive="current_time",
            reference_time_utc=REF,
        )


# ---------------------------------------------------------------------------
# §XIV-4: CLE fails closed when class timezone cannot be established
# ---------------------------------------------------------------------------

def test_cle_fails_with_unknown_timezone():
    with patch(
        "app.utils.canonical_temporal_resolver.get_class_timezone",
        return_value="Invalid/Zone",
    ):
        with pytest.raises(TemporalResolutionError, match="Unknown IANA"):
            canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=FakeContext("cls-bad"),
                primitive="current_time",
                reference_time_utc=REF,
            )


# ---------------------------------------------------------------------------
# §XIV-5: current_time returns UTC and authority-local forms
# ---------------------------------------------------------------------------

def test_current_time_returns_both_forms():
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="current_time",
        reference_time_utc=REF,
    )
    assert ev.canonical_now_utc == REF
    eastern_tz = pytz.timezone(EASTERN)
    expected_local = REF.astimezone(eastern_tz)
    assert ev.canonical_now == expected_local


# ---------------------------------------------------------------------------
# §XIV-6: earlier_than / later_than normalize through authority
# ---------------------------------------------------------------------------

def test_earlier_than_normalizes():
    t1 = _utc(2026, 7, 20, 10, 0, 0)
    t2 = _utc(2026, 7, 20, 11, 0, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="earlier_than",
        reference_time_utc=REF,
        candidate=t1,
        reference=t2,
    )
    assert ev.is_earlier is True


def test_later_than_normalizes():
    t1 = _utc(2026, 7, 20, 12, 0, 0)
    t2 = _utc(2026, 7, 20, 11, 0, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="later_than",
        reference_time_utc=REF,
        candidate=t1,
        reference=t2,
    )
    assert ev.is_later is True


# ---------------------------------------------------------------------------
# §XIV-7: between_boundaries uses inclusive-start / exclusive-end
# ---------------------------------------------------------------------------

def test_between_boundaries_inclusive_start_exclusive_end():
    start = _utc(2026, 7, 20, 8, 0, 0)
    end = _utc(2026, 7, 20, 17, 0, 0)

    # Exactly at start — included
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="between_boundaries",
        reference_time_utc=REF,
        candidate=start,
        start_boundary=start,
        end_boundary=end,
    )
    assert ev.is_between is True

    # Exactly at end — excluded
    ev2 = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="between_boundaries",
        reference_time_utc=REF,
        candidate=end,
        start_boundary=start,
        end_boundary=end,
    )
    assert ev2.is_between is False


# ---------------------------------------------------------------------------
# §XIV-8: time_since returns exact elapsed seconds
# ---------------------------------------------------------------------------

def test_time_since_exact_seconds():
    start = _utc(2026, 7, 20, 18, 0, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="time_since",
        reference_time_utc=REF,
        start=start,
    )
    assert ev.elapsed_seconds == 1800  # 30 minutes


# ---------------------------------------------------------------------------
# §XIV-9: time_until returns exact remaining seconds
# ---------------------------------------------------------------------------

def test_time_until_exact_seconds():
    target = _utc(2026, 7, 20, 19, 0, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="time_until",
        reference_time_utc=REF,
        target=target,
    )
    assert ev.remaining_seconds == 1800


# ---------------------------------------------------------------------------
# §XIV-10: current_evaluation_day derives class-local day for CLE
# ---------------------------------------------------------------------------

def test_current_evaluation_day_class_local():
    # 2026-07-20 18:30 UTC = 2026-07-20 14:30 Eastern (same day)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="current_evaluation_day",
        reference_time_utc=REF,
    )
    assert ev.evaluation_date == date(2026, 7, 20)

    # Use a time that crosses the day boundary:
    # 2026-07-21 02:00 UTC = 2026-07-20 22:00 Eastern (previous day)
    late_utc = _utc(2026, 7, 21, 2, 0, 0)
    ev2 = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="current_evaluation_day",
        reference_time_utc=late_utc,
    )
    assert ev2.evaluation_date == date(2026, 7, 20)


# ---------------------------------------------------------------------------
# §XIV-11: evaluation_day_boundaries returns authority-local and UTC
# ---------------------------------------------------------------------------

def test_evaluation_day_boundaries():
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="evaluation_day_boundaries",
        reference_time_utc=REF,
        evaluation_date=date(2026, 7, 20),
    )
    eastern_tz = pytz.timezone(EASTERN)
    expected_start = eastern_tz.localize(datetime(2026, 7, 20, 0, 0, 0))
    expected_end = expected_start + timedelta(days=1)

    assert ev.boundary_start == expected_start
    assert ev.boundary_end == expected_end
    assert ev.boundary_start_utc == expected_start.astimezone(timezone.utc)
    assert ev.boundary_end_utc == expected_end.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# §XIV-12: elapsed_duration sums one interval
# ---------------------------------------------------------------------------

def test_elapsed_duration_single_interval():
    s = _utc(2026, 7, 20, 8, 0, 0)
    e = _utc(2026, 7, 20, 8, 20, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="elapsed_duration",
        reference_time_utc=REF,
        intervals=[(s, e)],
    )
    assert ev.elapsed_seconds == 1200


# ---------------------------------------------------------------------------
# §XIV-13: elapsed_duration sums multiple discontinuous intervals
# ---------------------------------------------------------------------------

def test_elapsed_duration_multiple_intervals():
    intervals = [
        (_utc(2026, 7, 20, 8, 0, 0), _utc(2026, 7, 20, 8, 20, 0)),   # 1200s
        (_utc(2026, 7, 20, 8, 30, 0), _utc(2026, 7, 20, 9, 0, 22)),   # 1822s
    ]
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="elapsed_duration",
        reference_time_utc=REF,
        intervals=intervals,
    )
    assert ev.elapsed_seconds == 3022


# ---------------------------------------------------------------------------
# §XIV-14: elapsed_duration rejects end-before-start
# ---------------------------------------------------------------------------

def test_elapsed_duration_rejects_end_before_start():
    intervals = [
        (_utc(2026, 7, 20, 9, 0, 0), _utc(2026, 7, 20, 8, 0, 0)),
    ]
    with pytest.raises(TemporalResolutionError, match="end before start"):
        canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=FakeContext("cls-1"),
            primitive="elapsed_duration",
            reference_time_utc=REF,
            intervals=intervals,
        )


# ---------------------------------------------------------------------------
# §XIV-15: elapsed_duration rejects overlapping intervals
# ---------------------------------------------------------------------------

def test_elapsed_duration_rejects_overlapping():
    intervals = [
        (_utc(2026, 7, 20, 8, 0, 0), _utc(2026, 7, 20, 8, 30, 0)),
        (_utc(2026, 7, 20, 8, 20, 0), _utc(2026, 7, 20, 9, 0, 0)),
    ]
    with pytest.raises(TemporalResolutionError, match="Overlapping"):
        canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=FakeContext("cls-1"),
            primitive="elapsed_duration",
            reference_time_utc=REF,
            intervals=intervals,
        )


# ---------------------------------------------------------------------------
# §XIV-16: shift_timestamp returns authority-local and UTC forms
# ---------------------------------------------------------------------------

def test_shift_timestamp_returns_local_and_utc_forms():
    timestamp = _utc(2026, 7, 20, 13, 15, 0)
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="shift_timestamp",
        reference_time_utc=REF,
        timestamp=timestamp,
        elapsed_seconds=90,
    )

    assert ev.shifted_timestamp.tzinfo.zone == EASTERN
    assert ev.shifted_timestamp_utc == _utc(2026, 7, 20, 13, 16, 30)


# ---------------------------------------------------------------------------
# §XIV-18: Payroll-style rounding is NOT performed
# ---------------------------------------------------------------------------

def test_no_payroll_rounding():
    intervals = [
        (_utc(2026, 7, 20, 8, 0, 0), _utc(2026, 7, 20, 8, 0, 37)),
    ]
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="elapsed_duration",
        reference_time_utc=REF,
        intervals=intervals,
    )
    assert ev.elapsed_seconds == 37  # exact, no rounding


# ---------------------------------------------------------------------------
# §XIV-17: Browser display timezone is UTC for SLE
# ---------------------------------------------------------------------------

def test_display_timezone_utc_for_sle():
    ev = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
        reference_time_utc=REF,
    )
    assert ev.display_timezone == "UTC"


# ---------------------------------------------------------------------------
# §XIV-18: Browser display timezone is class timezone for CLE
# ---------------------------------------------------------------------------

def test_display_timezone_class_for_cle():
    ev = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=FakeContext("cls-1"),
        primitive="current_time",
        reference_time_utc=REF,
    )
    assert ev.display_timezone == EASTERN


# ---------------------------------------------------------------------------
# Additional fail-closed tests
# ---------------------------------------------------------------------------

def test_naive_timestamp_rejected():
    naive = datetime(2026, 7, 20, 12, 0, 0)
    with pytest.raises(TemporalResolutionError, match="Naive"):
        canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="time_since",
            reference_time_utc=REF,
            start=naive,
        )


def test_unknown_primitive_rejected():
    with pytest.raises(TemporalResolutionError, match="Unknown primitive"):
        canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="payroll_round",
            reference_time_utc=REF,
        )


def test_unknown_evaluation_type_rejected():
    with pytest.raises(TemporalResolutionError, match="Unknown evaluation type"):
        canonical_temporal_resolver(
            "INVALID",
            primitive="current_time",
            reference_time_utc=REF,
        )


def test_time_since_negative_fails_closed():
    future = _utc(2026, 7, 20, 19, 0, 0)
    with pytest.raises(TemporalResolutionError, match="Negative elapsed"):
        canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="time_since",
            reference_time_utc=REF,
            start=future,
        )


def test_time_until_negative_fails_closed():
    past = _utc(2026, 7, 20, 17, 0, 0)
    with pytest.raises(TemporalResolutionError, match="Negative remaining"):
        canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="time_until",
            reference_time_utc=REF,
            target=past,
        )


def test_empty_intervals_fails_closed():
    with pytest.raises(TemporalResolutionError, match="Empty interval"):
        canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="elapsed_duration",
            reference_time_utc=REF,
            intervals=[],
        )
