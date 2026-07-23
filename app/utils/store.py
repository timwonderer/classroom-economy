"""Shared utility functions for canonical store collective-goal management."""

from app.extensions import db
from app.models import Entitlement, EntitlementConsumption, GrantType, StoreItem, Transaction, Seat
from app.services import ledger_service
from app.utils.time import utc_now
from app.feats.transaction_void_feat import execute_void_transaction


def refund_pending_collective_purchases(item, description_suffix="Goal Expired"):
    """Refund all pending canonical entitlements for a collective goal item."""
    terminal_ids = (
        db.session.query(EntitlementConsumption.entitlement_id)
        .filter(EntitlementConsumption.class_id == item.class_id)
        .subquery()
    )
    pending_entitlements = Entitlement.query.filter(
        Entitlement.entitlement_item_id == item.id,
        Entitlement.class_id == item.class_id,
        Entitlement.grant_type == GrantType.PURCHASE,
        ~Entitlement.entitlement_id.in_(db.select(terminal_ids.c.entitlement_id)),
    ).all()

    refunded = 0
    for entitlement in pending_entitlements:
        purchase_tx = None
        if entitlement.correlation_id:
            purchase_tx = (
                Transaction.query
                .filter(
                    Transaction.class_id == entitlement.class_id,
                    Transaction.seat_id == entitlement.target_seat_id,
                    Transaction.description.like(f"Purchase: {item.name}%"),
                )
                .order_by(Transaction.timestamp.desc())
                .first()
            )
        if purchase_tx and (
            purchase_tx.seat_id != entitlement.target_seat_id
            or purchase_tx.class_id != item.class_id
        ):
            purchase_tx = None

        if purchase_tx:
            execute_void_transaction(purchase_tx)
        else:
            refund_amount = item.price
            refund_tx = ledger_service.create_pending_transaction(
                seat_id=entitlement.target_seat_id,
                class_id=entitlement.class_id,
                target_seat_id=entitlement.target_seat_id,
                actor_seat_id=entitlement.actor_seat_id,
                mechanism="system",
                user_id=db.session.get(Seat, entitlement.target_seat_id).user_id if entitlement.target_seat_id else None,
                amount=refund_amount,
                account_type='checking',
                type='refund',
                description=f"Refund: {item.name} ({description_suffix})",
            )
            db.session.add(refund_tx)

        refunded += 1

    return refunded


from app.feats.base import feat_shell


@feat_shell("FEAT-STOR-003")
def process_expired_collective_goals(user_id, correlation_id=None, idempotency_key=None):
    """Expire collective goals and refund pending canonical entitlements."""
    now = utc_now()
    terminal_ids = (
        db.session.query(EntitlementConsumption.entitlement_id)
        .filter(EntitlementConsumption.class_id == StoreItem.class_id)
        .subquery()
    )
    pending_exists = db.session.query(Entitlement.id).filter(
        Entitlement.entitlement_item_id == StoreItem.id,
        Entitlement.grant_type == GrantType.PURCHASE,
        ~Entitlement.entitlement_id.in_(db.select(terminal_ids.c.entitlement_id)),
    ).exists()

    expired_items = StoreItem.query.filter(
        StoreItem.user_id == user_id,
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
