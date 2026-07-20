from __future__ import annotations

from app.models import (
    AttendanceSession,
    HallPassLog,
    
    Seat,
)
from app.utils.time import ensure_utc, get_class_now


def _calculate_unpaid_from_sessions(session_rows, now_utc, last_payroll_time):
    last_anchor = ensure_utc(last_payroll_time) if last_payroll_time else None
    total_seconds = 0
    for session in session_rows:
        start = ensure_utc(session.started_at)
        end = ensure_utc(session.ended_at) if session.ended_at else now_utc
        if end < start:
            end = start
        if last_anchor:
            if end <= last_anchor:
                continue
            start = max(start, last_anchor)
        if end > start:
            total_seconds += (end - start).total_seconds()
    return int(max(0, total_seconds))


def calculate_unpaid_attendance_seconds(seat_id: int, class_id: str, last_payroll_time):
    """Calculate unpaid attendance from a caller-supplied payroll anchor."""
    now_utc = get_class_now(class_id)
    canonical_rows = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    ).order_by(AttendanceSession.started_at.asc()).all()
    return _calculate_unpaid_from_sessions(canonical_rows, now_utc, last_payroll_time)


def get_all_block_statuses(student, *, class_id: str, payroll_anchor_by_class_id=None):
    """Return attendance facts for one canonical class scope only."""
    if not class_id:
        raise ValueError("get_all_block_statuses requires class_id.")

    student_user_id = getattr(student, "user_id", None)
    if student_user_id is None:
        student_user_id = getattr(student, "id", None)

    claimed_seats = Seat.query.filter(
        Seat.user_id == student_user_id,
        Seat.class_id == class_id,
        Seat.role == 'student',
        Seat.claimed_at.isnot(None),
    ).all()
    student_blocks = [seat.class_economy.section.strip() for seat in claimed_seats if seat.class_economy and seat.class_economy.section]

    period_states = {}
    payroll_anchor_by_class_id = payroll_anchor_by_class_id or {}

    for block_original in student_blocks:
        blk = block_original.upper()
        seat = next((row for row in claimed_seats if row.class_economy and (row.class_economy.section or "").strip().upper() == blk), None)
        if not seat:
            continue
        seat_id = seat.id

        state = SeatAttendanceState.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
        ).first()
        is_active = state.is_active if state else False

        today_local = get_class_now(class_id).date()
        done = False
        if state and state.done_for_day_date == today_local:
            done = True
        duration = calculate_unpaid_attendance_seconds(
            seat_id,
            class_id,
            payroll_anchor_by_class_id.get(class_id),
        )

        active_pass = HallPassLog.query.filter_by(
            requested_by_seat_id=seat_id,
            class_id=class_id,
        ).filter(
            HallPassLog.status.in_(["pending", "approved", "left", "rejected"])
        ).order_by(HallPassLog.request_time.desc()).first()

        hall_pass = None
        if active_pass:
            hall_pass = {"id": active_pass.id, "status": active_pass.status, "reason": active_pass.reason}

        period_states[blk] = {
            "active": is_active,
            "done": done,
            "duration": duration,
            "projected_pay": None,
            "hall_pass": hall_pass,
        }

    return period_states
