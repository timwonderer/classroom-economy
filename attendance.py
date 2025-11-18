from datetime import datetime, timezone
from sqlalchemy import func

def get_last_payroll_time():
    """Fetches the timestamp of the most recent global payroll transaction."""
    from app.models import Transaction  # Local import to avoid circular dependency
    last_payroll_tx = Transaction.query.filter_by(type="payroll").order_by(Transaction.timestamp.desc()).first()
    return _as_utc(last_payroll_tx.timestamp) if last_payroll_tx else None

def _as_utc(dt):
    """Ensure a datetime is timezone-aware and in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time):
    """
    Calculates total attendance seconds for a student in a specific period
    since the last payroll run. This version is corrected to prevent double-counting
    and only calculates completed sessions to ensure correctness.
    """
    from app.models import TapEvent
    from app.extensions import db
    from datetime import datetime, timezone

    last_payroll_time = _as_utc(last_payroll_time)

    base_query = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period
    ).order_by(TapEvent.timestamp.asc())

    # If there's no payroll history for the system, calculate from all events.
    if not last_payroll_time:
        events = base_query.all()
        in_time = None
        total_seconds = 0
        for event in events:
            event_time = _as_utc(event.timestamp)
            if event.status == "active":
                in_time = event_time
            elif event.status == "inactive" and in_time:
                total_seconds += (event_time - in_time).total_seconds()
                in_time = None
        if in_time:
            # Student is still clocked in; count time up to now.
            now = datetime.now(timezone.utc)
            total_seconds += (now - in_time).total_seconds()
        return int(total_seconds)

    # --- If payroll history exists ---
    last_event_before_payroll = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period,
        TapEvent.timestamp <= last_payroll_time
    ).order_by(TapEvent.timestamp.desc()).first()

    events_after_payroll = base_query.filter(TapEvent.timestamp > last_payroll_time).all()

    total_seconds = 0
    in_time = None

    # If the student was active during payroll, start counting from the payroll time.
    if last_event_before_payroll and last_event_before_payroll.status == 'active':
        in_time = last_payroll_time

    # Process events that occurred strictly after the last payroll.
    for event in events_after_payroll:
        event_time = _as_utc(event.timestamp)
        if event.status == "active":
            if in_time is None:
                in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    if in_time:
        # Student remained clocked in past the last recorded event; count up to now.
        now = datetime.now(timezone.utc)
        total_seconds += (now - in_time).total_seconds()
    return int(total_seconds)


def calculate_period_attendance(student_id, period, date):
    """
    Calculates total attendance seconds for a student in a specific period
    on a specific date. Used for daily attendance reporting.
    """
    from app.models import TapEvent

    # Get all events for this student/period on the specified date
    events = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period,
        func.date(TapEvent.timestamp) == date
    ).order_by(TapEvent.timestamp.asc()).all()

    total_seconds = 0
    in_time = None

    for event in events:
        event_time = _as_utc(event.timestamp)
        if event.status == "active":
            in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    return int(total_seconds)


def get_session_status(student_id, period):
    """
    Gets the current session status for a student in a specific period.
    Returns a tuple of (is_active, done, duration).
    """
    from app.models import TapEvent
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date()

    # Check if student is currently active
    latest_event = (
        TapEvent.query
        .filter_by(student_id=student_id, period=period)
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = latest_event.status == "active" if latest_event else False

    # Check if marked as done today
    done = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period,
        func.date(TapEvent.timestamp) == today,
        TapEvent.reason != None
    ).filter(func.lower(TapEvent.reason) == 'done').first() is not None

    # Calculate unpaid duration
    last_payroll_time = get_last_payroll_time()
    duration = calculate_unpaid_attendance_seconds(student_id, period, last_payroll_time)

    return is_active, done, duration


def get_all_block_statuses(student):
    """
    Gets the status for all blocks assigned to a student for the /api/student-status endpoint.
    """
    from app.models import TapEvent
    from sqlalchemy import func
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date()
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
    period_states = {}

    last_payroll_time = get_last_payroll_time()
    RATE_PER_SECOND = 0.25 / 60

    for blk in student_blocks:
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=blk)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        is_active = latest_event.status == "active" if latest_event else False

        done = TapEvent.query.filter(
            TapEvent.student_id == student.id,
            TapEvent.period == blk,
            func.date(TapEvent.timestamp) == today,
            TapEvent.reason != None
        ).filter(func.lower(TapEvent.reason) == 'done').first() is not None

        duration = calculate_unpaid_attendance_seconds(student.id, blk, last_payroll_time)
        projected_pay = duration * RATE_PER_SECOND
        period_states[blk] = {
            "active": is_active,
            "done": done,
            "duration": duration,
            "projected_pay": projected_pay
        }
    return period_states