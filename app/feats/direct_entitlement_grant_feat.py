"""
FEAT-STOR-004: Direct Entitlement Grant (v1.0)

Orchestrates teacher-directed entitlement grants:
- Validates teacher authority for class
- Resolves product policy and validates supports_direct_grants
- Creates immutable EntitlementEvent rows (one per granted unit)
- Handles hall-pass grants (no mutable balance)
- Handles privilege grants (teacher-directed)

No Ledger coordination needed; grants are zero-cost from teacher authority.

Architecture:
- Accepts an exact policy_uuid (no inference from product_id)
- Resolves the immutable policy by UUID via StorePolicyResolver
- Validates policy per SPEC-STORE-001
- Creates entitlements with product_id and policy_uuid references
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell
from app.models import Seat, EntitlementEvent, StoreProduct
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver, PolicyNotFound, PolicyParseError, PolicyValidationError
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION


class DirectGrantError(Exception):
    """Raised when direct grant validation or execution fails."""
    pass


@dataclass
class DirectGrantResult:
    """Result of a successful direct entitlement grant."""
    success: bool
    correlation_id: str
    quantity_granted: int
    entitlement_ids: list[str] = field(default_factory=list)
    product_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_direct_grant(
    *,
    canonical_context: CanonicalContext,
    target_seat_id: int,
    policy_uuid: str,
    quantity: int = 1,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> DirectGrantResult:
    """
    Execute a lawful teacher-directed entitlement grant.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        target_seat_id: Seat receiving the grant
        policy_uuid: Exact policy UUID to resolve and execute against (no inference)
        quantity: Number of units to grant (default 1)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        DirectGrantResult with success status and granted entitlements

    Contract: Caller is responsible for discovering which policy applies.
    This FEAT accepts the exact policy_uuid and resolves it without inference.
    """
    return _execute_direct_grant_impl(
        canonical_context=canonical_context,
        target_seat_id=target_seat_id,
        policy_uuid=policy_uuid,
        quantity=quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-STOR-004")
def _execute_direct_grant_impl(
    *,
    canonical_context: CanonicalContext,
    target_seat_id: int,
    policy_uuid: str,
    quantity: int = 1,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> DirectGrantResult:
    """
    Internal implementation wrapped in @feat_shell for context management.

    Exact resolution: accept policy_uuid and resolve without inference.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.class_id or not canonical_context.seat_id:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="TEACHER_AUTHORITY_REQUIRED",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate actor is teacher (actor_role must be "teacher")
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="TEACHER_AUTHORITY_REQUIRED",
            error_message="Only teachers can grant entitlements",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != canonical_context.class_id:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="TEACHER_AUTHORITY_REQUIRED",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate target seat exists and belongs to class
    target_seat = db.session.get(Seat, target_seat_id)
    if not target_seat or target_seat.class_id != canonical_context.class_id:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="TARGET_SEAT_NOT_FOUND",
            error_message="Target seat not found or not in class scope",
        )

    # Validate quantity
    if not isinstance(quantity, int) or quantity <= 0:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="QUANTITY_NOT_ALLOWED",
            error_message="Quantity must be a positive integer",
        )

    # =========================================================================
    # Resolve and validate product policy per SPEC-STORE-001
    # =========================================================================

    # Exact resolution: resolve supplied policy_uuid without inference.
    # Caller is responsible for discovering which policy applies.
    try:
        policy_config = StorePolicyResolver.resolve_store_item(policy_uuid)
    except PolicyNotFound:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_NOT_FOUND",
            error_message=f"Policy UUID {policy_uuid} not found (may have been deleted)",
        )
    except (PolicyParseError, PolicyValidationError) as e:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_INVALID",
            error_message=f"Policy validation failed: {str(e)}",
        )

    # Verify policy belongs to the canonical class scope
    if policy_config.class_id != canonical_context.class_id:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_SCOPE_MISMATCH",
            error_message=f"Policy UUID {policy_uuid} belongs to different class ({policy_config.class_id} vs {canonical_context.class_id})",
        )

    # Validate supports_direct_grants
    if not policy_config.supports_direct_grants:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="GRANT_NOT_SUPPORTED",
            error_message=f"Product {policy_config.product_id} does not support direct grants",
        )

    # Validate per-student limit (if configured)
    if policy_config.limit_per_student is not None:
        # Count existing GRANTED entitlements for this target seat and product
        # Product_id comes from resolved policy, not inference
        existing_count = db.session.query(EntitlementEvent).filter_by(
            class_id=canonical_context.class_id,
            target_seat_id=target_seat_id,
            product_id=policy_config.product_id,
            event_type='GRANTED',
        ).count()

        if existing_count + quantity > policy_config.limit_per_student:
            return DirectGrantResult(
                success=False,
                correlation_id="",
                quantity_granted=0,
                error_code="LIMIT_EXCEEDED",
                error_message=f"Granting {quantity} would exceed per-student limit of {policy_config.limit_per_student}",
            )

    # Generate or use provided correlation ID
    corr_id = correlation_id or idempotency_key or f"direct_grant_{uuid.uuid4().hex}"

    # Replay guard: if this exact operation already committed, return the original result.
    if idempotency_key:
        existing_events = (
            db.session.query(EntitlementEvent)
            .filter_by(
                class_id=canonical_context.class_id,
                target_seat_id=target_seat_id,
                actor_seat_id=canonical_context.seat_id,
                product_id=policy_config.product_id,
                acquisition_type="GRANT",
                event_type="GRANTED",
                correlation_id=corr_id,
            )
            .order_by(EntitlementEvent.event_id.asc())
            .all()
        )
        if existing_events:
            return DirectGrantResult(
                success=True,
                correlation_id=corr_id,
                quantity_granted=len(existing_events),
                entitlement_ids=[event.entitlement_id for event in existing_events],
                product_id=policy_config.product_id,
            )

    # =========================================================================
    # PHASE 2: Atomic Entitlement Grants
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

        # Build event payload per DOM-STORE-001
        # Contains type-specific facts about this grant event (not policy rules)
        event_payload = {
            "unit_index": unit_idx,
            "quantity_total": quantity,
            "grant_type": "teacher_direct",  # Distinguishes from PURCHASE/PERK
            "policy_uuid": policy_config.policy_uuid,  # For audit/historical reference
        }

        event = EntitlementEvent(
            event_id=str(uuid.uuid4()),
            entitlement_id=entitlement_id,
            class_id=canonical_context.class_id,
            target_seat_id=target_seat_id,
            actor_seat_id=canonical_context.seat_id,  # Teacher's seat
            product_id=policy_config.product_id,  # Product identifier from resolved policy (per SPEC-STORE-001)
            entitlement_type=policy_config.entitlement_type,  # From resolved policy
            acquisition_type="GRANT",
            event_type="GRANTED",
            correlation_id=corr_id,
            payload=event_payload,
            timestamp=timestamp_utc,
        )
        db.session.add(event)
        entitlement_ids.append(entitlement_id)

    db.session.flush()

    return DirectGrantResult(
        success=True,
        correlation_id=corr_id,
        quantity_granted=quantity,
        entitlement_ids=entitlement_ids,
        product_id=policy_config.product_id,  # From resolved policy
        error_code=None,
        error_message=None,
    )
