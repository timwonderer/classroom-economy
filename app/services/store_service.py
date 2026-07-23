from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    IdentityProfile,
    Entitlement,
    EntitlementConsumption,
    RentSettings,
    Seat,
    StorePurchase,
    StoreItem,
    StoreItemVisibility,
    ClassEconomy,
    GrantType,
)
from app.services.store_entitlement_service import grant_entitlement, list_available_entitlements
from app.utils.time import utc_now


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def is_item_visible_to_seat(store_item_id: int, seat_id: int) -> bool:
    """Check if a store item is visible to a given seat.

    No visibility rows means visible to all. Presence of rows restricts to
    those specific seats.
    """
    has_grant_rows = StoreItemVisibility.query.filter_by(store_item_id=store_item_id).first()
    if has_grant_rows is None:
        return True
    return StoreItemVisibility.query.filter_by(
        store_item_id=store_item_id,
        seat_id=seat_id,
    ).first() is not None


def set_item_visibility(store_item_id: int, seat_ids: list[int]) -> None:
    """Replace visibility grants for a store item.

    Empty list = visible to all (removes all grants).
    """
    StoreItemVisibility.query.filter_by(store_item_id=store_item_id).delete()
    for sid in set(seat_ids):
        db.session.add(StoreItemVisibility(store_item_id=store_item_id, seat_id=sid))


# ---------------------------------------------------------------------------
# Purchase record helpers
# ---------------------------------------------------------------------------


def get_purchase_count(seat_id: int, class_id: str, store_item_id: int) -> int:
    """Count canonical purchase entitlements for an item by a seat in a class."""
    return Entitlement.query.filter(
        Entitlement.target_seat_id == seat_id,
        Entitlement.class_id == class_id,
        Entitlement.entitlement_item_id == store_item_id,
        Entitlement.grant_type == GrantType.PURCHASE,
    ).count()


def get_active_rent_grant(seat_id: int, class_id: str, store_item_id: int):
    """Find an active rent-derived entitlement for a seat and item."""
    active_entitlements = list_available_entitlements(
        target_seat_id=seat_id,
        class_id=class_id,
        entitlement_item_id=store_item_id,
    )
    return active_entitlements[0] if active_entitlements else None


def create_store_item(*, user_id: int, class_id: str, **fields) -> StoreItem:
    """Create and flush a canonical store item row."""
    item = StoreItem(
        user_id=user_id,
        class_id=class_id,
        **fields,
    )
    db.session.add(item)
    db.session.flush()
    return item


def deactivate_store_item(item: StoreItem) -> StoreItem:
    """Canonical soft-delete for a store item."""
    item.is_active = False
    db.session.flush()
    return item


def create_store_item_block(*, store_item_id: int, block: str) -> None:
    """Grant visibility to all seats in the given block."""
    store_item = db.session.get(StoreItem, store_item_id)
    if not store_item or not block:
        return
    normalized_block = block.strip().upper()
    seat_ids = [
        seat_id
        for (seat_id,) in (
            db.session.query(Seat.id)
            .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
            .filter(
                ClassEconomy.class_id == store_item.class_id,
                ClassEconomy.section.isnot(None),
                ClassEconomy.section == normalized_block,
            )
            .distinct()
            .all()
        )
    ]
    if seat_ids:
        db.session.add_all([
            StoreItemVisibility(store_item_id=store_item_id, seat_id=seat_id)
            for seat_id in seat_ids
        ])


def deactivate_linked_store_item(item_id: int) -> None:
    """Deactivate a linked store item by ID if it still exists."""
    store_item = db.session.get(StoreItem, item_id)
    if store_item:
        store_item.is_active = False


def delete_rent_item(item) -> None:
    """Delete a rent settings item row."""
    db.session.delete(item)


# ---------------------------------------------------------------------------
# Rent-derived entitlement helpers
# ---------------------------------------------------------------------------


def _get_rent_linked_store_items(class_id: str) -> list[StoreItem]:
    return (
        StoreItem.query.filter(
            StoreItem.class_id == class_id,
            StoreItem.is_rent_linked.is_(True),
        )
        .order_by(StoreItem.id.asc())
        .all()
    )


def get_rent_hall_pass_grant_total_from_settings(settings: RentSettings) -> int:
    """Sum hall_pass_count from canonical rent-linked store items."""
    if not settings:
        return 0
    total = 0
    for item in _get_rent_linked_store_items(settings.class_id):
        if item.item_type == 'hall_pass' and item.hall_pass_count:
            total += item.hall_pass_count
    return total


def get_frozen_privilege_items(settings: RentSettings) -> list[dict]:
    """Return privilege-type rent-linked items from canonical store rows."""
    if not settings:
        return []
    return [
        {
            'store_item_id': item.id,
            'rent_item_type': 'privilege',
            'is_available_in_store': item.is_rent_linked,
            'purchase_duration': 'per_period',
            'use_limit': item.limit_per_student,
        }
        for item in _get_rent_linked_store_items(settings.class_id)
        if item.item_type != 'hall_pass'
    ]


def get_frozen_store_linked_items(settings: RentSettings) -> list[dict]:
    """Return all rent-linked store items from canonical store rows."""
    if not settings:
        return []
    return [
        {
            'store_item_id': item.id,
            'rent_item_type': 'hall_pass' if item.item_type == 'hall_pass' else 'privilege',
            'is_available_in_store': item.is_rent_linked,
            'purchase_duration': 'per_use' if item.limit_per_student == -1 else 'per_period',
            'use_limit': item.limit_per_student,
        }
        for item in _get_rent_linked_store_items(settings.class_id)
        if item.item_type != 'hall_pass'
    ]


def grant_rent_per_use_items_from_settings(
    *, seat, settings: RentSettings, calculate_due_dates_fn,
) -> int:
    """Grant rent-derived per-use entitlements as canonical entitlement rows."""
    per_use_items = [
        item for item in _get_rent_linked_store_items(settings.class_id)
        if item.limit_per_student is not None
    ]

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        store_item_id = pu_item.id
        existing = list_available_entitlements(
            target_seat_id=seat.id,
            class_id=seat.class_id,
            entitlement_item_id=store_item_id,
        )
        if existing:
            continue

        grant_entitlement(
            entitlement_item_id=store_item_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            class_id=seat.class_id,
            grant_type=GrantType.OBLIGATION,
        )
        granted += 1

    return granted


def get_rent_hall_pass_grant_total(rent_setting_id: int) -> int:
    settings = db.session.get(RentSettings, rent_setting_id)
    return get_rent_hall_pass_grant_total_from_settings(settings) if settings else 0


def grant_rent_per_use_items(*, seat, settings, calculate_due_dates_fn) -> int:
    """Store-owned mutation for rent-derived per-use entitlements."""
    return grant_rent_per_use_items_from_settings(
        seat=seat,
        settings=settings,
        calculate_due_dates_fn=calculate_due_dates_fn,
    )


def ensure_active_rent_per_use_grant(
    *,
    seat,
    store_item_id: int,
    use_limit: int | None,
    now=None,
    expiry_date=None,
):
    """Ensure a current rent-linked entitlement exists."""
    now = now or utc_now()
    existing = list_available_entitlements(
        target_seat_id=seat.id,
        class_id=seat.class_id,
        entitlement_item_id=store_item_id,
    )
    if existing:
        return existing[0]

    return grant_entitlement(
        entitlement_item_id=store_item_id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        class_id=seat.class_id,
        grant_type=GrantType.OBLIGATION,
    )


def record_rent_perk_purchase(
    *,
    seat,
    item,
    purchase_tx_id: int,
    active_rent_item,
    now,
):
    """Store-owned mutation for a zero-cost rent-perk purchase."""
    _ = active_rent_item
    return grant_entitlement(
        entitlement_item_id=item.id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        class_id=seat.class_id,
        grant_type=GrantType.OBLIGATION,
        correlation_id=f"rent-perk:{seat.id}:{seat.class_id}:{item.id}:{purchase_tx_id}",
    )


def record_standard_purchase_items(
    *,
    seat,
    item,
    quantity: int,
    purchase_tx_id: int,
    total_price: Decimal,
    expiry_date,
    purchase_status: str,
    idempotency_key: str | None = None,
):
    """Store-owned mutation for standard StorePurchase issuance."""
    created_purchase_ids = []

    if item.is_bundle and item.bundle_quantity is not None:
        purchase = StorePurchase(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=item.id,
            quantity=quantity,
            price_at_purchase=item.price,
            total_price=total_price,
            status=purchase_status,
            idempotency_key=idempotency_key,
            ledger_tx_id=purchase_tx_id,
            purchased_at=utc_now(),
            expiry_date=expiry_date,
            is_from_bundle=True,
            collective_goal_instance_code=item.collective_goal_instance_code if item.item_type == 'collective' else None,
        )
        db.session.add(purchase)
        db.session.flush()
        created_purchase_ids.append(purchase.id)
        return created_purchase_ids

    for i in range(quantity):
        purchase = StorePurchase(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=item.price,
            total_price=item.price,
            status=purchase_status,
            idempotency_key=f"{idempotency_key}:{i}" if idempotency_key and quantity > 1 else idempotency_key,
            ledger_tx_id=purchase_tx_id,
            purchased_at=utc_now(),
            expiry_date=expiry_date,
            is_from_bundle=False,
            collective_goal_instance_code=item.collective_goal_instance_code if item.item_type == 'collective' else None,
        )
        db.session.add(purchase)
        db.session.flush()
        created_purchase_ids.append(purchase.id)

    return created_purchase_ids


def decrement_inventory(item, quantity: int) -> None:
    if item.inventory is not None:
        item.inventory -= quantity


def unlock_collective_goal_if_ready(*, item, class_id: str) -> None:
    """Store-owned mutation for collective-goal unlock state."""
    if not class_id:
        raise ValueError("class_id is required for collective goal unlock")
    class_size = db.session.query(db.func.count(db.func.distinct(Seat.id))).filter(
        Seat.class_id == class_id,
        Seat.claimed_at.isnot(None),
    ).scalar() or 0

    terminal_ids = (
        db.session.query(EntitlementConsumption.entitlement_id)
        .filter(EntitlementConsumption.class_id == class_id)
        .subquery()
    )
    purchased_count = (
        db.session.query(db.func.count(db.func.distinct(Entitlement.target_seat_id)))
        .filter(
            Entitlement.entitlement_item_id == item.id,
            Entitlement.class_id == class_id,
            Entitlement.grant_type == GrantType.PURCHASE,
            ~Entitlement.entitlement_id.in_(db.select(terminal_ids.c.entitlement_id)),
        )
        .scalar()
        or 0
    )

    target = int(item.collective_goal_target or 0) if item.collective_goal_type == 'fixed' else class_size
    if target > 0 and purchased_count >= target:
        return
