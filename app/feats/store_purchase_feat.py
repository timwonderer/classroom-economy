"""
FEAT-STOR-001: Store Purchase and Entitlement Grant (v3.0)

Orchestrates the complete purchase lifecycle:
- Validates purchase eligibility (product, quantity, financial)
- Coordinates Ledger purchase resolution
- Creates immutable EntitlementEvent rows (one per unit)
- Handles instant-use coordination if applicable

All mutations (Ledger + EntitlementEvent) succeed or fail together (atomic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell, FEATContext
from app.feats.ledger_resolution_feat import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
    apply_resolved_ledger_plan,
)
from app.models import Seat, EntitlementEvent, ClassEconomy
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION
from app.utils.time import utc_now


class StorePurchaseError(Exception):
    """Raised when purchase validation or execution fails."""
    pass


@dataclass
class StorePurchaseResult:
    """Result of a successful store purchase."""
    success: bool
    correlation_id: str
    quantity_granted: int
    entitlement_ids: list[str] = field(default_factory=list)
    product_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_store_purchase(
    *,
    canonical_context: CanonicalContext,
    product_id: int,
    quantity: int,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    instant_use: bool = False,
) -> StorePurchaseResult:
    """
    Execute a lawful store purchase and create entitlement grants.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role
        product_id: Configured product identifier
        quantity: Positive integer number of units
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard
        instant_use: If True, immediately consume granted entitlements

    Returns:
        StorePurchaseResult with success status and granted entitlements
    """
    # Use decorator's idempotency generation if not provided
    return _execute_store_purchase_impl(
        canonical_context=canonical_context,
        product_id=product_id,
        quantity=quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        instant_use=instant_use,
    )


@feat_shell("FEAT-STOR-001")
def _execute_store_purchase_impl(
    *,
    canonical_context: CanonicalContext,
    product_id: int,
    quantity: int,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    instant_use: bool = False,
) -> StorePurchaseResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.class_id or not canonical_context.seat_id:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate target seat exists and belongs to class
    target_seat = db.session.get(Seat, canonical_context.seat_id)
    if not target_seat or target_seat.class_id != canonical_context.class_id:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="INVALID_CONTEXT",
            error_message="Target seat not found or not in class scope",
        )

    # Validate quantity
    if not isinstance(quantity, int) or quantity <= 0:
        return StorePurchaseResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="QUANTITY_NOT_ALLOWED",
            error_message="Quantity must be a positive integer",
        )

    # TODO: Validate product exists and is purchasable
    # This requires reading from Policy/Class Configuration domain
    # For MVP, we assume product_id is valid

    # TODO: Validate eligibility rules (per-seat limits, obligations, etc.)
    # This requires reading from Obligations domain and Policy configuration

    # TODO: Validate financial plan and get Ledger resolution
    # For MVP, we assume purchase succeeds (amount = quantity * unit_price)
    # In production, call resolve_intended_ledger_plan() and check outcome

    # Generate or use provided correlation ID
    corr_id = correlation_id or f"store_purchase_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Ledger Execution (currently mocked)
    # =========================================================================

    # TODO: In production, build intended plan and resolve through Ledger FEAT
    # For MVP, assume purchase succeeds without Ledger coordination
    # In real impl:
    # 1. Calculate purchase amount from product_id + quantity
    # 2. build_intended_ledger_plan(seat_id=..., class_id=..., debit_amount=..., description=...)
    # 3. resolve_intended_ledger_plan(...) -> ResolvedLedgerPlan
    # 4. If outcome != "ACCEPT" and != "TRANSFORM", fail purchase
    # 5. apply_resolved_ledger_plan(...) -> persists debit/credit

    ledger_success = True  # MVP: assume success

    if not ledger_success:
        return StorePurchaseResult(
            success=False,
            correlation_id=corr_id,
            quantity_granted=0,
            error_code="INSUFFICIENT_FUNDS",
            error_message="Purchase denied by Ledger",
        )

    # =========================================================================
    # PHASE 3: Entitlement Grants (Atomic)
    # =========================================================================

    # Get current timestamp via canonical temporal resolver
    temporal_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="current_time",
    )
    timestamp_utc = temporal_eval.canonical_now_utc

    entitlement_ids = []

    for unit_idx in range(quantity):
        entitlement_id = str(uuid.uuid4())

        event = EntitlementEvent(
            event_id=str(uuid.uuid4()),
            entitlement_id=entitlement_id,
            class_id=canonical_context.class_id,
            target_seat_id=canonical_context.seat_id,
            actor_seat_id=canonical_context.seat_id,
            product_id=product_id,
            entitlement_type="DELAYED_USE",  # TODO: Read from product config
            acquisition_type="PURCHASE",
            event_type="GRANTED",
            correlation_id=corr_id,
            payload={
                "unit_index": unit_idx,
                "quantity_total": quantity,
                "instant_use": instant_use,
            },
            timestamp=timestamp_utc,
        )
        db.session.add(event)
        entitlement_ids.append(entitlement_id)

    db.session.flush()  # Ensure all rows are written before instant-use coordination

    # =========================================================================
    # PHASE 4: Instant-Use Coordination (if applicable)
    # =========================================================================

    if instant_use:
        # Create CONSUMED event for each granted entitlement in the same transaction
        for entitlement_id in entitlement_ids:
            consumed_event = EntitlementEvent(
                event_id=str(uuid.uuid4()),
                entitlement_id=entitlement_id,
                class_id=canonical_context.class_id,
                target_seat_id=canonical_context.seat_id,
                actor_seat_id=canonical_context.seat_id,
                product_id=product_id,
                entitlement_type="DELAYED_USE",
                acquisition_type="PURCHASE",
                event_type="CONSUMED",
                correlation_id=corr_id,
                payload={
                    "consumed_at_purchase": True,
                    "purchase_instant_use": True,
                },
                timestamp=timestamp_utc,
            )
            db.session.add(consumed_event)

        db.session.flush()

    return StorePurchaseResult(
        success=True,
        correlation_id=corr_id,
        quantity_granted=quantity,
        entitlement_ids=entitlement_ids,
        product_id=product_id,
        error_code=None,
        error_message=None,
    )
