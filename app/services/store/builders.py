"""
Store Domain View Model Builders — Phase 1 Remediation

Converts raw store item and entitlement data into immutable, presentation-ready
view models per SPEC-UI-001 and INV-ARC-022.

All business logic for rent entitlements, pricing, and collective goal progress
is pre-computed here. Templates receive only formatted display values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Any

from app.extensions import db
from app.models import StoreItem, EntitlementEvent, RentSettings, ClassEconomy


@dataclass(frozen=True)
class CollectiveProgressView:
    """Pre-computed progress state for collective goal items."""
    item_id: int
    purchase_count: int
    target_count: int
    remaining_count: int
    progress_percent: int
    is_complete: bool
    goal_type: str  # 'fixed' or 'whole_class'
    display_expires_at: str | None  # Pre-formatted expiry date, or None


@dataclass(frozen=True)
class StoreItemCardView:
    """
    Pre-computed view model for a store item card in the browse tab.

    Eliminates all template-level rent entitlement logic (lines 30-39 of student_shop.html).
    All boolean flags and pricing state are pre-calculated.
    """
    item_id: int
    name: str
    description: str | None
    display_price: str  # Pre-formatted as "$X.XX"
    display_regular_price: str  # Pre-formatted as "$X.XX" (used in rent perk badges)
    item_type: str  # 'immediate', 'delayed', 'collective', 'hall_pass'
    inventory_available: int | None  # None means unlimited
    limit_per_student: int | None
    is_bundle: bool
    bundle_quantity: int | None
    bulk_discount_enabled: bool
    bulk_discount_quantity: int | None
    bulk_discount_percentage: float | None

    # Rent entitlement flags (pre-computed per audit violations lines 30-39)
    is_privilege_rent_item: bool
    is_per_use_rent_item: bool
    is_hall_pass_item: bool
    is_rent_perk_item: bool
    is_rent_covered: bool  # Rendered with reduced opacity if True
    has_rent_free_purchase: bool
    has_legacy_rent_free_purchase: bool
    has_any_rent_free_purchase: bool
    rent_free_units_available: int | None  # None, -1 (unlimited), or count

    # Collective goal (pre-computed per audit violations lines 100-135)
    collective_progress: CollectiveProgressView | None

    # Derived presentation state
    is_out_of_stock: bool  # inventory is not None and <= 0
    button_disabled: bool  # True if out of stock or rent covered
    button_text: str  # "Out of Stock", "Already Included", or "Purchase"

    @property
    def display_rent_perk_message(self) -> str | None:
        """Return the rent perk badge message, or None if not applicable."""
        if not self.has_any_rent_free_purchase:
            return None
        if self.rent_free_units_available == -1:
            return "Unlimited free uses"
        if self.has_legacy_rent_free_purchase:
            return "Free with paid rent"
        if self.rent_free_units_available and self.rent_free_units_available > 0:
            plural = "use" if self.rent_free_units_available == 1 else "uses"
            return f"{self.rent_free_units_available} free {plural} remaining"
        return None


@dataclass(frozen=True)
class EntitlementCardView:
    """
    Pre-computed view model for a purchased item in the My Items tab.

    Flattens ORM traversals (entitlement.store_item.*) and pre-formats all dates.
    Eliminates template-level ORM access (lines 198-234 of student_shop.html).
    """
    entitlement_id: str
    item_id: int
    item_name: str  # Flattened from ORM: entitlement.store_item.name
    item_type: str  # 'immediate', 'delayed', 'collective', 'hall_pass'
    item_description: str | None  # Flattened from ORM
    status: str  # 'purchased', 'pending', 'processing', etc.
    display_status: str  # Display label: "Ready to Use", "Pending Approval", etc.
    display_purchased_date: str  # Pre-formatted ISO timestamp or "N/A"
    display_expiry_date: str | None  # Pre-formatted as "MM/DD/YY" or None if no expiry
    has_expiry_date: bool
    redemption_prompt: str | None

    # Derived presentation state
    can_redeem_immediately: bool  # immediate items in purchased status
    can_request_redemption: bool  # delayed items in purchased status
    is_pending_approval: bool
    is_processing: bool
    is_hall_pass: bool


def build_store_item_card_view(
    item: StoreItem,
    class_id: str,
    has_paid_rent: bool,
    rent_item_types_by_store_id: dict[int, list[str]],
    rent_free_entitlement_counts: dict[int, int | None],
    collective_progress_by_item: dict[int, CollectiveProgressView] | None = None,
) -> StoreItemCardView:
    """
    Build a pre-computed view model for a store item card.

    Eliminates all {% set %} logic from template (lines 30-39, 100-135).

    Args:
        item: The StoreItem model
        class_id: Class scope for multi-tenancy
        has_paid_rent: Whether current student has paid rent
        rent_item_types_by_store_id: Dict mapping item.id to list of rent types
        rent_free_entitlement_counts: Dict mapping item.id to free use count
        collective_progress_by_item: Pre-computed collective progress, if available

    Returns:
        Frozen StoreItemCardView ready for template consumption
    """
    # Pre-compute all rent entitlement flags (audit violations lines 30-39)
    rent_item_types = rent_item_types_by_store_id.get(item.id, [])
    is_privilege_rent_item = 'privilege' in rent_item_types
    is_per_use_rent_item = 'per_use' in rent_item_types
    is_hall_pass_item = item.item_type == 'hall_pass'
    is_rent_perk_item = (not is_hall_pass_item) and (
        (len(rent_item_types) > 0) or item.is_rent_linked
    )
    is_rent_covered = (
        has_paid_rent and is_privilege_rent_item and not is_per_use_rent_item
    )

    rent_free_units_available = rent_free_entitlement_counts.get(item.id)
    has_rent_free_purchase = (
        rent_free_units_available is not None
        and (rent_free_units_available == -1 or rent_free_units_available > 0)
    )
    has_legacy_rent_free_purchase = (
        (not is_hall_pass_item)
        and has_paid_rent
        and item.is_rent_linked
        and not is_rent_covered
        and not has_rent_free_purchase
    )
    has_any_rent_free_purchase = has_rent_free_purchase or has_legacy_rent_free_purchase

    # Pre-compute pricing display (pre-formatted, no Jinja filters)
    if is_rent_covered:
        display_price = "$0.00"
    elif has_any_rent_free_purchase:
        display_price = "$0.00"
    else:
        display_price = f"${item.price:.2f}"

    display_regular_price = f"${item.price:.2f}"

    # Pre-compute inventory state
    is_out_of_stock = item.inventory is not None and item.inventory <= 0
    button_disabled = is_rent_covered or is_out_of_stock
    if is_out_of_stock:
        button_text = "Out of Stock"
    elif is_rent_covered:
        button_text = "Already Included"
    else:
        button_text = "Purchase"

    # Pre-compute collective goal progress (audit violations lines 100-135)
    collective_progress = None
    if item.item_type == 'collective' and collective_progress_by_item:
        collective_progress = collective_progress_by_item.get(item.id)

    return StoreItemCardView(
        item_id=item.id,
        name=item.name,
        description=item.description,
        display_price=display_price,
        display_regular_price=display_regular_price,
        item_type=item.item_type,
        inventory_available=item.inventory,
        limit_per_student=item.limit_per_student,
        is_bundle=item.is_bundle,
        bundle_quantity=item.bundle_quantity,
        bulk_discount_enabled=item.bulk_discount_enabled,
        bulk_discount_quantity=item.bulk_discount_quantity,
        bulk_discount_percentage=item.bulk_discount_percentage,
        is_privilege_rent_item=is_privilege_rent_item,
        is_per_use_rent_item=is_per_use_rent_item,
        is_hall_pass_item=is_hall_pass_item,
        is_rent_perk_item=is_rent_perk_item,
        is_rent_covered=is_rent_covered,
        has_rent_free_purchase=has_rent_free_purchase,
        has_legacy_rent_free_purchase=has_legacy_rent_free_purchase,
        has_any_rent_free_purchase=has_any_rent_free_purchase,
        rent_free_units_available=rent_free_units_available,
        collective_progress=collective_progress,
        is_out_of_stock=is_out_of_stock,
        button_disabled=button_disabled,
        button_text=button_text,
    )


def build_entitlement_card_view(
    entitlement: Any,
    class_id: str,
) -> EntitlementCardView:
    """
    Build a pre-computed view model for a purchased item card.

    Flattens ORM traversals and pre-formats all dates (audit violations lines 198-234).
    Accepts both EntitlementEvent models and SimpleNamespace objects from legacy routes.

    Args:
        entitlement: EntitlementEvent or SimpleNamespace with entitlement data
        class_id: Class scope for multi-tenancy

    Returns:
        Frozen EntitlementCardView ready for template consumption
    """
    # Handle SimpleNamespace objects from legacy routes
    if hasattr(entitlement, 'store_item'):
        # Legacy route object: SimpleNamespace with store_item attribute
        item = entitlement.store_item
        item_name = item.name if item else "Unknown Item"
        item_description = item.description if item else None
        item_type = item.item_type if item else "immediate"
        status = getattr(entitlement, 'status', 'purchased')
        entitlement_id = getattr(entitlement, 'id', 'unknown')
        purchase_date = getattr(entitlement, 'purchase_date', None)
        expiry_date = getattr(entitlement, 'expiry_date', None)
        item_id = item.id if item else 0
    else:
        # EntitlementEvent model
        payload = getattr(entitlement, 'payload', None) or {}
        item_name = f"Product {getattr(entitlement, 'product_id', 0)}"
        item_description = None
        item_type = getattr(entitlement, 'entitlement_type', 'immediate') or getattr(entitlement, 'acquisition_type', 'immediate')
        status = "purchased"  # Default for GRANTED events
        event_type = getattr(entitlement, 'event_type', 'GRANTED')
        if event_type == "CONSUMED":
            status = "consumed"
        elif event_type == "EXPIRED":
            status = "expired"
        elif event_type == "REVOKED":
            status = "revoked"
        entitlement_id = getattr(entitlement, 'entitlement_id', 'unknown')
        purchase_date = getattr(entitlement, 'timestamp', None)
        expiry_date = payload.get("expiry_date")
        item_id = getattr(entitlement, 'product_id', 0) or 0

    # Map status to display label
    status_labels = {
        "purchased": "Ready to Use",
        "pending": "Pending Approval",
        "processing": "Processing",
        "consumed": "Used",
        "expired": "Expired",
        "revoked": "Revoked",
    }
    display_status = status_labels.get(status, status.title())

    # Pre-format dates (eliminating strftime from template)
    display_purchased_date = (
        purchase_date.strftime("%Y-%m-%dT%H:%M:%SZ") if purchase_date else "N/A"
    )

    # Expiry date (if applicable)
    display_expiry_date = None
    has_expiry_date = False
    if expiry_date:
        try:
            # Parse if it's a string, or use directly if datetime
            if isinstance(expiry_date, str):
                expiry_dt = datetime.fromisoformat(expiry_date.replace("Z", "+00:00"))
            else:
                expiry_dt = expiry_date
            display_expiry_date = expiry_dt.strftime("%m/%d/%y")
            has_expiry_date = True
        except (ValueError, AttributeError, TypeError):
            pass

    # Derive presentation state
    is_hall_pass = item_type == "hall_pass"
    can_redeem_immediately = (
        item_type == "immediate" and status == "purchased"
    )
    can_request_redemption = (
        item_type == "delayed" and status == "purchased"
    )
    is_pending_approval = status == "pending"
    is_processing = status == "processing"

    return EntitlementCardView(
        entitlement_id=str(entitlement_id),
        item_id=int(item_id),
        item_name=item_name,
        item_type=item_type,
        item_description=item_description,
        status=status,
        display_status=display_status,
        display_purchased_date=display_purchased_date,
        display_expiry_date=display_expiry_date,
        has_expiry_date=has_expiry_date,
        redemption_prompt=None,
        can_redeem_immediately=can_redeem_immediately,
        can_request_redemption=can_request_redemption,
        is_pending_approval=is_pending_approval,
        is_processing=is_processing,
        is_hall_pass=is_hall_pass,
    )


def build_collective_progress_view(
    item: StoreItem,
    purchase_count: int,
    class_size: int | None = None,
) -> CollectiveProgressView:
    """
    Build a pre-computed view model for collective goal progress.

    Pre-computes all calculations (audit violations lines 100-135).

    Args:
        item: The StoreItem with collective_goal_type and collective_goal_target
        purchase_count: Current number of purchases for this item
        class_size: Total students in class (for 'whole_class' goals)

    Returns:
        Frozen CollectiveProgressView ready for template consumption
    """
    if item.collective_goal_type == "whole_class":
        target = class_size or 1
    elif item.collective_goal_type == "fixed":
        target = item.collective_goal_target or 1
    else:
        target = 1

    remaining = max(0, target - purchase_count)
    progress_percent = min(100, (purchase_count * 100) // target if target > 0 else 0)
    is_complete = purchase_count >= target

    # Pre-format expiry date (no strftime in template)
    display_expires_at = None
    if item.collective_goal_expires_at:
        display_expires_at = item.collective_goal_expires_at.strftime("%b %d, %Y")

    return CollectiveProgressView(
        item_id=item.id,
        purchase_count=purchase_count,
        target_count=target,
        remaining_count=remaining,
        progress_percent=progress_percent,
        is_complete=is_complete,
        goal_type=item.collective_goal_type or "fixed",
        display_expires_at=display_expires_at,
    )
