"""Shared utility functions for canonical store collective-goal management."""

from app.extensions import db
from app.models import Entitlement, EntitlementConsumption, GrantType, StoreItem, Seat
from app.utils.time import utc_now


from app.feats.base import feat_shell


@feat_shell("FEAT-STOR-003")
def process_expired_collective_goals(user_id, correlation_id=None, idempotency_key=None):
    """Expire collective goals without rewriting downstream monetary facts."""
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
        item.is_active = False

    db.session.flush()
    return len(expired_items)
