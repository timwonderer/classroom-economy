from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.utils.time import (
    utc_now,
    ensure_utc,
    normalize_for_db,
    class_date,
    get_class_now,
    get_class_today_range,
    local_date_range_utc,
)
import sqlalchemy as sa
from flask import current_app
from app.extensions import db
import pytz
from app.services.attendance_service import (
    calculate_unpaid_attendance_seconds as _calculate_unpaid_attendance_seconds,
    get_all_block_statuses as _get_all_block_statuses,
)
from app.services.ledger_service import get_last_payroll_time as _get_last_payroll_time
from app.models import AttendanceReasonCode, AttendanceSession
from app.utils.canonical_temporal_resolver import CLASS_LEVEL_EVALUATION, canonical_temporal_resolver

def get_last_payroll_time(*, seat_id: int, class_id: str):
    """Return the latest payroll/manual payment anchor for one canonical seat/class scope."""
    if not seat_id or not class_id:
        raise ValueError("get_last_payroll_time requires seat_id and class_id.")
    return _get_last_payroll_time(seat_id=seat_id, class_id=class_id)



def calculate_unpaid_attendance_seconds(seat_id, class_id, last_payroll_time):
    """Calculate unpaid attendance seconds for one canonical seat/class scope."""
    if not seat_id or not class_id:
        raise ValueError("calculate_unpaid_attendance_seconds requires seat_id and class_id.")
    return _calculate_unpaid_attendance_seconds(
        seat_id,
        class_id,
        last_payroll_time,
    )


def calculate_period_attendance(seat_id, class_id, date):
    """
    Calculates total attendance seconds for a seat in a class
    on a specific date. Used for daily attendance reporting.
    NOTE: This uses UTC day boundaries.
    For class-timezone daily limits, use calculate_period_attendance_utc_range instead.
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_period_attendance requires seat_id and class_id.")

    # Build UTC range for the specified date
    start_utc = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    sessions = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.started_at < end_db,
        sa.or_(AttendanceSession.ended_at.is_(None), AttendanceSession.ended_at > start_db),
    ).all()

    total_seconds = 0
    now_utc = utc_now()
    for session in sessions:
        start_time = max(ensure_utc(session.started_at), start_utc)
        end_time = ensure_utc(session.ended_at) if session.ended_at else now_utc
        end_time = min(end_time, end_utc)
        if end_time > start_time:
            total_seconds += (end_time - start_time).total_seconds()
    return int(total_seconds)


def calculate_period_attendance_utc_range(seat_id, class_id, start_utc, end_utc):
    """
    Calculates total attendance seconds for a seat in a class
    within a UTC datetime range. Use this for timezone-aware daily limits.

    Args:
        seat_id: The seat's ID
        class_id: The class's ID
        start_utc: Start of range (UTC datetime, inclusive)
        end_utc: End of range (UTC datetime, exclusive)

    Returns:
        int: Total seconds of attendance in the range
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_period_attendance_utc_range requires seat_id and class_id.")

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    sessions = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.started_at < end_db,
        sa.or_(AttendanceSession.ended_at.is_(None), AttendanceSession.ended_at > start_db),
    ).all()

    total_seconds = 0
    now_utc = utc_now()
    for session in sessions:
        start_time = max(ensure_utc(session.started_at), start_utc)
        end_time = ensure_utc(session.ended_at) if session.ended_at else now_utc
        end_time = min(end_time, end_utc)
        if end_time > start_time:
            total_seconds += (end_time - start_time).total_seconds()
    return int(total_seconds)


def get_session_status(seat_id, class_id):
    """
    Gets the current session status for a seat in a class.
    Returns a tuple of (is_active, done, duration).
    """
    if not seat_id or not class_id:
        raise ValueError("get_session_status requires seat_id and class_id.")

    latest_event = (
        AttendanceSession.query.filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
        )
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )
    is_active = bool(latest_event and latest_event.status == "active")

    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="evaluation_day_boundaries",
    )
    done = (
        AttendanceSession.query.filter(
            AttendanceSession.target_seat_id == seat_id,
            AttendanceSession.class_id == class_id,
            AttendanceSession.status == "inactive",
            AttendanceSession.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value,
            AttendanceSession.timestamp >= day_bounds.boundary_start_utc,
            AttendanceSession.timestamp < day_bounds.boundary_end_utc,
        )
        .first()
        is not None
    )

    # Calculate unpaid duration
    last_payroll_time = get_last_payroll_time(seat_id=seat_id, class_id=class_id)
    duration = calculate_unpaid_attendance_seconds(seat_id, class_id, last_payroll_time)

    return is_active, done, duration


def get_all_block_statuses(student, *, class_id: str, ctx):
    """Return block statuses within one canonical class scope."""
    if not class_id:
        raise ValueError("get_all_block_statuses requires class_id.")
    return _get_all_block_statuses(student, class_id=class_id, ctx=ctx)

# -------------------------------------------------------------------
# BATCH OPTIMIZATION HELPERS
# -------------------------------------------------------------------

def get_batch_attendance_events(seat_ids, min_anchor, allowed_class_ids):
    """
    Fetch attendance transitions from canonical attendance sessions.
    Returns a dict: (seat_id, class_id) -> list of event-like rows
    with ``status`` and ``timestamp`` fields.

    SECURITY: ``allowed_class_ids`` is required to restrict results to explicit
    tenant-owned class scopes.
    """
    if not seat_ids:
        return {}
    if not allowed_class_ids:
        return {}

    min_anchor_utc = ensure_utc(min_anchor) if min_anchor else None
    query = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id.in_(seat_ids),
        AttendanceSession.class_id.in_(allowed_class_ids),
    )

    if min_anchor_utc:
        query = query.filter(
            sa.or_(
                AttendanceSession.started_at > min_anchor_utc,
                AttendanceSession.ended_at.is_(None),
                AttendanceSession.ended_at > min_anchor_utc,
            )
        )

    sessions = query.order_by(AttendanceSession.started_at.asc(), AttendanceSession.id.asc()).all()

    grouped = {}
    for session in sessions:
        start_time = ensure_utc(session.started_at)
        end_time = ensure_utc(session.ended_at) if session.ended_at else None

        if min_anchor_utc:
            if end_time is not None and end_time <= min_anchor_utc:
                continue
            active_at = max(start_time, min_anchor_utc)
        else:
            active_at = start_time

        key = (session.target_seat_id, session.class_id)
        grouped.setdefault(key, []).append(
            SimpleNamespace(
                seat_id=session.target_seat_id,
                class_id=session.class_id,
                status="active",
                timestamp=active_at,
            )
        )

        if end_time and (not min_anchor_utc or end_time > min_anchor_utc):
            grouped[key].append(
                SimpleNamespace(
                    seat_id=session.target_seat_id,
                    class_id=session.class_id,
                    status="inactive",
                    timestamp=end_time,
                )
            )

    for events in grouped.values():
        events.sort(key=lambda event: (ensure_utc(event.timestamp), 0 if event.status == "active" else 1))

    return grouped

def calculate_seconds_in_memory(events, anchor):
    """
    Calculate unpaid seconds from a sorted list of events, strictly after anchor.
    """
    total_seconds = 0
    in_time = None

    anchor = ensure_utc(anchor)

    for event in events:
        event_time = ensure_utc(event.timestamp)

        # Skip events before specific anchor
        if anchor and event_time <= anchor:
            # If active, it effectively sets in_time for subsequent period
            if event.status == 'active':
                in_time = event_time
            else:
                in_time = None
            continue

        # If we crossed the anchor boundary and in_time was set from a pre-anchor event
        if in_time and in_time < anchor:
            in_time = anchor

        if event.status == 'active':
            if in_time is None:
                in_time = event_time
        elif event.status == 'inactive' and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    # If still active at "now"
    if in_time:
        if anchor and in_time < anchor:
            in_time = anchor

        now = utc_now()
        total_seconds += (now - in_time).total_seconds()

    return int(total_seconds)
