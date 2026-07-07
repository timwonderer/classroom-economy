from decimal import Decimal
import logging
from flask import g
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Transaction, TransactionStatus, BalanceCache, AccountType, ClassEconomy, Seat
from app.utils.time import utc_now
from app.utils.seat_scope import transaction_scope_filter

logger = logging.getLogger(__name__)


from app.feats.base import feat_shell

@feat_shell("FEAT-LED-003")
def settle_pending_transaction_contexts(*args, **kwargs):
    """FEAT-Shell for transaction settlement sweep."""
    return _settle_pending_transaction_contexts_legacy(*args, **kwargs)

def _settle_pending_transaction_contexts_legacy(limit: int | None = None) -> dict[str, int]:
    """
    Sweep each seat/class context with unsettled ledger activity.

    Each context is committed independently so one failure does not stop the run.
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
 
    # Materialize the contexts before iterating because the loop commits per
    # context, which invalidates server-side cursors on PostgreSQL.
    pending_contexts = context_query.all()
 
    for seat_id, class_id in pending_contexts:
        try:
            with db.session.begin_nested():
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
    1. Locks the BalanceCache row for the seat/class context (creating if needed).
    2. Fetches all PENDING transactions for this context.
    3. Aggregates their amounts by account type.
    4. Updates the BalanceCache with the net changes.
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
            .with_entities(ClassEconomy.class_id, ClassEconomy.join_code)
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
        resolved_join_code = class_row[1]
        cache_was_created = False
        # 1. Lock (or Create) BalanceCache Row
        # ---------------------------------------------------------
        # We must lock the cache row to prevent concurrent settlements
        # or balance updates for the same seat/class.
        cache = None
        cache = (
            BalanceCache.query
            .filter(
                BalanceCache.class_id == canonical_class_id,
                BalanceCache.seat_id == resolved_seat_id,
            )
            .with_for_update()
            .first()
        )
        if not cache:
            try:
                with db.session.begin_nested():
                    cache = BalanceCache(
                        seat_id=resolved_seat_id,
                        class_id=canonical_class_id,
                        join_code=resolved_join_code,
                    )
                    db.session.add(cache)
                    db.session.flush()
                    cache_was_created = True
            except IntegrityError:
                logger.warning("Race condition creating BalanceCache, retrying fetch")
                cache = (
                    BalanceCache.query
                    .filter(
                        BalanceCache.class_id == canonical_class_id,
                        BalanceCache.seat_id == resolved_seat_id,
                    )
                    .with_for_update()
                    .first()
                )
                if not cache:
                    raise

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

        # Legacy/direct-write compatibility:
        # absorb posted rows that were written outside settlement and not yet folded into cache.
        unsettled_posted_txs = []
        if not cache_was_created:
            unsettled_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.class_id == class_id,
                    Transaction.status == TransactionStatus.POSTED,
                )
                .filter(
                    Transaction.is_void == False,
                    Transaction.posted_at.is_(None),
                )
                .order_by(Transaction.timestamp)
                .with_for_update()
                .all()
            )

        # Seed a newly created cache from existing posted/non-pending ledger rows.
        # This preserves legacy balances when cache rows are introduced lazily at read time.
        if cache_was_created:
            seed_time = utc_now()
            all_checking = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.class_id == canonical_class_id,
                Transaction.account_type == 'checking',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')
            pending_checking = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.class_id == class_id,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.account_type == 'checking',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')

            all_savings = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.class_id == class_id,
                Transaction.account_type == 'savings',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')
            pending_savings = db.session.query(db.func.sum(Transaction.amount)).filter(
                scope_filter,
                Transaction.class_id == class_id,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.account_type == 'savings',
                Transaction.is_void == False,
            ).scalar() or Decimal('0.00')

            cache.posted_checking_balance_cents = int((all_checking - pending_checking) * 100)
            cache.posted_savings_balance_cents = int((all_savings - pending_savings) * 100)
            cache.last_settlement_at = seed_time

            seeded_posted_txs = (
                Transaction.query
                .filter(
                    scope_filter,
                    Transaction.class_id == class_id,
                    Transaction.status == TransactionStatus.POSTED,
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

        checking_delta_cents = 0
        savings_delta_cents = 0
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
            
            # Account Type Check (handle string or Enum)
            # Database stores string 'checking'/'savings'
            acct_type = str(tx.account_type).lower()
            if acct_type == 'checking' or acct_type == AccountType.CHECKING.value:
                checking_delta_cents += tx.amount_cents
            elif acct_type == 'savings' or acct_type == AccountType.SAVINGS.value:
                savings_delta_cents += tx.amount_cents
            else:
                raise ValueError(
                    f"Unknown account type '{tx.account_type}' for transaction {tx.id}"
                )

            cnt_posted += 1

        for tx in unsettled_posted_txs:
            if not tx.posted_at:
                tx.posted_at = now
            if tx.amount_cents is None:
                tx.amount_cents = int(tx.amount * 100)

            acct_type = str(tx.account_type).lower()
            if acct_type == 'checking' or acct_type == AccountType.CHECKING.value:
                checking_delta_cents += tx.amount_cents
            elif acct_type == 'savings' or acct_type == AccountType.SAVINGS.value:
                savings_delta_cents += tx.amount_cents
            else:
                raise ValueError(
                    f"Unknown account type '{tx.account_type}' for transaction {tx.id}"
                )
            cnt_posted += 1
            
        # 3. Update Cache
        # ---------------------------------------------------------
        cache.posted_checking_balance_cents += checking_delta_cents
        cache.posted_savings_balance_cents += savings_delta_cents
        cache.last_settlement_at = now
        
        logger.info(
            "Settled balances resolved=(seat_id=%s, class_id=%s, student_id=%s, join_code=%s): "
            "Posted %s, Voided %s. Checking Net: %s, Savings Net: %s",
            resolved_seat_id,
            canonical_class_id,
            seat.user_id,
            resolved_join_code,
            cnt_posted,
            cnt_voided,
            checking_delta_cents,
            savings_delta_cents,
        )
        
    except Exception as e:
        logger.error(
            "Error settling balances scope=(%s, %s): %s",
            seat_id,
            class_id,
            e,
        )
        raise
