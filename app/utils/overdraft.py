from datetime import datetime, timezone
from app.utils.time import utc_now
from decimal import Decimal, InvalidOperation

from sqlalchemy import func

from app.extensions import db
from app.models import Transaction, TransactionStatus, _quantize_currency


def evaluate_overdraft_allowance(seat, debit_amount, banking_settings):
    """
    Check whether a checking debit can proceed based on balances and overdraft protection.

    Returns (allowed, shortfall, checking_balance, savings_balance).
    """
    from app.services.ledger_service import get_available_balances

    checking_balance, savings_balance = get_available_balances(seat.id, seat.class_id)
    try:
        debit_amount = Decimal(str(debit_amount))
    except (TypeError, InvalidOperation):
        return False, Decimal('0.00'), checking_balance, savings_balance

    if debit_amount <= 0:
        return True, Decimal('0.00'), checking_balance, savings_balance

    if checking_balance >= debit_amount:
        return True, Decimal('0.00'), checking_balance, savings_balance

    shortfall = debit_amount - checking_balance
    if banking_settings and banking_settings.overdraft_protection_enabled and savings_balance >= shortfall:
        return True, shortfall, checking_balance, savings_balance

    return False, shortfall, checking_balance, savings_balance


def charge_overdraft_fee_if_needed(seat, banking_settings, *, force=False, idempotency_key=None):
    """
    Charge an overdraft fee if enabled.

    Args:
        force: Charge fee even if balance is non-negative (declined transaction).
        idempotency_key: Mandatory for Tier 1 (HIGH blast radius) enforcement.
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, Decimal('0.00')

    from app.services.ledger_service import create_pending_transaction_idempotent, get_available_balance

    current_balance = _quantize_currency(
        get_available_balance(seat.id, seat.class_id, 'checking')
    )

    # CRITICAL FIX: Normalize near-zero balances to exactly zero
    if abs(current_balance) < Decimal('0.01'):  # Less than 1 cent
        current_balance = Decimal('0.00')

    # Only charge if balance is negative unless forced (declined transaction).
    if not force and current_balance >= Decimal('0.00'):
        return False, Decimal('0.00')

    fee_amount = Decimal('0.00')

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = _quantize_currency(banking_settings.overdraft_fee_flat_amount)
    elif banking_settings.overdraft_fee_type == 'progressive':
        # V2 Temporal Model: Use class-scoped month/year
        from app.utils.time import get_class_now
        now = get_class_now(seat.class_id)
        # We need a UTC boundary for the query, but it should represent the start of the month in class time.
        from app.utils.time import get_class_month_start_utc
        month_start_utc = get_class_month_start_utc(seat.class_id)

        fee_filters = [
            Transaction.seat_id == seat.id,
            Transaction.class_id == seat.class_id,
            Transaction.type == 'overdraft_fee',
            Transaction.timestamp >= month_start_utc
        ]

        overdraft_fee_count = Transaction.query.filter(*fee_filters).count()

        if overdraft_fee_count == 0:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_1 or 0)
        elif overdraft_fee_count == 1:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_2 or 0)
        elif overdraft_fee_count >= 2:
            fee_amount = _quantize_currency(banking_settings.overdraft_fee_progressive_3 or 0)

        if banking_settings.overdraft_fee_progressive_cap:
            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.seat_id == seat.id,
                Transaction.class_id == seat.class_id,
                Transaction.type == 'overdraft_fee',
                Transaction.timestamp >= month_start_utc
            ).scalar()
            total_fees_this_month = _quantize_currency(total_fees_this_month) if total_fees_this_month else Decimal('0.00')
            cap = _quantize_currency(banking_settings.overdraft_fee_progressive_cap)

            if abs(total_fees_this_month) + fee_amount > cap:
                fee_amount = max(Decimal('0.00'), cap - abs(total_fees_this_month))

    if fee_amount > 0:
        if not idempotency_key:
             from app.feats.base import get_correlation_id
             idempotency_key = f"overdraft:{get_correlation_id()}:{seat.id}"

        from app.models import ClassEconomy
        class_economy = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        teacher_id = class_economy.user_id if class_economy else None
        if not teacher_id:
            return False, Decimal('0.00')

        overdraft_fee_tx, created = create_pending_transaction_idempotent(
            idempotency_key=idempotency_key,
            seat_id=seat.id,
            class_id=seat.class_id,
            teacher_id=teacher_id,
            amount=-fee_amount,
            account_type='checking',
            type='overdraft_fee',
            description=(
                f'Overdraft fee (declined transaction balance: ${current_balance:.2f})'
                if force else
                f'Overdraft fee (balance: ${current_balance:.2f})'
            ),
        )
        db.session.flush()
        return True, fee_amount

    return False, Decimal('0.00')
