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

# Deterministic account order. INV-LED-009 requires a seat settlement to lock all
# applicable account snapshot rows in a fixed order, which is what keeps two
# concurrent settlements for the same seat from deadlocking on each other.
SETTLEMENT_ACCOUNT_TYPES = ("checking", "savings")


def _normalize_account_type(raw_account_type, transaction_id) -> str:
    """Coerce a transaction's account target to a canonical snapshot scope value."""
    value = getattr(raw_account_type, "value", raw_account_type)
    account_type = str(value).lower()
    if account_type in (AccountType.CHECKING.value, "checking"):
        return "checking"
    if account_type in (AccountType.SAVINGS.value, "savings"):
        return "savings"
    raise ValueError(
        f"Unknown account type '{raw_account_type}' for transaction {transaction_id}"
    )


def _lock_account_snapshot(class_id: str, seat_id: int, account_type: str):
    """Lock — or create — the snapshot row for one ``(class, seat, account)`` scope.

    Returns ``(snapshot, was_created)``. Snapshot identity is per account
    (DOM-LED-001 §2), so settlement holds one lock per account rather than a
    single row standing in for both.
    """
    def _locked():
        return (
            LedgerBalanceSnapshot.query
            .filter(
                LedgerBalanceSnapshot.class_id == class_id,
                LedgerBalanceSnapshot.seat_id == seat_id,
                LedgerBalanceSnapshot.account_type == account_type,
            )
            .with_for_update()
            .first()
        )

    snapshot = _locked()
    if snapshot:
        return snapshot, False

    try:
        with db.session.begin_nested():
            snapshot = LedgerBalanceSnapshot(
                seat_id=seat_id,
                class_id=class_id,
                account_type=account_type,
                posted_balance_cents=0,
            )
            db.session.add(snapshot)
            db.session.flush()
            return snapshot, True
    except IntegrityError:
        # uq_balance_snapshot_scope rejected a concurrent insert for this scope.
        logger.warning("Race condition creating LedgerBalanceSnapshot, retrying fetch")
        snapshot = _locked()
        if not snapshot:
            raise
        return snapshot, False


def _posted_history_cents(scope_filter, class_id: str, account_type: str) -> int:
    """Recompute one account's posted balance from ledger history (INV-LED-006)."""
    all_non_void = db.session.query(db.func.sum(Transaction.amount)).filter(
        scope_filter,
        Transaction.class_id == class_id,
        Transaction.account_type == account_type,
        Transaction.is_void == False,
    ).scalar() or Decimal('0.00')
    pending = db.session.query(db.func.sum(Transaction.amount)).filter(
        scope_filter,
        Transaction.class_id == class_id,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.account_type == account_type,
        Transaction.is_void == False,
    ).scalar() or Decimal('0.00')
    return int((all_non_void - pending) * 100)


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

def settle_balances(seat_id: int, class_id: str) -> None:
    """
    Atomic settlement of pending transactions into the balance cache.
    
    CRITICAL SAFETY GUARD:
    Raises RuntimeError if called during a read-only request (g.read_only=True).

    This function:
    1. Locks the LedgerBalanceSnapshot row for the seat/class context (creating if needed).
    2. Fetches all PENDING transactions for this context.
    3. Aggregates their amounts by account type.
    4. Updates the LedgerBalanceSnapshot with the net changes.
    5. Transitions transactions to POSTED (or VOID if marked as void).
    
    Args:
        seat_id: The ID of the seat.
        class_id: The canonical class UUID.
    """
    # Guard against write-on-read
    if getattr(g, "read_only", False):
        raise RuntimeError("Settlement attempted during read-only request context")

    try:
        resolved_seat_id = int(seat_id)
        class_row = (
            ClassEconomy.query
            .with_entities(ClassEconomy.class_id)
            .filter_by(class_id=class_id)
            .first()
        )
        if not class_row:
            raise ValueError(f"settle_balances could not resolve class_id={class_id}")
        canonical_class_id = str(class_row[0])
        seat = db.session.get(Seat, resolved_seat_id)
        if not seat or seat.class_id != canonical_class_id:
            raise ValueError("settle_balances requires a seat bound to the provided class_id")

        scope_filter = transaction_scope_filter(Transaction, resolved_seat_id)

        # 1. Lock (or Create) one LedgerBalanceSnapshot row per account
        # ---------------------------------------------------------
        # We must lock the snapshot rows to prevent concurrent settlements or
        # balance updates for the same seat/class. Locking happens in the fixed
        # SETTLEMENT_ACCOUNT_TYPES order, and the whole seat is reconciled
        # against one settlement boundary (INV-LED-009).
        snapshots = {}
        seeded_accounts = set()
        for account_type in SETTLEMENT_ACCOUNT_TYPES:
            snapshot, was_created = _lock_account_snapshot(
                canonical_class_id, resolved_seat_id, account_type
            )
            snapshots[account_type] = snapshot
            if was_created:
                seeded_accounts.add(account_type)

        # 2. Fetch PENDING transactions
        # ---------------------------------------------------------
        pending_txs = (
            Transaction.query
            .filter(
                scope_filter,
                Transaction.class_id == canonical_class_id,
                Transaction.status == TransactionStatus.PENDING,
            )
            .order_by(Transaction.timestamp)
            .with_for_update()
            .all()
        )

        # Legacy/direct-write compatibility: absorb posted rows that were written
        # outside settlement and not yet folded into the snapshot. Accounts seeded
        # below already absorbed their posted history, so only the surviving
        # accounts need this pass.
        unsettled_posted_txs = []
        absorbing_accounts = [
            account_type for account_type in SETTLEMENT_ACCOUNT_TYPES
            if account_type not in seeded_accounts
        ]
        if absorbing_accounts:
            unsettled_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.class_id == canonical_class_id,
                    Transaction.status == TransactionStatus.POSTED,
                    Transaction.account_type.in_(absorbing_accounts),
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .order_by(Transaction.timestamp)
                .with_for_update()
                .all()
            )

        # Seed newly created snapshot rows from existing posted/non-pending ledger
        # rows. This preserves balances when snapshot rows are introduced lazily.
        if seeded_accounts:
            seed_time = utc_now()
            for account_type in SETTLEMENT_ACCOUNT_TYPES:
                if account_type not in seeded_accounts:
                    continue
                snapshots[account_type].posted_balance_cents = _posted_history_cents(
                    scope_filter, canonical_class_id, account_type
                )
                snapshots[account_type].last_settlement_at = seed_time

            seeded_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.class_id == canonical_class_id,
                    Transaction.status == TransactionStatus.POSTED,
                    Transaction.account_type.in_(sorted(seeded_accounts)),
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .with_for_update()
                .all()
            )
            for tx in seeded_posted_txs:
                tx.posted_at = seed_time

        if not pending_txs and not unsettled_posted_txs:
            # Nothing to settle
            return

        deltas = {account_type: 0 for account_type in SETTLEMENT_ACCOUNT_TYPES}
        now = utc_now()
        
        cnt_posted = 0
        cnt_voided = 0
        
        for tx in pending_txs:
            # Fill missing data if needed (defensive)
            if not tx.posted_at:
                tx.posted_at = now
            
            if tx.amount_cents is None:
                # Fallback if validation missed this (should be prevented by strict creation)
                tx.amount_cents = int(tx.amount * 100)

            # Handle Void Logic for Pending
            if tx.is_void:
                # If a transaction is pending AND is_void, it means it was voided
                # before it ever posted. We simply mark it as VOID status and
                # do NOT add its amount to the ledger balance.
                tx.status = TransactionStatus.VOID
                if not tx.voided_at:
                    tx.voided_at = now
                cnt_voided += 1
                continue
            
            # Process Valid Transaction
            tx.status = TransactionStatus.POSTED

            # Account Type Check (handles string or Enum; DB stores the string)
            deltas[_normalize_account_type(tx.account_type, tx.id)] += tx.amount_cents

            cnt_posted += 1

        for tx in unsettled_posted_txs:
            if not tx.posted_at:
                tx.posted_at = now
            if tx.amount_cents is None:
                tx.amount_cents = int(tx.amount * 100)

            deltas[_normalize_account_type(tx.account_type, tx.id)] += tx.amount_cents
            cnt_posted += 1

        # 3. Update each account's snapshot against one settlement boundary
        # ---------------------------------------------------------
        for account_type in SETTLEMENT_ACCOUNT_TYPES:
            snapshots[account_type].posted_balance_cents += deltas[account_type]
            snapshots[account_type].last_settlement_at = now

        logger.info(
            "Settled balances resolved=(seat_id=%s, class_id=%s, student_id=%s): "
            "Posted %s, Voided %s. Checking Net: %s, Savings Net: %s",
            resolved_seat_id,
            canonical_class_id,
            seat.user_id,
            cnt_posted,
            cnt_voided,
            deltas["checking"],
            deltas["savings"],
        )
        
    except Exception as e:
        logger.error(
            "Error settling balances scope=(%s, %s): %s",
            seat_id,
            class_id,
            e,
        )
        raise
