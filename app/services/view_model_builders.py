"""
View model builders for all domains.

Phase 5 canonical read layer for presentation-only aggregates.
Builds pure read models from authoritative domain facts.
Routes and templates should consume these builders rather than reconstructing
domain truth in the presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import EntitlementEvent, IdentityProfile, Seat
from app.services.entitlement_read_service import get_entitlement_status
from app.services.store_policy_resolver import StorePolicyResolver, PolicyNotFound
from app.services.class_configuration_economic_service import EconomicView


@dataclass(frozen=True)
class IdentityProfileView:
    """Phase 5 view model for seat-bound display identity."""
    seat_id: int
    class_id: str
    profile_type: str
    first_name: str
    last_name: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def last_initial(self) -> str:
        """Return first letter of last name for display."""
        return self.last_name[0] if self.last_name else ''

    @property
    def full_name(self) -> str:
        """Return full display name."""
        return f"{self.first_name} {self.last_name}"


def build_identity_profile_view(seat_id: int, class_id: str) -> IdentityProfileView | None:
    """
    Build the canonical identity profile view for a seat.

    Queries the authoritative IdentityProfile for the seat and returns
    a frozen read model for template consumption.

    Args:
        seat_id: The seat to query
        class_id: The class scope (for multi-tenancy verification)

    Returns:
        Frozen view model, or None if profile not found
    """
    profile = (
        IdentityProfile.query
        .filter_by(seat_id=seat_id, class_id=class_id)
        .first()
    )

    if not profile:
        return None

    return IdentityProfileView(
        seat_id=profile.seat_id,
        class_id=profile.class_id,
        profile_type=profile.profile_type,
        first_name=profile.first_name,
        last_name=profile.last_name,
        notes=profile.notes,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


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


@dataclass(frozen=True)
class PolicyListView:
    policy_uuid: str
    class_id: str
    product_id: int
    name: str
    description: str | None
    entitlement_type: str
    price: Decimal
    is_purchasable: bool
    supports_direct_grants: bool
    created_at: datetime | None


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
                price_per_unit = Decimal(str((representative.payload or {}).get("price_per_unit", "0.00")))
        else:
            product_name = f"Product {representative.product_id}"
            price_per_unit = Decimal(str((representative.payload or {}).get("price_per_unit", "0.00")))

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


def build_policy_list_view(class_id: str) -> list[PolicyListView]:
    """
    Build the canonical policy list for a class.

    This is pure discovery + presentation ordering only:
    - Discovery comes from StorePolicyResolver.list_store_policies(class_id)
    - Ordering is presentation-only and does not affect policy truth
    """
    policies = StorePolicyResolver.list_store_policies(class_id)
    sorted_policies = sorted(
        policies,
        key=lambda policy: (
            policy.product_id,
            policy.name or "",
            policy.policy_uuid,
        ),
    )

    return [
        PolicyListView(
            policy_uuid=policy.policy_uuid,
            class_id=policy.class_id,
            product_id=policy.product_id,
            name=policy.name or f"Product {policy.product_id}",
            description=policy.description,
            entitlement_type=policy.entitlement_type,
            price=policy.price,
            is_purchasable=policy.is_purchasable,
            supports_direct_grants=policy.supports_direct_grants,
            created_at=policy.created_at,
        )
        for policy in sorted_policies
    ]


@dataclass(frozen=True)
class StoreManagementView:
    """Phase 6-7: Canonical view model for admin store management page."""
    # Store items (owned by Store domain)
    items: list[Any]
    total_items: int
    active_items: int
    rent_managed_item_ids: set[int]

    # Store statistics (owned by Store domain)
    total_purchases: int
    pending_redemptions: list[Any]
    recent_purchases: list[Any]

    # Collective items progress (owned by Store domain)
    collective_progress_by_item: dict[int, list[dict]]

    # Class/block labels (owned by Class Configuration domain)
    class_labels_by_block: dict[str, str]

    # Redemption audit (owned by Store domain)
    audit_rows: list[dict[str, Any]]
    audit_total: int
    audit_page: int
    audit_total_pages: int
    audit_class_options: list[str]
    audit_filters: dict[str, Any] = field(default_factory=dict)

    # Feature scope (owned by Class Configuration domain)
    selected_scope: dict[str, Any] = field(default_factory=dict)
    feature_options: list[dict[str, Any]] = field(default_factory=list)

    # Economic presentation model (owned by Class Configuration domain)
    # Consumed by Store but produced by Class Configuration economic service.
    # Contains presentation concepts: pricing guidance, economy health, warnings.
    # Does NOT expose implementation details like expected_weekly_hours or CWI calculations.
    economic: EconomicView = field(default_factory=lambda: EconomicView(
        suggested_pricing_range={},
        economy_health=0,
        warnings=[],
        display_context={},
    ))


def build_store_management_view(
    items: list[Any],
    total_items: int,
    active_items: int,
    total_purchases: int,
    pending_redemptions: list[Any],
    recent_purchases: list[Any],
    class_labels_by_block: dict[str, str],
    rent_managed_item_ids: set[int],
    collective_progress_by_item: dict[int, list[dict]],
    audit_rows: list[dict[str, Any]],
    audit_total: int,
    audit_page: int,
    audit_total_pages: int,
    audit_class_options: list[str],
    economic: EconomicView | None = None,
    audit_student: str = "",
    audit_class: str = "",
    audit_action: str = "",
    audit_start_date: str = "",
    audit_end_date: str = "",
    selected_scope: dict[str, Any] | None = None,
    feature_options: list[dict[str, Any]] | None = None,
) -> StoreManagementView:
    """
    Build the canonical store management view for admin dashboard.

    Consolidates all store management data into a single frozen dataclass
    for Phase 6-7 template consumption.
    """
    return StoreManagementView(
        items=items,
        total_items=total_items,
        active_items=active_items,
        rent_managed_item_ids=rent_managed_item_ids,
        total_purchases=total_purchases,
        pending_redemptions=pending_redemptions,
        recent_purchases=recent_purchases,
        collective_progress_by_item=collective_progress_by_item,
        class_labels_by_block=class_labels_by_block,
        audit_rows=audit_rows,
        audit_total=audit_total,
        audit_page=audit_page,
        audit_total_pages=audit_total_pages,
        audit_class_options=audit_class_options,
        audit_filters={
            "student": audit_student,
            "class": audit_class,
            "action": audit_action,
            "start_date": audit_start_date,
            "end_date": audit_end_date,
        },
        selected_scope=selected_scope or {},
        feature_options=feature_options or [],
        economic=economic or EconomicView(
            suggested_pricing_range={},
            economy_health=0,
            warnings=[],
            display_context={},
        ),
    )
