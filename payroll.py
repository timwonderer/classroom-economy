from app import db, TapEvent, Student, Transaction, PayrollSettings
from datetime import datetime, timezone

def get_pay_rate_for_block(block):
    """
    Get the pay rate for a specific block from settings, falling back to global/default.

    Args:
        block (str): The block/period identifier.

    Returns:
        float: The pay rate per second.
    """
    # Try block-specific settings first
    if block:
        setting = PayrollSettings.query.filter_by(block=block, is_active=True).first()
        if setting and setting.pay_rate:
            return setting.pay_rate / 60.0  # Convert per-minute to per-second

    # Fall back to global settings
    global_setting = PayrollSettings.query.filter_by(block=None, is_active=True).first()
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / 60.0

    # Ultimate fallback to hardcoded default
    return 0.25 / 60  # $0.25 per minute


def calculate_payroll(students, last_payroll_time):
    """
    Calculates payroll for a given list of students since the last payroll run.
    Now uses PayrollSettings from database for configurable pay rates.

    Args:
        students (list): A list of Student objects.
        last_payroll_time (datetime): The timestamp of the last payroll run.

    Returns:
        dict: A dictionary mapping student IDs to their calculated payroll amount.
    """
    summary = {}

    for student in students:
        student_blocks = [b.strip().upper() for b in (student.block or "").split(',') if b.strip()]
        for blk in student_blocks:
            # Get pay rate for this specific block
            rate_per_second = get_pay_rate_for_block(blk)
            q = TapEvent.query.filter(
                TapEvent.student_id == student.id,
                TapEvent.period == blk
            )
            if last_payroll_time:
                q = q.filter(TapEvent.timestamp > last_payroll_time)

            events = q.order_by(TapEvent.timestamp.asc()).all()

            total_seconds = 0
            in_time = None
            for event in events:
                event_time = event.timestamp.replace(tzinfo=timezone.utc)
                if event.status == "active":
                    if in_time is None:
                        in_time = event_time
                elif event.status == "inactive":
                    if in_time:
                        delta = (event_time - in_time).total_seconds()
                        if delta > 0:
                            total_seconds += delta
                        in_time = None

            if in_time:
                now = datetime.now(timezone.utc)
                delta = (now - in_time).total_seconds()
                if delta > 0:
                    total_seconds += delta

            if total_seconds > 0:
                amount = round(total_seconds * rate_per_second, 2)
                if amount > 0:
                    summary.setdefault(student.id, 0)
                    summary[student.id] += amount

    return summary