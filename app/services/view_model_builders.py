"""
Store/Entitlements read-side view model builders.

Phase 5 canonical read layer for presentation-only aggregates.
Builds pure read models from authoritative Store and Entitlement facts.
Routes and templates should consume these builders rather than reconstructing
domain truth in the presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

from app.models import EntitlementEvent
from app.services.entitlement_read_service import get_entitlement_status
from app.services.store_policy_resolver import StorePolicyResolver, PolicyNotFound


@dataclass(frozen=True)
class EntitlementListView:
    entitlement_id: str
    product_id: int
    product_name: str
    entitlement_type: str
    acquisition_type: str
    status: str
    granted_at: datetime
    consumed_at: datetime | None
    granted_by_seat_id: int


@dataclass(frozen=True)
class PurchaseHistoryView:
    purchase_date: datetime
    policy_uuid: str
    product_name: str
    quantity: int
    price_per_unit: Decimal
    total_price: Decimal
    entitlement_status: str
    correlation_id: str


def _resolve_product_name(policy_uuid: str, product_id: int) -> str:
    policy = StorePolicyResolver.resolve_store_item(policy_uuid)
    if policy.name:
        return policy.name
    if policy.product_id == product_id:
        return f"Product {product_id}"
    return f"Product {product_id}"


def build_entitlement_list_view(seat_id: int, class_id: str) -> list[EntitlementListView]:
    """
    Build the canonical entitlement list for one seat.

    Pure aggregation over immutable entitlement events plus current policy names.
    """
    granted_events = (
        EntitlementEvent.query
        .filter_by(target_seat_id=seat_id, class_id=class_id, event_type="GRANTED")
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )

    views: list[EntitlementListView] = []
    for event in granted_events:
        policy_uuid = (event.payload or {}).get("policy_uuid") if event.payload else None
        product_name = "Unknown product"
        if policy_uuid:
            try:
                product_name = _resolve_product_name(policy_uuid, event.product_id)
            except PolicyNotFound:
                product_name = f"Product {event.product_id}"

        consumed_at = (
            EntitlementEvent.query
            .filter_by(entitlement_id=event.entitlement_id, class_id=class_id, event_type="CONSUMED")
            .order_by(EntitlementEvent.timestamp.asc())
            .with_entities(EntitlementEvent.timestamp)
            .first()
        )

        views.append(
            EntitlementListView(
                entitlement_id=event.entitlement_id,
                product_id=event.product_id,
                product_name=product_name,
                entitlement_type=event.entitlement_type,
                acquisition_type=event.acquisition_type,
                status=get_entitlement_status(event.entitlement_id, class_id),
                granted_at=event.timestamp,
                consumed_at=consumed_at[0] if consumed_at else None,
                granted_by_seat_id=event.actor_seat_id,
            )
        )

    return views


def build_purchase_history_view(seat_id: int, class_id: str) -> list[PurchaseHistoryView]:
    """
    Build the canonical purchase history for one seat.

    Purchases are grouped by correlation_id so each purchase action renders once.
    """
    purchase_events = (
        EntitlementEvent.query
        .filter_by(
            target_seat_id=seat_id,
            class_id=class_id,
            event_type="GRANTED",
            acquisition_type="PURCHASE",
        )
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )

    grouped: dict[str, list[EntitlementEvent]] = {}
    for event in purchase_events:
        grouped.setdefault(event.correlation_id or event.entitlement_id, []).append(event)

    views: list[PurchaseHistoryView] = []
    for correlation_id, events in grouped.items():
        representative = events[0]
        policy_uuid = (representative.payload or {}).get("policy_uuid") if representative.payload else ""
        if policy_uuid:
            try:
                policy = StorePolicyResolver.resolve_store_item(policy_uuid)
                product_name = policy.name or f"Product {policy.product_id}"
                price_per_unit = policy.price
            except PolicyNotFound:
                product_name = f"Product {representative.product_id}"
                price_per_unit = Decimal("0.00")
        else:
            product_name = f"Product {representative.product_id}"
            price_per_unit = Decimal("0.00")

        quantity = len(events)
        total_price = price_per_unit * quantity
        entitlement_status = get_entitlement_status(representative.entitlement_id, class_id)

        views.append(
            PurchaseHistoryView(
                purchase_date=representative.timestamp,
                policy_uuid=policy_uuid or "",
                product_name=product_name,
                quantity=quantity,
                price_per_unit=price_per_unit,
                total_price=total_price,
                entitlement_status=entitlement_status,
                correlation_id=correlation_id,
            )
        )

    return views
