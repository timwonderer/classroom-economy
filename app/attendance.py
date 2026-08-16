from types import SimpleNamespace
from app.services.attendance_service import (
    calculate_unpaid_attendance_seconds as _calculate_unpaid_attendance_seconds,
)
from app.models import AttendanceReasonCode, AttendanceSession, PayrollEvent
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


def _ensure_utc_timestamp(timestamp):
    if timestamp is None:
        return None
    evaluation = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
        reference_time_utc=timestamp,
    )
    return evaluation.canonical_now_utc

def get_last_payroll_time(*, seat_id: int, class_id: str):
    """Return the latest payroll settlement anchor for one canonical seat/class scope."""
    if not seat_id or not class_id:
        raise ValueError("get_last_payroll_time requires seat_id and class_id.")
    last_payroll = (
        PayrollEvent.query.filter(
            PayrollEvent.target_seat_id == seat_id,
            PayrollEvent.class_id == class_id,
            PayrollEvent.payroll_event_type == "payroll",
        )
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .first()
    )
    return _ensure_utc_timestamp(last_payroll.recorded_at) if last_payroll else None



def calculate_unpaid_attendance_seconds(seat_id, class_id, last_payroll_time):
    """Calculate unpaid attendance seconds for one canonical seat/class scope."""
    if not seat_id or not class_id:
        raise ValueError("calculate_unpaid_attendance_seconds requires seat_id and class_id.")
    return _calculate_unpaid_attendance_seconds(
        seat_id,
        class_id,
        last_payroll_time,
        ctx=SimpleNamespace(class_id=class_id),
    )


def _calculate_active_seconds_for_range(*, seat_id, class_id, start_utc, end_utc):
    """Derive active intervals from append-only attendance rows and measure them."""
    rows = (
        AttendanceSession.query.filter(
            AttendanceSession.target_seat_id == seat_id,
            AttendanceSession.class_id == class_id,
            AttendanceSession.timestamp < end_utc,
        )
        .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
        .all()
    )
    now_evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
    )
    now_utc = min(now_evaluation.canonical_now_utc, end_utc)
    intervals = []
    active_start = None
    for row in rows:
        timestamp = _ensure_utc_timestamp(row.timestamp)
        if row.status == "active":
            active_start = timestamp
            continue
        if row.status == "inactive" and active_start is not None:
            interval_start = max(active_start, start_utc)
            interval_end = min(timestamp, end_utc)
            if interval_end >= interval_start:
                intervals.append((interval_start, interval_end))
            active_start = None

    if active_start is not None and now_utc >= start_utc:
        interval_start = max(active_start, start_utc)
        interval_end = min(now_utc, end_utc)
        if interval_end >= interval_start:
            intervals.append((interval_start, interval_end))

    if not intervals:
        return 0

    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="elapsed_duration",
        intervals=intervals,
        reference_time_utc=now_utc,
    )
    return int(evaluation.elapsed_seconds)


def calculate_period_attendance(seat_id, class_id, date):
    """
    Calculates total attendance seconds for a seat in a class
    on a specific date. Used for daily attendance reporting.
    NOTE: This uses UTC day boundaries.
    For class-timezone daily limits, use calculate_period_attendance_utc_range instead.
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_period_attendance requires seat_id and class_id.")

    bounds = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="evaluation_day_boundaries",
        evaluation_date=date,
    )

    return _calculate_active_seconds_for_range(
        seat_id=seat_id,
        class_id=class_id,
        start_utc=bounds.boundary_start_utc,
        end_utc=bounds.boundary_end_utc,
    )


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

    return _calculate_active_seconds_for_range(
        seat_id=seat_id,
        class_id=class_id,
        start_utc=_ensure_utc_timestamp(start_utc),
        end_utc=_ensure_utc_timestamp(end_utc),
    )


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

    min_anchor_utc = _ensure_utc_timestamp(min_anchor) if min_anchor else None
    query = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id.in_(seat_ids),
        AttendanceSession.class_id.in_(allowed_class_ids),
    )

    sessions = query.order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()

    grouped = {}
    for session in sessions:
        key = (session.target_seat_id, session.class_id)
        grouped.setdefault(key, []).append(
            SimpleNamespace(
                seat_id=session.target_seat_id,
                class_id=session.class_id,
                status=session.status,
                timestamp=_ensure_utc_timestamp(session.timestamp),
            )
        )

    for events in grouped.values():
        events.sort(key=lambda event: (_ensure_utc_timestamp(event.timestamp), 0 if event.status == "active" else 1))

    return grouped

def calculate_seconds_in_memory(events, anchor):
    """
    Calculate unpaid seconds from a sorted list of events, strictly after anchor.
    """
    in_time = None
    intervals = []
    class_id = getattr(events[0], "class_id", None) if events else None

    anchor = _ensure_utc_timestamp(anchor)

    for event in events:
        event_time = _ensure_utc_timestamp(event.timestamp)

        # Skip events before specific anchor
        if anchor and event_time <= anchor:
            # If active, it effectively sets in_time for subsequent period
            if event.status == 'active':
                in_time = event_time
            else:
                in_time = None
            continue

        # If we crossed the anchor boundary and in_time was set from a pre-anchor event
        if in_time and anchor and in_time < anchor:
            in_time = anchor

        if event.status == 'active':
            if in_time is None:
                in_time = event_time
        elif event.status == 'inactive' and in_time:
            intervals.append((in_time, event_time))
            in_time = None

    # If still active at "now"
    if in_time:
        if anchor and in_time < anchor:
            in_time = anchor

        now_evaluation = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=SimpleNamespace(class_id=class_id),
            primitive="current_time",
        )
        intervals.append((in_time, now_evaluation.canonical_now_utc))

    if not intervals:
        return 0

    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="elapsed_duration",
        intervals=intervals,
    )
    return int(evaluation.elapsed_seconds)
