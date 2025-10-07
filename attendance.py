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
    since the last payroll run. This version is corrected to prevent double-counting.
    """
    from app import TapEvent, db, app
    from datetime import datetime, timezone

    app.logger.info(f"--- AGGRESSIVE LOG: START unpaid seconds for student {student_id}, period {period} ---")

    last_payroll_time = _as_utc(last_payroll_time)
    app.logger.info(f"AGGRESSIVE LOG: last_payroll_time (UTC): {last_payroll_time}")

    base_query = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period
    ).order_by(TapEvent.timestamp.asc())

    if not last_payroll_time:
        app.logger.info("AGGRESSIVE LOG: No payroll history. Calculating from all events.")
        events = base_query.all()
        app.logger.info(f"AGGRESSIVE LOG: Found {len(events)} total events for student.")
        in_time = None
        total_seconds = 0
        for i, event in enumerate(events):
            event_time = _as_utc(event.timestamp)
            app.logger.info(f"AGGRESSIVE LOG (no payroll) [Event {i}]: status={event.status}, time={event_time}, current_in_time={in_time}, total_seconds={total_seconds}")
            if event.status == "active":
                if in_time is None:
                    in_time = event_time
                    app.logger.info(f"AGGRESSIVE LOG (no payroll) [Event {i}]: ACTIVE event. Setting in_time to {in_time}")
            elif event.status == "inactive" and in_time:
                duration = (event_time - in_time).total_seconds()
                total_seconds += duration
                app.logger.info(f"AGGRESSIVE LOG (no payroll) [Event {i}]: INACTIVE event. Adding {duration}s. New total_seconds={total_seconds}")
                in_time = None
        if in_time:
            now = datetime.now(timezone.utc)
            duration = (now - in_time).total_seconds()
            total_seconds += duration
            app.logger.info(f"AGGRESSIVE LOG (no payroll): Still active. Adding {duration}s from {in_time} to {now}. Final total_seconds={total_seconds}")
        app.logger.info(f"--- AGGRESSIVE LOG: END (no payroll). Returning {int(total_seconds)} seconds. ---")
        return int(total_seconds)

    app.logger.info("AGGRESSIVE LOG: Payroll history found.")
    last_event_before_payroll = TapEvent.query.filter(
        TapEvent.student_id == student_id,
        TapEvent.period == period,
        TapEvent.timestamp <= last_payroll_time
    ).order_by(TapEvent.timestamp.desc()).first()

    if last_event_before_payroll:
        app.logger.info(f"AGGRESSIVE LOG: Last event before payroll: status={last_event_before_payroll.status} at {last_event_before_payroll.timestamp}")
    else:
        app.logger.info("AGGRESSIVE LOG: No events found before last payroll.")

    events_after_payroll = base_query.filter(TapEvent.timestamp > last_payroll_time).all()
    app.logger.info(f"AGGRESSIVE LOG: Found {len(events_after_payroll)} events after last payroll.")

    total_seconds = 0
    in_time = None

    if last_event_before_payroll and last_event_before_payroll.status == 'active':
        in_time = last_payroll_time
        app.logger.info(f"AGGRESSIVE LOG: Student was active during payroll. Setting initial in_time to last_payroll_time: {in_time}")

    for i, event in enumerate(events_after_payroll):
        event_time = _as_utc(event.timestamp)
        app.logger.info(f"AGGRESSIVE LOG (with payroll) [Event {i}]: status={event.status}, time={event_time}, current_in_time={in_time}, total_seconds={total_seconds}")
        if event.status == "active":
            if in_time is None:
                in_time = event_time
                app.logger.info(f"AGGRESSIVE LOG (with payroll) [Event {i}]: ACTIVE event. Setting in_time to {in_time}")
        elif event.status == "inactive" and in_time:
            duration = (event_time - in_time).total_seconds()
            total_seconds += duration
            app.logger.info(f"AGGRESSIVE LOG (with payroll) [Event {i}]: INACTIVE event. Adding {duration}s. New total_seconds={total_seconds}")
            in_time = None

    if in_time:
        now = datetime.now(timezone.utc)
        duration = (now - in_time).total_seconds()
        total_seconds += duration
        app.logger.info(f"AGGRESSIVE LOG (with payroll): Still active. Adding {duration}s from {in_time} to {now}. Final total_seconds={total_seconds}")

    app.logger.info(f"--- AGGRESSIVE LOG: END (with payroll). Returning {int(total_seconds)} seconds. ---")
    return int(total_seconds)

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