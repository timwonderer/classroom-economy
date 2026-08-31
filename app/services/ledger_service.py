from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.extensions import db
from app.models import LedgerBalanceSnapshot, LedgerMechanism, Seat, Transaction, TransactionStatus, ClassEconomy, _quantize_currency
from app.utils.seat_scope import transaction_scope_filter
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now
from app.utils.transaction_idempotency import create_idempotent_transaction
from app.feats.base import audit_protected
from app.services.class_configuration_query_service import get_current_economic_engine

# Protected fields captured in the audit payload for every ledger write
_TRANSACTION_AUDIT_FIELDS = [
    "amount", "account_type", "type", "status",
    "class_id", "seat_id", "target_seat_id", "actor_seat_id",
    "mechanism", "description", "correlation_id",
]


def _non_void_filter():
    return Transaction.is_void.isnot(True)


# --- Ledger provenance classifier (SPEC-ITR-001 §6.3) ----------------------
#
# The Interpretation domain classifies ledger rows by origin without ever
# consulting ``Transaction.type`` (INV-ITR-015). A row is *student-originated*
# iff it is a self-mechanism, non-reversal, non-void row whose ``feat_code`` is
# NOT one of the system-originated FEATs enumerated below. SPEC-ITR-001 §6.6
# defers the concrete enumeration to the implementing surface; the Ledger domain
# owns the provenance of its own rows, so the set lives here.
#
# Categories (SPEC-ITR-001 §6.3): payroll accrual, interest accrual, obligation
# assessment, admin adjustment, ledger resolution. Student-agency FEATs
# (FEAT-STOR-001 purchase, FEAT-OBL-001 rent self-payment, transfers) are
# deliberately excluded so those acts remain student-originated.
SYSTEM_ORIGINATED_FEAT_CODES: frozenset[str] = frozenset(
    {
        # payroll accrual
        "FEAT-LED-004",   # Payroll Execution
        "FEAT-PROD-003",  # Record Payroll Event
        # interest accrual / ledger resolution (Ledger authority posts these)
        "FEAT-LED-000",   # Canonical Monetary Resolution
        "FEAT-LED-003",   # Settlement Sweep
        # system-imposed fees
        "FEAT-LED-001",   # Overdraft/NSF Fee Application
        # obligation assessment (scheduled cycles, not self-payment)
        "FEAT-OBL-002",   # Scheduled Rent Cycle
        "FEAT-OBL-003",   # Scheduled Insurance Cycle
        # admin adjustment
        "FEAT-ADMN-001",  # Bulk administration
    }
)


def _student_originated_filter():
    """SQLAlchemy predicate for the §6.3 student-originated ledger classifier."""
    return db.and_(
        Transaction.mechanism == LedgerMechanism.SELF,
        Transaction.original_transaction_id.is_(None),
        Transaction.is_void.isnot(True),
        db.or_(
            Transaction.feat_code.is_(None),
            Transaction.feat_code.notin_(SYSTEM_ORIGINATED_FEAT_CODES),
        ),
    )


def get_seat_ids_with_student_originated_activity(
    class_id: str, window_start, window_end
) -> set[int]:
    """Return seat ids with ≥1 student-originated ledger row in ``[start, end)``.

    Read-only Ledger surface consumed by the Interpretation domain
    (SPEC-ITR-001 §6.2 first source, §6.3 classifier). Scoped by ``class_id``
    (multi-tenancy) and the half-open completed-cycle window. Uses the canonical
    ledger anchor (``Transaction.seat_id``) as the acting seat. Never consults
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return set()
    rows = (
        Transaction.query
        .with_entities(Transaction.seat_id)
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            _student_originated_filter(),
        )
        .distinct()
        .all()
    )
    return {row.seat_id for row in rows if row.seat_id is not None}


# --- Interpretation read projections (SPEC-ITR-001 §7, §10) -----------------
#
# Lightweight, read-only row projections consumed by the Interpretation compute
# layer. They carry only the fields Interpretation is permitted to classify on;
# ``Transaction.type`` is deliberately excluded (INV-ITR-015). These surfaces are
# pure reads (INV-ARC-007) exposed by the Ledger domain, which owns the
# provenance of its own rows (INV-ARC-009, INV-ITR-016).


class StudentOriginatedRow(NamedTuple):
    """One student-originated ledger row (§6.3), projected for Q2 aggregation."""

    seat_id: int | None
    amount_cents: int


class InboundLedgerRow(NamedTuple):
    """One inbound-to-seat ledger row, projected for Q5 income-origin classification.

    ``mechanism`` is normalized to its lowercase string value (``self`` /
    ``teacher`` / ``system``) so the interpretation classifier operates on plain
    data rather than an ORM enum.
    """

    transaction_id: int
    seat_id: int | None
    amount_cents: int
    feat_code: str | None
    correlation_id: str | None
    original_transaction_id: int | None
    mechanism: str | None
    account_type: str | None


def _mechanism_value(mechanism) -> str | None:
    """Normalize a stored mechanism (enum member or string) to its lowercase value."""
    if mechanism is None:
        return None
    value = getattr(mechanism, "value", mechanism)
    return str(value).lower()


def get_student_originated_rows(
    class_id: str, window_start, window_end
) -> list[StudentOriginatedRow]:
    """Return student-originated ledger rows (§6.3) in ``[start, end)``.

    Read-only Ledger surface for Q2 (SPEC-ITR-001 §7.3). Applies the same §6.3
    student-originated classifier as :func:`get_seat_ids_with_student_originated_activity`,
    but projects the per-row ``amount_cents`` so Q2-C1 (frequency) and Q2-C2
    (monetary volume) can be computed from a single scoped read. Never consults
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return []
    rows = (
        Transaction.query
        .with_entities(Transaction.seat_id, Transaction.amount_cents)
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            _student_originated_filter(),
        )
        .all()
    )
    return [
        StudentOriginatedRow(seat_id=row.seat_id, amount_cents=int(row.amount_cents or 0))
        for row in rows
    ]


def get_inbound_ledger_rows(
    class_id: str, window_start, window_end
) -> list[InboundLedgerRow]:
    """Return inbound-to-seat (positive-amount), non-void ledger rows in ``[start, end)``.

    Read-only Ledger surface for Q5 income composition (SPEC-ITR-001 §10.3). An
    inbound row is a credit to the canonical anchor seat (``amount_cents > 0``;
    the model documents positive amounts as inbound). Classification into the six
    §10.2 origin categories is performed by the Interpretation domain
    (``income_origin``) using the projected provenance fields — never
    ``Transaction.type`` (INV-ITR-015).
    """
    if not class_id or window_start is None or window_end is None:
        return []
    rows = (
        Transaction.query
        .with_entities(
            Transaction.id,
            Transaction.seat_id,
            Transaction.amount_cents,
            Transaction.feat_code,
            Transaction.correlation_id,
            Transaction.original_transaction_id,
            Transaction.mechanism,
            Transaction.account_type,
        )
        .filter(
            Transaction.class_id == class_id,
            Transaction.timestamp >= ensure_utc(window_start),
            Transaction.timestamp < ensure_utc(window_end),
            Transaction.amount_cents > 0,
            Transaction.is_void.isnot(True),
        )
        .all()
    )
    return [
        InboundLedgerRow(
            transaction_id=row.id,
            seat_id=row.seat_id,
            amount_cents=int(row.amount_cents or 0),
            feat_code=row.feat_code,
            correlation_id=row.correlation_id,
            original_transaction_id=row.original_transaction_id,
            mechanism=_mechanism_value(row.mechanism),
            account_type=row.account_type,
        )
        for row in rows
    ]


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


def resolve_class_authority_seat_id(class_id: str) -> int:
    """Resolve the class-level teacher seat that owns scheduled authority for a class."""
    if not class_id:
        raise ValueError("FATAL: class_id is required to resolve class authority.")
    authority_seat = (
        db.session.query(Seat)
        .filter(Seat.class_id == class_id, Seat.role == "teacher")
        .order_by(Seat.id.asc())
        .first()
    )
    if authority_seat is None:
        raise ValueError(f"FATAL: No teacher seat found for class_id={class_id}.")
    return authority_seat.id


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
    target_seat_id: int,
    actor_seat_id: int,
    mechanism: str,
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
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        class_id=class_id,
        user_id=user_id,
        amount=_quantize_currency(amount),
        account_type=account_type,
        status=TransactionStatus.PENDING,
        mechanism=mechanism,
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
    target_seat_id: int,
    actor_seat_id: int,
    mechanism: str,
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
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        mechanism=mechanism,
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
            target_seat_id=transaction.target_seat_id,
            actor_seat_id=transaction.actor_seat_id,
            mechanism=transaction.mechanism,
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
            target_seat_id=transaction.target_seat_id,
            actor_seat_id=transaction.actor_seat_id,
            mechanism=transaction.mechanism,
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
        target_seat_id=seat_id,
        actor_seat_id=seat_id,
        mechanism="self",
        user_id=user_id,
        amount=-quantized_amount,
        account_type=from_account,
        type="Withdrawal",
        description=withdraw_description,
    )
    deposit_tx = create_pending_transaction(
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=seat_id,
        actor_seat_id=seat_id,
        mechanism="self",
        user_id=user_id,
        amount=quantized_amount,
        account_type=to_account,
        type="Deposit",
        description=deposit_description,
    )
    return withdraw_tx, deposit_tx


def apply_overdraft_fee_if_needed(*args, **kwargs):
    """Execute the Ledger overdraft command; the caller owns the FEAT transaction."""
    return _apply_overdraft_fee_if_needed(*args, **kwargs)


def _apply_overdraft_fee_if_needed(
    seat,
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
    economic_engine = get_current_economic_engine(seat.class_id)
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        economic_engine=economic_engine,
        idempotency_key=idempotency_key,
        force_overdraft_fee=force,
        allow_recovery_transfer=False,
    )
    result = apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        economic_engine=economic_engine,
        idempotency_key=idempotency_key,
    )
    return result.get("accepted", False), resolved_plan.overdraft_fee_amount


def apply_monthly_savings_interest(*args, **kwargs):
    """Execute the Ledger interest command; the caller owns the FEAT transaction."""
    return _apply_monthly_savings_interest(*args, **kwargs)


def _apply_monthly_savings_interest(seat, *, annual_rate=Decimal("0.045")):
    """Command to post monthly savings interest through the ledger authority."""
    if not seat:
        return None

    # V2 Temporal Model: INTEREST IS CLASS-SCOPED
    # Use class timezone for month/year resolution via canonical resolver
    from types import SimpleNamespace
    from app.utils.canonical_temporal_resolver import (
        canonical_temporal_resolver, CLASS_LEVEL_EVALUATION,
        _get_class_timezone,
    )
    ctx = SimpleNamespace(class_id=seat.class_id)
    now_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    )
    now = now_eval.canonical_now
    now_utc = now_eval.canonical_now_utc
    this_month = now.month
    this_year = now.year
    class_tz = _get_class_timezone(seat.class_id)

    month_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_period_boundaries",
        period="month",
        reference_time_utc=now_eval.canonical_now_utc,
    )

    start_utc = month_bounds.result["boundary_start_utc"]
    end_utc = month_bounds.result["boundary_end_utc"]

    for tx in seat.transactions:
        tx_timestamp = ensure_utc(tx.timestamp)

        if (
            tx.account_type == "savings"
            and tx.description == "Monthly Savings Interest"
            and tx_timestamp is not None
            and start_utc <= tx_timestamp < end_utc
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
        available_class = available_at.astimezone(class_tz) if available_at else None
        if available_class and (now - available_class).days >= 30:
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
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        user_id=seat.user_id,
        amount=interest,
        account_type="savings",
        type="Interest",
        description="Monthly Savings Interest",
    )
