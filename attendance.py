from datetime import datetime, timezone
from sqlalchemy import func

def get_last_payroll_time():
    """Fetches the timestamp of the most recent global payroll transaction."""
    from app import Transaction  # Local import to avoid circular dependency
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
    since the last payroll run.
    """
    from app import TapEvent  # Local import
    query = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period
    )

    in_time = None
    last_payroll_time = _as_utc(last_payroll_time)

    # Check if the student was already tapped in *before* the last payroll.
    if last_payroll_time:
        last_event_before_payroll = TapEvent.query.filter(
            TapEvent.student_id == student_id,
            TapEvent.period == period,
            TapEvent.timestamp <= last_payroll_time
        ).order_by(TapEvent.timestamp.desc()).first()

        if last_event_before_payroll and last_event_before_payroll.status == 'active':
            in_time = last_payroll_time

    # Get events since the last payroll
    if last_payroll_time:
        query = query.filter(TapEvent.timestamp > last_payroll_time)

    events = query.order_by(TapEvent.timestamp.asc()).all()
    total_seconds = 0

    # Process events that occurred after the last payroll
    for event in events:
        event_time = _as_utc(event.timestamp)

        if event.status == "active":
            if in_time is None:
                in_time = event_time
        elif event.status == "inactive" and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    # If the student is still tapped in, calculate duration up to now.
    if in_time:
        now = datetime.now(timezone.utc)
        total_seconds += (now - in_time).total_seconds()

    return int(total_seconds)

def calculate_period_attendance(student_id, period, date):
    """Calculates total attendance seconds for a given day and period."""
    from app import TapEvent  # Local import
    events = TapEvent.query.filter_by(student_id=student_id, period=period).filter(
        func.date(TapEvent.timestamp) == date
    ).order_by(TapEvent.timestamp.asc()).all()

    total_seconds = 0
    current_in = None
    for event in events:
        event_time = event.timestamp
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        if event.status == "active":
            current_in = event_time
        elif event.status == "inactive" and current_in:
            total_seconds += (event_time - current_in).total_seconds()
            current_in = None
    # Handle case where still active without tap_out
    if current_in:
        now = datetime.now(timezone.utc)
        total_seconds += (now - current_in).total_seconds()
    return int(total_seconds)

def get_session_status(student_id, blk):
    """
    Determines active/inactive/done state for a block using the most recent TapEvent row.
    - active: latest TapEvent.status == 'active'
    - done: if any TapEvent today for this block has reason 'done'
    - duration: total seconds for today (from calculate_period_attendance)
    """
    from app import TapEvent # Local import
    from sqlalchemy import func
    from datetime import datetime

    today = datetime.utcnow().date()
    # Find the most recent TapEvent for this student/block
    latest_event = (
        TapEvent.query
        .filter(
            TapEvent.student_id == student_id,
            TapEvent.period == blk
        )
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = False
    if latest_event and latest_event.status == 'active':
        is_active = True

    # Determine done: any event today for this block with reason 'done'
    done = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == blk,
        func.date(TapEvent.timestamp) == today,
        TapEvent.reason != None
    ).filter(func.lower(TapEvent.reason) == 'done').first() is not None

    # Duration: sum of today's durations using calculate_period_attendance
    duration = calculate_period_attendance(student_id, blk, today)

    return is_active, done, duration

def get_all_block_statuses(student):
    """
    Gets the status for all blocks assigned to a student for the /api/student-status endpoint.
    """
    from app import TapEvent
    from sqlalchemy import func
    from datetime import datetime

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