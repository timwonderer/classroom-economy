from __future__ import annotations

from app.extensions import db
from app.models import (
    AttendanceReasonCode,
    AttendanceSession,
    HallPassLog,
    Seat,
)
from app.services.hall_pass_request_queue import list_pending_hall_pass_requests_for_class
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
    ensure_utc,
)


def get_attendance_session_counts_by_seat(
    class_id: str, window_start, window_end
) -> dict[int, int]:
    """Map ``target_seat_id`` → count of attendance sessions in ``[start, end)``.

    Read-only DOM-PROD-001 surface consumed by the Interpretation domain
    (SPEC-ITR-001 §5.3). ``AttendanceSession`` is the authoritative participation
    fact; Ledger is never consulted for participation (INV-ITR-016). Only seats
    with ≥1 session appear in the mapping — the caller supplies the enrolled
    population and treats absent seats as zero. Scoped by ``class_id`` and the
    half-open completed-cycle window.
    """
    if not class_id or window_start is None or window_end is None:
        return {}
    rows = (
        AttendanceSession.query
        .with_entities(
            AttendanceSession.target_seat_id,
            db.func.count(AttendanceSession.id),
        )
        .filter(
            AttendanceSession.class_id == class_id,
            AttendanceSession.timestamp >= ensure_utc(window_start),
            AttendanceSession.timestamp < ensure_utc(window_end),
        )
        .group_by(AttendanceSession.target_seat_id)
        .all()
    )
    return {seat_id: int(count) for seat_id, count in rows if seat_id is not None}


def _current_evaluation_day_bounds(ctx):
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
    )
    return evaluation.boundary_start_utc, evaluation.boundary_end_utc


def _current_evaluation_day_bounds_for_date(ctx, evaluation_date):
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        evaluation_date=evaluation_date,
    )
    return evaluation.boundary_start_utc, evaluation.boundary_end_utc


def _elapsed_seconds(ctx, intervals):
    if not intervals:
        return 0
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="elapsed_duration",
        intervals=intervals,
    )
    return evaluation.elapsed_seconds


def _pair_active_intervals(rows, *, end_boundary, start_boundary=None):
    intervals = []
    active_start = None
    for row in rows:
        timestamp = row.timestamp
        if row.status == "active":
            active_start = timestamp
            continue
        if row.status == "inactive" and active_start is not None:
            interval_start = active_start
            interval_end = timestamp
            if start_boundary and interval_end <= start_boundary:
                active_start = None
                continue
            if start_boundary and interval_start < start_boundary:
                interval_start = start_boundary
            if interval_end > end_boundary:
                interval_end = end_boundary
            if interval_end >= interval_start:
                intervals.append((interval_start, interval_end))
            active_start = None
    if active_start is not None:
        interval_start = active_start
        interval_end = end_boundary
        if start_boundary and interval_start < start_boundary:
            interval_start = start_boundary
        if interval_end >= interval_start:
            intervals.append((interval_start, interval_end))
    return intervals


def _derive_hall_pass_state(seat_id: int, class_id: str):
    """Return the latest non-returned hall-pass display state for a seat/class."""
    pending_requests = [
        request for request in list_pending_hall_pass_requests_for_class(class_id)
        if request.requested_by_seat_id == seat_id
    ]
    if pending_requests:
        latest_pending = pending_requests[-1]
        return {
            "id": latest_pending.request_id,
            "status": "pending",
            "reason": latest_pending.destination,
        }

    latest_pass = HallPassLog.query.filter_by(
        requested_by_seat_id=seat_id,
        class_id=class_id,
    ).order_by(HallPassLog.timestamp.desc(), HallPassLog.id.desc()).first()
    if latest_pass is None:
        return None

    rows = AttendanceSession.query.filter_by(
        target_seat_id=seat_id,
        class_id=class_id,
        hall_pass_id=latest_pass.hall_pass_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    left_row = next(
        (
            row for row in rows
            if row.status == "inactive"
            and row.reason_code == AttendanceReasonCode.HALL_PASS.value
        ),
        None,
    )
    return_row = next(
        (
            row for row in rows
            if left_row is not None
            and row.status == "active"
            and row.timestamp >= left_row.timestamp
        ),
        None,
    )
    if return_row is not None:
        return None
    status = "left" if left_row is not None else "approved"
    return {
        "id": latest_pass.id,
        "status": status,
        "reason": latest_pass.destination,
    }


def calculate_unpaid_attendance_seconds(seat_id: int, class_id: str, last_payroll_time, *, ctx):
    """Calculate unpaid attendance from a caller-supplied payroll anchor."""
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    intervals = _pair_active_intervals(
        canonical_rows,
        start_boundary=last_payroll_time,
        end_boundary=now_evaluation.canonical_now_utc,
    )
    return _elapsed_seconds(ctx, intervals)


def calculate_worked_attendance_seconds_for_date(seat_id: int, class_id: str, evaluation_date, *, ctx):
    """Return authoritative worked seconds for one class-local date.

    PRODUCTIVITY consumers receive a duration only; they never interpret
    AttendanceSession rows or reason codes. Still-active sessions are clipped
    at the canonical now so a claim cannot count time that has not elapsed.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds_for_date(ctx, evaluation_date)
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    end_boundary = min(day_end_utc, now_evaluation.canonical_now_utc)
    if end_boundary <= day_start_utc:
        return 0
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    intervals = _pair_active_intervals(
        canonical_rows,
        start_boundary=day_start_utc,
        end_boundary=end_boundary,
    )
    return _elapsed_seconds(ctx, intervals)


def calculate_worked_attendance_seconds_today(seat_id: int, class_id: str, *, ctx):
    """Return authoritative worked seconds for the CURRENT class-local day.

    Same day-bounded, now-clipped semantics as
    ``calculate_worked_attendance_seconds_for_date`` but anchored to the class's
    current evaluation day. This is the value the student UI labels "Time Today";
    it must never be the unbounded unpaid-since-payroll figure, which can span
    many days when payroll has not run.
    """
    day_start_utc, day_end_utc = _current_evaluation_day_bounds(ctx)
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    end_boundary = min(day_end_utc, now_evaluation.canonical_now_utc)
    if end_boundary <= day_start_utc:
        return 0
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    intervals = _pair_active_intervals(
        canonical_rows,
        start_boundary=day_start_utc,
        end_boundary=end_boundary,
    )
    return _elapsed_seconds(ctx, intervals)


def get_class_attendance_status(student, *, class_id: str, payroll_anchor_utc=None, ctx=None):
    """Return PROD attendance facts for one canonical class scope."""
    if not class_id:
        raise ValueError("get_class_attendance_status requires class_id.")
    if ctx is None:
        raise ValueError("get_class_attendance_status requires CanonicalContext.")

    seat_id = getattr(ctx, "seat_id", None) or getattr(student, "id", None)
    if not seat_id:
        raise ValueError("get_class_attendance_status requires seat_id.")

    seat = Seat.query.filter(
        Seat.id == seat_id,
        Seat.class_id == class_id,
        Seat.role == 'student',
        Seat.claimed_at.isnot(None),
    ).first()
    if seat is None:
        raise ValueError("Seat is not claimed in the requested class scope.")

    rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat.id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()
    latest = rows[-1] if rows else None
    is_active = bool(latest and latest.status == "active")

    day_start_utc, day_end_utc = _current_evaluation_day_bounds(ctx)
    done = any(
        row.status == "inactive"
        and row.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value
        and day_start_utc <= row.timestamp < day_end_utc
        for row in rows
    )
    duration = calculate_unpaid_attendance_seconds(
        seat.id,
        class_id,
        payroll_anchor_utc,
        ctx=ctx,
    )
    # "Time Today" must be the day-bounded worked figure, not the unbounded
    # unpaid-since-payroll duration (which can span days if payroll has not run).
    duration_today = calculate_worked_attendance_seconds_today(
        seat.id, class_id, ctx=ctx
    )

    return {
        "active": is_active,
        "done": done,
        "duration": duration,
        "duration_today": duration_today,
        "projected_pay": None,
        "hall_pass": _derive_hall_pass_state(seat.id, class_id),
    }
