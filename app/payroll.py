import sqlalchemy as sa
from app.extensions import db
from app.models import Transaction, PayrollSettings, ClassEconomy
from app.utils.time import ensure_utc
from app.attendance import (
    get_batch_attendance_events,
    calculate_seconds_in_memory
)
from flask import has_request_context, session
from decimal import Decimal


DEFAULT_PAY_RATE_PER_MINUTE = Decimal('0.25')
DEFAULT_PAY_RATE_PER_SECOND_DECIMAL = DEFAULT_PAY_RATE_PER_MINUTE / Decimal('60')
# Public default constant kept as Decimal to match helper return types.
DEFAULT_PAY_RATE_PER_SECOND = DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


def _fetch_single_active_setting(*, class_id: str, block: str | None):
    """Return exactly one active payroll setting for class/block or None.

    Raises:
        ValueError: when class scope is missing or duplicate active rows exist.
    """
    if not class_id:
        raise ValueError("PayrollSettings lookup requires class_id.")
    query = PayrollSettings.query.filter(
        PayrollSettings.class_id == class_id,
        PayrollSettings.is_active.is_(True),
    )
    if block:
        query = query.filter(sa.func.upper(PayrollSettings.block) == block.upper())
    else:
        query = query.filter(PayrollSettings.block.is_(None))
    rows = query.order_by(PayrollSettings.updated_at.desc(), PayrollSettings.id.desc()).limit(2).all()
    if len(rows) > 1:
        raise ValueError(
            f"Ambiguous PayrollSettings scope for class_id={class_id} block={block or '__GLOBAL__'}."
        )
    return rows[0] if rows else None


def get_pay_rate_for_block(block, *, class_id: str):
    """
    Get the pay rate for a specific block from settings, falling back to global/default.

    Args:
        block (str): The block/period identifier.
        class_id (str): Canonical class scope.

    Returns:
        Decimal: The pay rate per second as Decimal for precise financial calculations.
    """
    from decimal import Decimal
    
    # Try block-specific settings first
    setting = _fetch_single_active_setting(class_id=class_id, block=block)
    if setting and setting.pay_rate:
        return setting.pay_rate / Decimal('60')

    # Fall back to class-scoped global settings
    global_setting = _fetch_single_active_setting(class_id=class_id, block=None)
    if global_setting and global_setting.pay_rate:
        return global_setting.pay_rate / Decimal('60')

    # Ultimate fallback to hardcoded default
    return DEFAULT_PAY_RATE_PER_SECOND_DECIMAL


def get_daily_limit_seconds(block, *, class_id: str):
    """
    Get the daily time limit in seconds for a specific block from settings.

    Args:
        block (str): The block/period identifier.
        class_id (str): Canonical class scope.

    Returns:
        int or None: The daily limit in seconds, or None if no limit is set.
    """
    # Try block-specific settings first
    setting = _fetch_single_active_setting(class_id=class_id, block=block)
    if setting:
        # Simple mode: daily_limit_hours
        if setting.settings_mode == 'simple' and setting.daily_limit_hours:
            return int(setting.daily_limit_hours * 3600)  # Convert hours to seconds
        # Advanced mode: max_time_per_day
        if setting.settings_mode == 'advanced' and setting.max_time_per_day:
            unit_to_seconds = {
                'seconds': 1,
                'minutes': 60,
                'hours': 3600,
                'days': 86400
            }
            multiplier = unit_to_seconds.get(setting.max_time_per_day_unit, 3600)
            return int(setting.max_time_per_day * multiplier)

    # Fall back to class-scoped global settings
    global_setting = _fetch_single_active_setting(class_id=class_id, block=None)
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


def calculate_payroll_breakdown(class_id, seat_ids, last_payroll_time):
    """
    Calculates payroll for a given list of seat_ids since the last payroll run.
    Optimized to use batch queries and avoid N+1 performance issues.
    """
    summary = {}
    if not seat_ids or not class_id:
        return summary

    from app.models import Seat
    seats = Seat.query.filter(Seat.id.in_(seat_ids), Seat.class_id == class_id).all()
    if not seats:
        return summary

    # --- 1. Determine class scope and fetch class-scoped payroll anchors ---
    allowed_class_ids = [class_id]
    scoped_seat_ids = [s.id for s in seats]
    pay_rates = _get_batch_pay_rates(allowed_class_ids)
    student_last_payrolls = _get_batch_last_payroll_times(
        scoped_seat_ids,
        allowed_class_ids=allowed_class_ids,
    )

    # --- 2. Batch Fetch Attendance Events ---
    normalized_global_last_payroll = ensure_utc(last_payroll_time)
    valid_times = [t for t in student_last_payrolls.values() if t]
    if normalized_global_last_payroll:
        valid_times.append(normalized_global_last_payroll)

    min_anchor = min(valid_times) if valid_times else None
    events_map = get_batch_attendance_events(scoped_seat_ids, min_anchor, allowed_class_ids=allowed_class_ids)

    # --- 3. In-Memory Calculation ---
    for seat in seats:
        block_upper = (seat.class_economy.section if seat.class_economy and seat.class_economy.section else "").upper()
        
        rate_per_second = pay_rates.get(
            (class_id, block_upper),
            pay_rates.get((class_id, None), DEFAULT_PAY_RATE_PER_SECOND_DECIMAL),
        )

        payroll_anchor = student_last_payrolls.get((seat.id, class_id))
        if payroll_anchor is None:
            payroll_anchor = normalized_global_last_payroll

        # Attendance events are grouped by canonical seat/class scope only.
        events = events_map.get((seat.id, class_id), [])
        total_seconds = calculate_seconds_in_memory(events, payroll_anchor)

        if total_seconds > 0:
            amount = (Decimal(total_seconds) * rate_per_second).quantize(Decimal('0.01'))
            if amount > 0:
                summary.setdefault(seat.id, Decimal('0.00'))
                summary[seat.id] += amount

    return summary

def _get_batch_pay_rates(class_ids):
    """Batch fetch pay rates scoped to canonical class IDs."""
    from decimal import Decimal
    if not class_ids:
        return {}
    settings = (
        PayrollSettings.query
        .filter(
            PayrollSettings.class_id.in_(class_ids),
            PayrollSettings.is_active.is_(True),
        )
        .all()
    )
    rates = {}

    # Populate specific blocks and class-global defaults.
    for s in settings:
        if s.pay_rate and s.class_id:
            rate_sec = s.pay_rate / Decimal('60')
            key = (s.class_id, s.block.upper() if s.block else None)
            rates[key] = rate_sec
            
    return rates



def _get_batch_last_payroll_times(seat_ids, allowed_class_ids):
    """
    Batch find the last payroll/manual-payment anchor for each (seat_id, class_id).
    """
    from sqlalchemy import func

    if not seat_ids or not allowed_class_ids:
        return {}

    query = db.session.query(
        Transaction.seat_id,
        Transaction.class_id,
        func.max(Transaction.timestamp)
    ).filter(
        Transaction.seat_id.in_(seat_ids),
        Transaction.class_id.in_(allowed_class_ids),
        Transaction.type.in_(["payroll", "manual_payment"]),
        Transaction.is_void.isnot(True),
    )

    results = query.group_by(Transaction.seat_id, Transaction.class_id).all()

    return {(seat_id, class_id): ensure_utc(ts) for seat_id, class_id, ts in results}




from app.feats.base import feat_shell
from app.utils.time import utc_now


@feat_shell("FEAT-LED-004")
def get_cached_payroll_with_meta(class_id, seat_ids, last_payroll_time):
    """Calculate payroll directly without persisted cache state."""
    if not class_id:
        raise ValueError("Class scope (class_id) must be explicitly provided.")

    summary = calculate_payroll_breakdown(class_id, seat_ids, last_payroll_time)
    return summary, utc_now()
