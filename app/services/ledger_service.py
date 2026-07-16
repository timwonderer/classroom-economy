from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import LedgerBalanceSnapshot, Seat, Transaction, TransactionStatus, ClassEconomy, _quantize_currency
from app.utils.seat_scope import transaction_scope_filter
from app.utils.time import ensure_utc, utc_now
from app.utils.transaction_idempotency import create_idempotent_transaction
from app.feats.base import feat_shell, audit_protected

# Protected fields captured in the audit payload for every ledger write
_TRANSACTION_AUDIT_FIELDS = [
    "amount", "account_type", "type", "status",
    "class_id", "seat_id", "description", "correlation_id",
]


def _non_void_filter():
    return Transaction.is_void.isnot(True)


def get_last_payroll_time(seat_id: int | None = None, class_id: str | None = None):
    """Return the most recent payroll anchor without mutating any state."""
    if seat_id is None and class_id is None:
        # V2 Safety: If no scope is provided, we cannot reliably find an anchor.
        return None

    query = Transaction.query.filter(_non_void_filter())
    
    if seat_id:
        # Seat-specific anchor: includes manual payments
        query = query.filter(
            Transaction.seat_id == seat_id,
            Transaction.type.in_(["payroll", "manual_payment"])
        )
    elif class_id:
        # Class-wide anchor: only actual payroll runs
        query = query.filter(
            Transaction.class_id == class_id,
            Transaction.type == "payroll"
        )
    else:
        # Fallback for unexpected states (should be caught by the first check though)
        query = query.filter(Transaction.type == "payroll")

    last_payroll_tx = query.order_by(Transaction.timestamp.desc()).first()
    return ensure_utc(last_payroll_tx.timestamp) if last_payroll_tx else None


def _get_balance_cache(seat_id: int, class_id: str):
    """Retrieve authoritative balance snapshot."""
    if not class_id or not seat_id:
        raise ValueError("FATAL: Balance lookup requires class_id and seat_id.")
    return LedgerBalanceSnapshot.query.filter_by(seat_id=seat_id, class_id=class_id).first()


def _get_posted_balance_fallback(seat_id: int, class_id: str, account_type: str) -> Decimal:
    """Compute posted balance from class-scoped ledger history."""
    all_non_void = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.seat_id == seat_id,
        Transaction.class_id == class_id,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.seat_id == seat_id,
        Transaction.class_id == class_id,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(all_non_void - pending)


def get_posted_balance(seat_id: int, class_id: str, account_type: str) -> Decimal:
    """Read the posted balance snapshot for a single account without side effects."""
    cache = _get_balance_cache(seat_id, class_id)
    if cache:
        cents = (
            cache.posted_checking_balance_cents
            if account_type == "checking"
            else cache.posted_savings_balance_cents
        )
        return _quantize_currency(Decimal(cents) / 100)

    return _get_posted_balance_fallback(seat_id, class_id, account_type)


def get_pending_balance_delta(seat_id: int, class_id: str, account_type: str) -> Decimal:
    """Return the pending delta for an account without mutating settlement state."""
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.seat_id == seat_id,
        Transaction.class_id == class_id,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == account_type,
        _non_void_filter(),
    ).scalar() or Decimal("0.00")
    return _quantize_currency(pending)


def get_available_balance(seat_id: int, class_id: str, account_type: str) -> Decimal:
    """Return posted + pending balance for an account under the current policy model."""
    return _quantize_currency(
        get_posted_balance(seat_id, class_id, account_type)
        + get_pending_balance_delta(seat_id, class_id, account_type)
    )


def get_available_balances(seat_id: int, class_id: str) -> tuple[Decimal, Decimal]:
    """Return checking and savings available balances without side effects."""
    return (
        get_available_balance(seat_id, class_id, "checking"),
        get_available_balance(seat_id, class_id, "savings"),
    )


def create_pending_transaction(
    *,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    account_type: str,
    type: str,
    description: str,
    original_transaction_id: int | None = None,
    policy_id: int | None = None,
) -> Transaction:
    """Create a pending transaction row as the canonical write path for ledger mutations."""
    if not class_id or not seat_id:
         # CRITICAL: Clean break V2 requires explicit class_id and seat_id for all ledger writes.
         raise ValueError(f"FATAL: Ledger mutation requires seat_id ({seat_id}) and class_id ({class_id}).")

    transaction = Transaction(  # FEAT-AUTHORIZED-DIRECT-TX
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=_quantize_currency(amount),
        account_type=account_type,
        status=TransactionStatus.PENDING,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )
    db.session.add(transaction)
    db.session.flush()  # populate transaction.id before audit event

    audit_protected("ledger_transaction", transaction, "INSERT", _TRANSACTION_AUDIT_FIELDS)

    return transaction


def create_pending_transaction_idempotent(
    *,
    idempotency_key: str,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    account_type: str,
    type: str,
    description: str,
    original_transaction_id: int | None = None,
    policy_id: int | None = None,
):
    """Create a pending transaction through the idempotent ledger path."""
    transaction, created = create_idempotent_transaction(
        idempotency_key=idempotency_key,
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=_quantize_currency(amount),
        account_type=account_type,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )
    return transaction, created


def void_pending_transaction(transaction, *, voided_at=None) -> None:
    """Mark a pending transaction as void."""
    transaction.is_void = True
    transaction.status = TransactionStatus.VOID
    transaction.voided_at = voided_at or utc_now()


def compensate_posted_transaction(
    transaction,
    *,
    description: str,
    compensation_type: str = "refund",
    idempotency_key: str | None = None,
):
    """Append a compensating pending transaction for posted truth."""
    compensation_amount = _quantize_currency(-(transaction.amount or Decimal("0.00")))
    if idempotency_key:
        reversal_tx, _created = create_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=transaction.seat_id,
            class_id=transaction.class_id,
            user_id=transaction.user_id,
            amount=compensation_amount,
            account_type=transaction.account_type or "checking",
            type=compensation_type,
            original_transaction_id=transaction.id,
            policy_id=transaction.policy_id,
            description=description,
        )
    else:
        reversal_tx = create_pending_transaction(
            seat_id=transaction.seat_id,
            class_id=transaction.class_id,
            user_id=transaction.user_id,
            amount=compensation_amount,
            account_type=transaction.account_type or "checking",
            type=compensation_type,
            description=description,
            original_transaction_id=transaction.id,
            policy_id=transaction.policy_id,
        )
    db.session.flush()
    transaction.reversal_transaction_id = reversal_tx.id
    transaction.is_void = True
    db.session.flush()
    return reversal_tx


@feat_shell("FEAT-LED-001")
def create_transfer_pair(
    *,
    seat_id: int,
    class_id: str,
    user_id: int | None = None,
    amount,
    from_account: str,
    to_account: str,
    withdraw_description: str,
    deposit_description: str,
) -> tuple[Transaction, Transaction]:
    """Create the canonical pending transfer pair."""
    quantized_amount = _quantize_currency(amount)
    withdraw_tx = create_pending_transaction(
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=-quantized_amount,
        account_type=from_account,
        type="Withdrawal",
        description=withdraw_description,
    )
    deposit_tx = create_pending_transaction(
        seat_id=seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=quantized_amount,
        account_type=to_account,
        type="Deposit",
        description=deposit_description,
    )
    return withdraw_tx, deposit_tx


@feat_shell("FEAT-LED-001")
def apply_overdraft_fee_if_needed(*args, **kwargs):
    """FEAT-Shell for overdraft fee application."""
    from app.feats.base import is_nested_feat
    res = _apply_overdraft_fee_if_needed(*args, **kwargs)
    if not is_nested_feat():
        db.session.commit() # FEAT-AUTHORIZED-SHELL
    else:
        db.session.flush() # FEAT-LEGACY-WRAP: parent owns commit
    return res


def _apply_overdraft_fee_if_needed(
    seat,
    banking_settings,
    *,
    force=False,
    idempotency_key: str | None = None,
):
    """Ledger-owned overdraft-fee command wrapper."""
    from app.feats.ledger_resolution_feat import (
        apply_resolved_ledger_plan,
        build_intended_ledger_plan,
        resolve_intended_ledger_plan,
    )

    intended_plan = build_intended_ledger_plan(
        seat_id=seat.id,
        class_id=seat.class_id,
        user_id=seat.user_id,
        debit_amount=Decimal("0.00"),
        description="Overdraft fee",
    )
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        banking_settings=banking_settings,
        idempotency_key=idempotency_key,
        force_overdraft_fee=force,
        allow_recovery_transfer=False,
    )
    result = apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        banking_settings=banking_settings,
        idempotency_key=idempotency_key,
    )
    return result.get("accepted", False), resolved_plan.overdraft_fee_amount


@feat_shell("FEAT-LED-001")
def apply_monthly_savings_interest(*args, **kwargs):
    """FEAT-Shell for monthly savings interest application."""
    from app.feats.base import is_nested_feat
    res = _apply_monthly_savings_interest(*args, **kwargs)
    if not is_nested_feat():
        db.session.commit() # FEAT-AUTHORIZED-SHELL
    else:
        db.session.flush() # FEAT-LEGACY-WRAP: parent owns commit
    return res


def _apply_monthly_savings_interest(seat, *, annual_rate=Decimal("0.045")):
    """Command to post monthly savings interest through the ledger authority."""
    if not seat:
        return None

    # V2 Temporal Model: INTEREST IS CLASS-SCOPED
    # Use class timezone for month/year resolution
    from app.utils.time import get_class_now
    now = get_class_now(seat.class_id)
    this_month = now.month
    this_year = now.year

    # Check for existing interest this month
    for tx in seat.transactions:
        tx_timestamp = ensure_utc(tx.timestamp)
        # Convert UTC timestamp to class time for comparison
        from app.utils.time import to_class_time
        tx_class_time = to_class_time(tx_timestamp, seat.class_id)
        
        if (
            tx.account_type == "savings"
            and tx.description == "Monthly Savings Interest"
            and tx_class_time.month == this_month
            and tx_class_time.year == this_year
            and not tx.is_void
        ):
            return None

    eligible_balance = Decimal("0.00")
    for tx in seat.transactions:
        if tx.account_type != "savings" or tx.is_void or tx.amount is None:
            continue
        if tx.amount <= Decimal("0.00"):
            continue
        if tx.type == "Interest" or "Interest" in (tx.description or ""):
            continue
            
        available_at = ensure_utc(tx.date_funds_available)
        if available_at and (now - to_class_time(available_at, seat.class_id)).days >= 30:
            eligible_balance += _quantize_currency(tx.amount)

    current_savings_balance = get_posted_balance(seat.id, seat.class_id, "savings")
    eligible_balance = min(eligible_balance, current_savings_balance)

    monthly_rate = annual_rate / Decimal("12")
    interest = _quantize_currency(eligible_balance * monthly_rate)
    if interest <= Decimal("0.00"):
        return None

    return create_pending_transaction(
        seat_id=seat.id,
        class_id=seat.class_id,
        user_id=seat.user_id,
        amount=interest,
        account_type="savings",
        type="Interest",
        description="Monthly Savings Interest",
    )
