"""Shared utility functions for canonical store collective-goal management."""

from app.extensions import db
from app.models import StoreItem, StorePurchase, Transaction, Seat
from app.services import ledger_service
from app.utils.time import utc_now


def refund_pending_collective_purchases(item, description_suffix="Goal Expired"):
    """Refund all pending canonical purchases for a collective goal item."""
    pending_purchases = StorePurchase.query.filter(
        StorePurchase.store_item_id == item.id,
        StorePurchase.status == 'pending',
        StorePurchase.collective_goal_instance_code == item.collective_goal_instance_code,
    ).all()

    refunded = 0
    for purchase in pending_purchases:
        purchase_tx = None
        if purchase.ledger_tx_id:
            purchase_tx = db.session.get(Transaction, purchase.ledger_tx_id)
        if purchase_tx and (
            purchase_tx.seat_id != purchase.seat_id
            or purchase_tx.class_id != item.class_id
        ):
            purchase_tx = None

        if purchase_tx is None and purchase.class_id:
            purchase_tx = (
                Transaction.query
                .filter_by(
                    seat_id=purchase.seat_id,
                    class_id=item.class_id,
                    type='purchase',
                    reversal_transaction_id=None,
                )
                .filter(
                    Transaction.class_id == purchase.class_id,
                    Transaction.description.like(f"Purchase: {item.name}%"),
                )
                .order_by(Transaction.timestamp.desc())
                .first()
            )

        refund_amount = abs(purchase_tx.amount) if purchase_tx and purchase_tx.amount is not None else item.price
        refund_tx = ledger_service.create_pending_transaction(
            seat_id=purchase.seat_id,
            class_id=purchase.class_id,
            user_id=db.session.get(Seat, purchase.seat_id).user_id if purchase.seat_id else None,
            amount=refund_amount,
            account_type='checking',
            type='refund',
            original_transaction_id=purchase_tx.id if purchase_tx else None,
            description=f"Refund: {item.name} ({description_suffix})",
        )
        db.session.add(refund_tx)
        if purchase_tx:
            db.session.flush()
            purchase_tx.reversal_transaction_id = refund_tx.id

        purchase.status = 'voided'
        refunded += 1

    return refunded


from app.feats.base import feat_shell


@feat_shell("FEAT-STOR-003")
def process_expired_collective_goals(teacher_id, correlation_id=None, idempotency_key=None):
    """Expire collective goals and refund pending canonical purchases."""
    now = utc_now()
    pending_exists = db.session.query(StorePurchase.id).filter(
        StorePurchase.store_item_id == StoreItem.id,
        StorePurchase.status == 'pending',
        StorePurchase.collective_goal_instance_code == StoreItem.collective_goal_instance_code,
    ).exists()

    expired_items = StoreItem.query.filter(
        StoreItem.user_id == teacher_id,
        StoreItem.item_type == 'collective',
        StoreItem.is_active == True,
        StoreItem.collective_goal_expires_at.isnot(None),
        StoreItem.collective_goal_expires_at <= now,
        pending_exists,
    ).all()

    if not expired_items:
        return 0

    for item in expired_items:
        refund_pending_collective_purchases(item, description_suffix="Collective Goal Expired")
        item.is_active = False

    db.session.flush()
    return len(expired_items)
