"""Ledger-owned class/seat settlement service.

Settlement is the only path that assigns posting sequences and advances normalized
balance snapshots. The caller owns the FEAT transaction boundary.
"""

from decimal import Decimal
import logging
from flask import g
from sqlalchemy.exc import IntegrityError
from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus, LedgerBalanceSnapshot, AccountType, ClassEconomy, Seat
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.seat_scope import transaction_scope_filter

logger = logging.getLogger(__name__)


def settle_pending_transaction_contexts(limit: int | None = None) -> dict[str, int]:
    """
    Sweep each seat/class context with unsettled ledger activity.

    Each context is settled inside its own FEAT-LED-003 (Settlement Sweep)
    transaction boundary, so the settlement is durably committed and one
    context's failure does not stop the run. Establishing the FEAT context is
    mandatory: settlement mutates Transaction and LedgerBalanceSnapshot rows,
    and FEAT-INTEGRITY blocks any flush/commit of mutated state outside a
    verified FEAT context (see app/feats/base.py). Without this boundary the
    standalone scheduled sweep (scripts/settle_pending_transactions.py) would
    raise on the first flush and settle nothing.

    When invoked while another FEAT is already active (composed automation),
    each FEAT-LED-003 boundary nests as a savepoint under that parent, which
    owns the durable commit.
    """
    context_query = (
        db.session.query(Transaction.seat_id, Transaction.class_id)
        .filter(
            Transaction.class_id.isnot(None),
            Transaction.seat_id.isnot(None),
            db.or_(
                Transaction.status == TransactionStatus.PENDING,
                db.and_(
                    Transaction.status == TransactionStatus.POSTED,
                    Transaction.posted_at.is_(None),
                ),
            ),
        )
        .distinct()
        .order_by(Transaction.class_id.asc(), Transaction.seat_id.asc())
    )
    if limit is not None:
        context_query = context_query.limit(limit)

    settled_contexts = 0
    failed_contexts = 0

    # Materialize the contexts before iterating because each context commits
    # independently, which invalidates server-side cursors on PostgreSQL.
    pending_contexts = context_query.all()

    for seat_id, class_id in pending_contexts:
        try:
            with FEATContext(
                "FEAT-LED-003",
                idempotency_key=f"settlement-sweep:{class_id}:{seat_id}",
            ):
                settle_balances(seat_id, class_id)
            settled_contexts += 1
        except Exception:
            failed_contexts += 1
            logger.exception(
                "Settlement sweep failed for seat %s in class %s",
                seat_id,
                class_id,
            )

    return {
        "settled_contexts": settled_contexts,
        "failed_contexts": failed_contexts,
    }

def _normalize_account_type(raw_account_type, transaction_id) -> str:
    """Coerce a transaction's account target to a canonical snapshot scope value.

    ``Transaction.account_type`` is a plain ``String``, so a caller that passes
    an ``AccountType`` member instead of its value stores the *repr*
    (``"AccountType.CHECKING"``). Reading that back with a bare ``str().lower()``
    would not fail — it would mint a third snapshot scope named
    ``accounttype.checking`` and quietly strand that money outside both real
    accounts. An account this function cannot name is an error, not a new
    account.
    """
    value = getattr(raw_account_type, "value", raw_account_type)
    account_type = str(value).lower()
    if account_type in (AccountType.CHECKING.value, "checking"):
        return "checking"
    if account_type in (AccountType.SAVINGS.value, "savings"):
        return "savings"
    raise ValueError(
        f"Unknown account type '{raw_account_type}' for transaction {transaction_id}"
    )


def _posted_history_cents(class_id: str, seat_id: int, account_type: str) -> int:
    """Recompute one account's posted balance from ledger history (INV-LED-006).

    Used only when a snapshot row is created lazily. Seeding at zero would be
    correct only if a missing snapshot implied a seat with no posted history —
    it does not. `get_posted_balance` falls back to aggregating the ledger
    exactly while no snapshot exists; the moment settlement inserts a zero row
    that fallback stops firing, and the seat's prior posted balance disappears
    from every read. The snapshot is a projection (INV-LED-006), so a new row
    must be born holding what the history already says.
    """
    total = db.session.query(db.func.sum(Transaction.amount_cents)).filter(
        Transaction.class_id == class_id,
        Transaction.seat_id == seat_id,
        Transaction.account_type == account_type,
        Transaction.status == TransactionStatus.POSTED,
        Transaction.is_void.isnot(True),
    ).scalar()
    return int(total or 0)


def settle_balances(seat_id: int, class_id: str) -> None:
    """Atomically post one seat's pending Ledger effects into canonical snapshots."""
    if getattr(g, "read_only", False):
        raise RuntimeError("Settlement attempted during read-only request context")
    seat = db.session.get(Seat, int(seat_id))
    if not seat or str(seat.class_id) != str(class_id):
        raise ValueError("settle_balances requires a seat bound to the provided class_id")

    # The class row serializes posting-sequence allocation for this class.
    db.session.query(ClassEconomy).filter(ClassEconomy.class_id == class_id).with_for_update().one()
    pending = (
        Transaction.query.filter(
            Transaction.class_id == class_id,
            Transaction.seat_id == seat_id,
            Transaction.status == TransactionStatus.PENDING,
        )
        .order_by(Transaction.account_type.asc(), Transaction.id.asc())
        .with_for_update()
        .all()
    )
    if not pending:
        return

    account_types = sorted({_normalize_account_type(tx.account_type, tx.id) for tx in pending})
    snapshots = {}
    for account_type in account_types:
        snapshot = (
            LedgerBalanceSnapshot.query.filter_by(
                class_id=class_id, seat_id=seat_id, account_type=account_type
            ).with_for_update().first()
        )
        if snapshot is None:
            snapshot = LedgerBalanceSnapshot(
                class_id=class_id, seat_id=seat_id, account_type=account_type,
                posted_balance_cents=_posted_history_cents(class_id, seat_id, account_type),
                reconciled_through_posting_sequence=None,
            )
            db.session.add(snapshot)
            db.session.flush()
        snapshots[account_type] = snapshot

    next_sequence = db.session.query(db.func.coalesce(db.func.max(Transaction.posting_sequence), 0)).filter(
        Transaction.class_id == class_id
    ).scalar()
    now = utc_now()
    for tx in pending:
        account_type = _normalize_account_type(tx.account_type, tx.id)
        if tx.is_void:
            tx.status = TransactionStatus.VOID
            tx.voided_at = tx.voided_at or now
            continue
        next_sequence = int(next_sequence) + 1
        tx.status = TransactionStatus.POSTED
        tx.posted_at = tx.posted_at or now
        tx.posting_sequence = next_sequence
        snapshot = snapshots[account_type]
        snapshot.posted_balance_cents += int(tx.amount_cents or 0)
        snapshot.reconciled_through_posting_sequence = next_sequence
        snapshot.last_settlement_at = now
        snapshot.updated_at = now
