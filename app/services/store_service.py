from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    IdentityProfile,
    RentItem,
    RentPolicyVersion,
    Seat,
    StorePurchase,
    StoreItemVisibility,
)
from app.utils.time import utc_now


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def is_item_visible_to_seat(store_item_id: int, seat_id: int) -> bool:
    """Check if a store item is visible to a given seat.

    No visibility rows means visible to all. Presence of rows restricts to
    those specific seats.
    """
    has_grants = db.session.query(
        StoreItemVisibility.query.filter_by(store_item_id=store_item_id).exists()
    ).scalar()
    if not has_grants:
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
    for sid in seat_ids:
        db.session.add(StoreItemVisibility(store_item_id=store_item_id, seat_id=sid))


# ---------------------------------------------------------------------------
# Purchase record helpers
# ---------------------------------------------------------------------------


def get_purchase_count(seat_id: int, class_id: str, store_item_id: int) -> int:
    """Count non-voided purchases of an item by a seat in a class."""
    return StorePurchase.query.filter(
        StorePurchase.seat_id == seat_id,
        StorePurchase.class_id == class_id,
        StorePurchase.store_item_id == store_item_id,
        StorePurchase.status.notin_(['voided', 'rejected']),
    ).count()


def get_active_rent_grant(seat_id: int, class_id: str, store_item_id: int):
    """Find an active rent-derived purchase with remaining uses."""
    now = utc_now()
    return StorePurchase.query.filter(
        StorePurchase.seat_id == seat_id,
        StorePurchase.class_id == class_id,
        StorePurchase.store_item_id == store_item_id,
        db.or_(StorePurchase.uses_remaining > 0, StorePurchase.uses_remaining == -1),
        db.or_(StorePurchase.expiry_date.is_(None), StorePurchase.expiry_date > now),
    ).first()


# ---------------------------------------------------------------------------
# Rent-derived entitlement helpers
# ---------------------------------------------------------------------------


def get_rent_hall_pass_grant_total_from_version(version: RentPolicyVersion) -> int:
    """Sum hall_pass_count from the frozen manifest on a policy version."""
    total = 0
    for item in (version.frozen_items or []):
        if item.get('rent_item_type') == 'hall_pass' and item.get('hall_pass_count'):
            total += item['hall_pass_count']
    return total


def get_frozen_privilege_items(version: RentPolicyVersion) -> list[dict]:
    """Return privilege-type items from the frozen manifest that are store-linked."""
    return [
        item for item in (version.frozen_items or [])
        if item.get('rent_item_type') == 'privilege'
        and item.get('is_available_in_store')
        and item.get('purchase_duration') != 'per_use'
    ]


def get_frozen_store_linked_items(version: RentPolicyVersion) -> list[dict]:
    """Return all store-linked items from the frozen manifest (excludes hall passes)."""
    return [
        item for item in (version.frozen_items or [])
        if item.get('is_available_in_store')
        and item.get('store_item_id')
        and item.get('rent_item_type') != 'hall_pass'
    ]


def grant_rent_per_use_items_from_version(
    *, seat, version: RentPolicyVersion, calculate_due_dates_fn, settings=None,
) -> int:
    """Store-owned mutation for rent-derived per-use entitlements."""
    per_use_items = [
        item for item in (version.frozen_items or [])
        if item.get('rent_item_type') == 'per_use' and item.get('store_item_id')
    ]

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        store_item_id = pu_item['store_item_id']
        use_limit = pu_item.get('use_limit')

        existing = StorePurchase.query.filter(
            StorePurchase.seat_id == seat.id,
            StorePurchase.store_item_id == store_item_id,
            db.or_(StorePurchase.uses_remaining > 0, StorePurchase.uses_remaining == -1),
            db.or_(StorePurchase.expiry_date.is_(None), StorePurchase.expiry_date > now),
        ).first()

        if existing:
            existing.uses_remaining = use_limit if use_limit else -1
            continue

        expiry_date = None
        if settings and getattr(settings, 'first_rent_due_date', None):
            _, next_due = calculate_due_dates_fn(settings, now)
            if next_due:
                expiry_date = next_due

        db.session.add(StorePurchase(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=store_item_id,
            quantity=1,
            price_at_purchase=Decimal('0.00'),
            total_price=Decimal('0.00'),
            status='purchased',
            purchased_at=now,
            expiry_date=expiry_date,
            is_from_bundle=False,
            uses_remaining=use_limit if use_limit else -1,
        ))
        granted += 1

    return granted


def get_rent_hall_pass_grant_total(rent_setting_id: int) -> int:
    total = db.session.query(
        db.func.coalesce(db.func.sum(RentItem.hall_pass_count), 0)
    ).filter(
        RentItem.rent_setting_id == rent_setting_id,
        RentItem.rent_item_type == 'hall_pass',
    ).scalar() or 0
    return int(total)


def grant_rent_per_use_items(*, seat, settings, calculate_due_dates_fn) -> int:
    """Store-owned mutation for rent-derived per-use entitlements."""
    per_use_items = RentItem.query.filter_by(
        rent_setting_id=settings.id,
        rent_item_type='per_use',
    ).all()

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        if not pu_item.store_item_id:
            continue

        existing = StorePurchase.query.filter(
            StorePurchase.seat_id == seat.id,
            StorePurchase.store_item_id == pu_item.store_item_id,
            db.or_(StorePurchase.uses_remaining > 0, StorePurchase.uses_remaining == -1),
            db.or_(StorePurchase.expiry_date.is_(None), StorePurchase.expiry_date > now),
        ).first()

        if existing:
            existing.uses_remaining = pu_item.use_limit if pu_item.use_limit else -1
            continue

        expiry_date = None
        if settings.first_rent_due_date:
            _, next_due = calculate_due_dates_fn(settings, now)
            if next_due:
                expiry_date = next_due

        db.session.add(StorePurchase(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=pu_item.store_item_id,
            quantity=1,
            price_at_purchase=Decimal('0.00'),
            total_price=Decimal('0.00'),
            status='purchased',
            purchased_at=now,
            expiry_date=expiry_date,
            is_from_bundle=False,
            uses_remaining=pu_item.use_limit if pu_item.use_limit else -1,
        ))
        granted += 1

    return granted


def ensure_active_rent_per_use_grant(
    *,
    seat,
    store_item_id: int,
    use_limit: int | None,
    now=None,
    expiry_date=None,
):
    """Store-owned mutation for ensuring a current rent grant row exists."""
    now = now or utc_now()
    existing = StorePurchase.query.filter(
        StorePurchase.seat_id == seat.id,
        StorePurchase.store_item_id == store_item_id,
        db.or_(StorePurchase.uses_remaining > 0, StorePurchase.uses_remaining == -1),
        db.or_(StorePurchase.expiry_date.is_(None), StorePurchase.expiry_date > now),
    ).first()
    if existing:
        return existing

    granted_item = StorePurchase(
        seat_id=seat.id,
        class_id=seat.class_id,
        store_item_id=store_item_id,
        quantity=1,
        price_at_purchase=Decimal('0.00'),
        total_price=Decimal('0.00'),
        status='purchased',
        purchased_at=now,
        expiry_date=expiry_date,
        is_from_bundle=False,
        uses_remaining=use_limit if use_limit else -1,
    )
    db.session.add(granted_item)
    return granted_item


def record_rent_perk_purchase(
    *,
    seat,
    item,
    purchase_tx_id: int,
    active_rent_item,
    now,
):
    """Store-owned mutation for a zero-cost rent-perk purchase."""
    if active_rent_item and active_rent_item.uses_remaining != -1:
        active_rent_item.uses_remaining -= 1

    expiry_date = None
    if item.item_type == 'delayed' and item.auto_expiry_days:
        expiry_date = now + timedelta(days=item.auto_expiry_days)

    purchase = StorePurchase(
        seat_id=seat.id,
        class_id=seat.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=Decimal('0.00'),
        total_price=Decimal('0.00'),
        status='purchased',
        ledger_tx_id=purchase_tx_id,
        purchased_at=now,
        expiry_date=expiry_date,
        is_from_bundle=False,
        uses_remaining=None,
    )
    db.session.add(purchase)
    return purchase


def record_standard_purchase_items(
    *,
    seat,
    item,
    quantity: int,
    purchase_tx_id: int,
    total_price: Decimal,
    expiry_date,
    purchase_status: str,
    uses_remaining,
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
            bundle_remaining=item.bundle_quantity * quantity,
            uses_remaining=uses_remaining,
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
            uses_remaining=uses_remaining,
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

    purchased_count = StorePurchase.query.filter(
        StorePurchase.store_item_id == item.id,
        StorePurchase.class_id == class_id,
        StorePurchase.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
        StorePurchase.collective_goal_instance_code == item.collective_goal_instance_code,
    ).with_entities(db.func.count(db.func.distinct(StorePurchase.seat_id))).scalar() or 0

    target = int(item.collective_goal_target or 0) if item.collective_goal_type == 'fixed' else class_size
    if target > 0 and purchased_count >= target:
        pending_purchases = StorePurchase.query.filter(
            StorePurchase.store_item_id == item.id,
            StorePurchase.class_id == class_id,
            StorePurchase.status == 'pending',
            StorePurchase.collective_goal_instance_code == item.collective_goal_instance_code,
        ).all()
        for p in pending_purchases:
            p.status = "processing"
