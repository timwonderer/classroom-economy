from app.extensions import db
from app.models import TapEvent, Student, Transaction, PayrollSettings
from datetime import datetime, timezone
from attendance import calculate_unpaid_attendance_seconds


def load_payroll_settings_cache():
    """Preload active payroll settings to avoid repeated queries during batch operations."""

    settings = PayrollSettings.query.filter_by(is_active=True).all()
    block_settings = {s.block: s for s in settings if s.block}
    global_setting = next((s for s in settings if s.block is None), None)
    return block_settings, global_setting


def get_pay_rate_for_block(block, settings_cache=None):
    """
    Get the pay rate for a specific block from settings, falling back to global/default.

    Args:
        block (str): The block/period identifier.

    Returns:
        float: The pay rate per second.
    """
    block_settings, global_setting = settings_cache or load_payroll_settings_cache()

    # Try block-specific settings first
    if block:
        setting = block_settings.get(block)
        if setting and setting.pay_rate:
            return setting.pay_rate / 60.0  # Convert per-minute to per-second

    # Fall back to global settings
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / 60.0

    # Ultimate fallback to hardcoded default
    return 0.25 / 60  # $0.25 per minute


def get_daily_limit_seconds(block, settings_cache=None):
    """
    Get the daily time limit in seconds for a specific block from settings.

    Args:
        block (str): The block/period identifier.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    block_settings, global_setting = settings_cache or load_payroll_settings_cache()

    # Try block-specific settings first
    if block:
        setting = block_settings.get(block)
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

    # Fall back to global settings
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


def calculate_payroll(students, last_payroll_time, settings_cache=None):
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

    settings_cache = settings_cache or load_payroll_settings_cache()

    for student in students:
        # Keep original block names for settings lookup, but uppercase for TapEvent queries
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        for block_original in student_blocks:
            block_upper = block_original.upper()

            # Get pay rate using original block name (matches PayrollSettings.block)
            rate_per_second = get_pay_rate_for_block(block_original, settings_cache)

            total_seconds = calculate_unpaid_attendance_seconds(
                student.id,
                block_upper,
                last_payroll_time,
            )

            if total_seconds > 0:
                amount = round(total_seconds * rate_per_second, 2)
                if amount > 0:
                    summary.setdefault(student.id, 0)
                    summary[student.id] += amount

    return summary
