"""Regression: an unclosed `active` attendance session must not accrue time
across a day boundary.

DOM-PROD-001 §312: "Any ``active`` sessions SHALL automatically terminate by end
of day at canonical class timezone with the ``reason_code = done_for_day``.
Timestamp for the ``inactive`` entry SHALL be recorded using the same date as the
originating ``active`` entry."

The old ``_calculate_attendance_seconds_since`` extended any trailing open
``active`` interval to ``current_time_utc`` unconditionally. A student who tapped
in and never tapped out would keep accruing payable seconds overnight and across
subsequent days -- so a payroll run the next day paid for hours the student was
never present. The fix caps the open interval at the end-of-day boundary of the
canonical class-local day on which the ``active`` entry was recorded.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.feats.prod import _calculate_attendance_seconds_since, record_attendance_session
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)
from app.services.context_resolver import CanonicalContext
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def test_DOM_PROD_001__open_active_session_caps_at_end_of_day(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    ctx = _student_ctx(classroom, student)

    # Student taps in mid-day (11:00 PDT = 18:00 UTC on 2026-08-26) and never
    # taps out.
    active_start = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key=f"test:attn:active:{ctx.seat_id}:{active_start.isoformat()}",
        reference_time_utc=active_start,
    )

    # Payroll evaluates the NEXT day.
    current_time = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)

    seconds = _calculate_attendance_seconds_since(
        ctx=ctx,
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        since_utc=None,
        current_time_utc=current_time,
    )

    # Expected: capped at end-of-day of the active entry's canonical class day,
    # derived through the same canonical resolver production uses.
    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=active_start,
    )
    expected = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="elapsed_duration",
        reference_time_utc=current_time,
        intervals=[(active_start, day_bounds.boundary_end_utc)],
    ).elapsed_seconds

    assert seconds == expected
    # And crucially NOT the naive overnight span to current_time (~24h).
    naive_full = int((current_time - active_start).total_seconds())
    assert seconds < naive_full


def test_DOM_PROD_001__later_day_tap_in_closes_prior_session_at_its_own_day_end(client):
    """A tap-in on a later day auto-closes the prior open session at THAT prior
    day's end-of-day (DOM-PROD-001 §312), not carried forward to today."""
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    student = classroom.students[0]
    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    ctx = _student_ctx(classroom, student)

    # Day 1: tap in at 11:00 PDT (18:00 UTC), never tap out.
    day1_active = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key=f"test:attn:d1:{ctx.seat_id}",
        reference_time_utc=day1_active,
    )

    # Day 2: tap in again -> the prior open session must auto-close.
    day2_active = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key=f"test:attn:d2:{ctx.seat_id}",
        reference_time_utc=day2_active,
    )

    # The auto-close inactive row is dated to day 1's end-of-day, not day 2.
    from app.models import AttendanceReasonCode, AttendanceSession

    close_row = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == student.seat.id,
        AttendanceSession.class_id == classroom.class_id,
        AttendanceSession.status == "inactive",
        AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
    ).order_by(AttendanceSession.timestamp.asc()).first()
    assert close_row is not None

    day1_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=day1_active,
    )
    close_ts = close_row.timestamp
    if close_ts.tzinfo is None:
        close_ts = close_ts.replace(tzinfo=timezone.utc)
    assert close_ts == day1_bounds.boundary_end_utc
    # Not carried forward to the day-2 tap-in time.
    assert close_ts < day2_active

    # Payroll evaluated on day 2 pays only day-1's bounded span, never overnight.
    seconds = _calculate_attendance_seconds_since(
        ctx=ctx,
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        since_utc=None,
        current_time_utc=datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc),
    )
    # Day 1 bounded span (18:00 UTC -> day1 end) + day 2 span (18:00 -> 19:00 UTC).
    day1_expected = int((day1_bounds.boundary_end_utc - day1_active).total_seconds())
    day2_expected = 3600
    assert seconds == day1_expected + day2_expected
