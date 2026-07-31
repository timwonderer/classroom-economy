"""
Store Service — Operational Store Item and Visibility Management (Supporting DOM-POL-001)

Utility functions for managing product catalog and visibility.

SCOPE:
- Store item CRUD (create, read, update, deactivate) — product definitions belong to Class Configuration / policy-authority surfaces
- Store item visibility (per-seat visibility rules) — visibility rules belong to Class Configuration / policy-authority surfaces
- Inventory management (decrements) — operational state
- Rent-linked store item helpers — operational queries

OUT OF SCOPE (moved to FEATs and other services):
- Entitlement grant/consumption (use FEAT-STOR-001/002/004)
- Entitlement queries (use entitlement_read_service.py, which is DOM-STORE-001)
- Purchase coordination (use FEAT-STOR-001)
- Insurance claims (use FEAT-STOR-003)

NOTE: This service is NOT part of the Store and Entitlements domain (DOM-STORE-001).
StoreItem and StoreItemVisibility definitions are class-scoped catalog definitions owned by Class Configuration / policy-authority surfaces.
Store and Entitlements owns only entitlement_events and pending_actions.
Entitlement truth flows through immutable EntitlementEvent rows in entitlement_read_service.py.
"""

from __future__ import annotations

from app.extensions import db
from app.models import (
    Seat,
    StoreItem,
    StoreItemVisibility,
    ClassEconomy,
    RentSettings,
)


# ---------------------------------------------------------------------------
# Store Item CRUD
# ---------------------------------------------------------------------------


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


def deactivate_linked_store_item(item_id: int) -> None:
    """Deactivate a linked store item by ID if it still exists."""
    store_item = db.session.get(StoreItem, item_id)
    if store_item:
        store_item.is_active = False


def delete_rent_item(item: RentSettings) -> None:
    """Delete a rent settings item row."""
    db.session.delete(item)


# ---------------------------------------------------------------------------
# Store Item Visibility
# ---------------------------------------------------------------------------


def is_item_visible_to_seat(store_item_id: int, seat_id: int) -> bool:
    """
    Check if a store item is visible to a given seat.

    No visibility rows means visible to all.
    Presence of rows restricts to those specific seats.
    """
    has_visibility_rows = StoreItemVisibility.query.filter_by(store_item_id=store_item_id).first()
    if has_visibility_rows is None:
        return True
    return StoreItemVisibility.query.filter_by(
        store_item_id=store_item_id,
        seat_id=seat_id,
    ).first() is not None


def set_item_visibility(store_item_id: int, seat_ids: list[int]) -> None:
    """
    Replace visibility grants for a store item.

    Empty list = visible to all (removes all grants).
    """
    StoreItemVisibility.query.filter_by(store_item_id=store_item_id).delete()
    for sid in set(seat_ids):
        db.session.add(StoreItemVisibility(store_item_id=store_item_id, seat_id=sid))


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


# ---------------------------------------------------------------------------
# Inventory Management
# ---------------------------------------------------------------------------


def decrement_inventory(item: StoreItem, quantity: int) -> None:
    """Decrement store item inventory."""
    if item.inventory is not None:
        item.inventory -= quantity


# ---------------------------------------------------------------------------
# Rent-Linked Store Item Helpers
# ---------------------------------------------------------------------------


def _get_rent_linked_store_items(class_id: str) -> list[StoreItem]:
    """Get all rent-linked store items for a class."""
    return (
        StoreItem.query.filter(
            StoreItem.class_id == class_id,
            StoreItem.is_rent_linked.is_(True),
        )
        .order_by(StoreItem.id.asc())
        .all()
    )


def get_rent_hall_pass_grant_total_from_settings(settings: RentSettings | None) -> int:
    """
    Sum hall_pass_count from canonical rent-linked store items.

    Returns total hall passes configured to grant from rent payments.
    """
    if not settings:
        return 0

    total = 0
    for item in _get_rent_linked_store_items(settings.class_id):
        if item.item_type == "hall_pass" and item.hall_pass_count:
            total += item.hall_pass_count
    return total


def get_rent_hall_pass_grant_total(rent_setting_id: int) -> int:
    """Wrapper to get hall pass grant total by rent settings ID."""
    settings = db.session.get(RentSettings, rent_setting_id)
    return get_rent_hall_pass_grant_total_from_settings(settings) if settings else 0


def get_frozen_privilege_items(settings: RentSettings | None) -> list[dict]:
    """
    Return privilege-type rent-linked items from canonical store rows.

    Returns a frozen view of privilege items (non-hall-pass) for UI display.
    """
    if not settings:
        return []

    return [
        {
            "store_item_id": item.id,
            "rent_item_type": "privilege",
            "is_available_in_store": item.is_rent_linked,
            "purchase_duration": "per_period",
            "use_limit": item.limit_per_student,
        }
        for item in _get_rent_linked_store_items(settings.class_id)
        if item.item_type != "hall_pass"
    ]


def get_frozen_store_linked_items(settings: RentSettings | None) -> list[dict]:
    """
    Return all rent-linked store items from canonical store rows.

    Returns a frozen view of both hall-pass and privilege items for UI display.
    """
    if not settings:
        return []

    return [
        {
            "store_item_id": item.id,
            "rent_item_type": "hall_pass" if item.item_type == "hall_pass" else "privilege",
            "is_available_in_store": item.is_rent_linked,
            "purchase_duration": "per_use" if item.limit_per_student == -1 else "per_period",
            "use_limit": item.limit_per_student,
        }
        for item in _get_rent_linked_store_items(settings.class_id)
        if item.item_type != "hall_pass"
    ]
