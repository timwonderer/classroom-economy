from app.extensions import db
from app.models import TapEvent, Student, Transaction, PayrollSettings
from datetime import datetime, timezone
from attendance import calculate_unpaid_attendance_seconds, get_last_payroll_time
from flask import session


def get_pay_rate_for_block(block, teacher_id=None):
    """
    Get the pay rate for a specific block from settings, falling back to global/default.

    CRITICAL: Scopes query by teacher_id to prevent multi-tenancy leaks.

    Args:
        block (str): The block/period identifier.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        float: The pay rate per second.
    """
    # Get teacher_id from session if not provided
    if teacher_id is None:
        teacher_id = session.get('admin_id')

    # Can't lookup settings without a teacher_id - return default
    if teacher_id is None:
        return 0.25 / 60  # $0.25 per minute

    # Try block-specific settings first
    if block:
        setting = PayrollSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block,
            is_active=True
        ).first()
        if setting and setting.pay_rate:
            return setting.pay_rate / 60.0  # Convert per-minute to per-second

    # Fall back to global settings for this teacher
    global_setting = PayrollSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None,
        is_active=True
    ).first()
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / 60.0

    # Ultimate fallback to hardcoded default
    return 0.25 / 60  # $0.25 per minute


def get_daily_limit_seconds(block, teacher_id=None):
    """
    Get the daily time limit in seconds for a specific block from settings.

    CRITICAL: Scopes query by teacher_id to prevent multi-tenancy leaks.

    Args:
        block (str): The block/period identifier.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    # Get teacher_id from session if not provided
    if teacher_id is None:
        teacher_id = session.get('admin_id')

    # Can't lookup settings without a teacher_id - return no limit
    if teacher_id is None:
        return None

    # Try block-specific settings first
    if block:
        setting = PayrollSettings.query.filter_by(
            teacher_id=teacher_id,
            block=block,
            is_active=True
        ).first()
        if setting:
            # Simple mode: daily_limit_hours
            if setting.settings_mode == 'simple' and setting.daily_limit_hours:
                return int(setting.daily_limit_hours * 3600)  # Convert hours to seconds
            # Advanced mode: max_time_per_day
            elif setting.settings_mode == 'advanced' and setting.max_time_per_day:
                unit_to_seconds = {
                    'seconds': 1,
                    'minutes': 60,
                    'hours': 3600,
                    'days': 86400
                }
                multiplier = unit_to_seconds.get(setting.max_time_per_day_unit, 3600)
                return int(setting.max_time_per_day * multiplier)

    # Fall back to global settings for this teacher
    global_setting = PayrollSettings.query.filter_by(
        teacher_id=teacher_id,
        block=None,
        is_active=True
    ).first()
    if global_setting:
        if global_setting.settings_mode == 'simple' and global_setting.daily_limit_hours:
            return int(global_setting.daily_limit_hours * 3600)
        elif global_setting.settings_mode == 'advanced' and global_setting.max_time_per_day:
            unit_to_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400
            }
            multiplier = unit_to_seconds.get(global_setting.max_time_per_day_unit, 3600)
            return int(global_setting.max_time_per_day * multiplier)

    # No limit set
    return None


def calculate_payroll(students, last_payroll_time, teacher_id=None):
    """
    Calculates payroll for a given list of students since the last payroll run.
    Now uses PayrollSettings from database for configurable pay rates.

    CRITICAL: Scopes payroll settings by teacher_id to prevent multi-tenancy leaks.

    Args:
        students (list): A list of Student objects.
        last_payroll_time (datetime): The timestamp of the last payroll run.
        teacher_id (int, optional): The teacher's ID. If not provided, uses session.

    Returns:
        dict: A dictionary mapping student IDs to their calculated payroll amount.
    """
    # Get teacher_id from session if not provided
    if teacher_id is None:
        teacher_id = session.get('admin_id')

    summary = {}

    for student in students:
        # Keep original block names for settings lookup, but uppercase for TapEvent queries
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        student_last_payroll_time = get_last_payroll_time(student_id=student.id)
        possible_anchors = [
            t for t in [last_payroll_time, student_last_payroll_time] if t
        ]
        payroll_anchor = max(possible_anchors) if possible_anchors else None
        for block_original in student_blocks:
            block_upper = block_original.upper()

            # Get pay rate using original block name (matches PayrollSettings.block)
            # Pass teacher_id to ensure correct settings are used
            rate_per_second = get_pay_rate_for_block(block_original, teacher_id=teacher_id)

            total_seconds = calculate_unpaid_attendance_seconds(
                student.id,
                block_upper,
                payroll_anchor,
            )

            if total_seconds > 0:
                amount = round(total_seconds * rate_per_second, 2)
                if amount > 0:
                    summary.setdefault(student.id, 0)
                    summary[student.id] += amount

    return summary
