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
- Accepts product_id (user-facing identifier)
- Resolves applicable policy for that product in the class
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
    product_id: int,
    quantity: int = 1,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> DirectGrantResult:
    """
    Execute a lawful teacher-directed entitlement grant.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        target_seat_id: Seat receiving the grant
        product_id: Configured product identifier
        quantity: Number of units to grant (default 1)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        DirectGrantResult with success status and granted entitlements
    """
    return _execute_direct_grant_impl(
        canonical_context=canonical_context,
        target_seat_id=target_seat_id,
        product_id=product_id,
        quantity=quantity,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-STOR-004")
def _execute_direct_grant_impl(
    *,
    canonical_context: CanonicalContext,
    target_seat_id: int,
    product_id: int,
    quantity: int = 1,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> DirectGrantResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
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

    # Look up applicable policy for this product_id in the class
    # Query for non-retired store_products where payload.product_id matches
    applicable_products = db.session.query(StoreProduct).filter_by(
        class_id=canonical_context.class_id,
        is_retired=False,
    ).all()

    matching_policy = None
    for sp in applicable_products:
        try:
            if sp.payload.get('product_id') == product_id:
                matching_policy = sp
                break
        except Exception:
            # Skip policies with unparseable payloads
            continue

    if not matching_policy:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="PRODUCT_NOT_AVAILABLE",
            error_message=f"Product {product_id} not found or not grantable in this class",
        )

    # Resolve and validate policy
    try:
        policy_config = StorePolicyResolver.resolve_store_item(matching_policy.policy_uuid)
    except PolicyNotFound:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_NOT_FOUND",
            error_message=f"Policy for product {product_id} not found (may have been deleted)",
        )
    except (PolicyParseError, PolicyValidationError) as e:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="POLICY_INVALID",
            error_message=f"Policy validation failed: {str(e)}",
        )

    # Validate supports_direct_grants
    if not policy_config.supports_direct_grants:
        return DirectGrantResult(
            success=False,
            correlation_id="",
            quantity_granted=0,
            error_code="GRANT_NOT_SUPPORTED",
            error_message=f"Product {product_id} does not support direct grants",
        )

    # Validate per-student limit (if configured)
    if policy_config.limit_per_student is not None:
        # Count existing entitlements for this target seat and product
        existing_count = db.session.query(EntitlementEvent).filter_by(
            class_id=canonical_context.class_id,
            target_seat_id=target_seat_id,
            product_id=product_id,
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
    corr_id = correlation_id or f"direct_grant_{uuid.uuid4().hex}"

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
            product_id=product_id,  # Product identifier (per SPEC-STORE-001)
            entitlement_type=policy_config.entitlement_type,  # Read from resolved policy
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
        product_id=product_id,
        error_code=None,
        error_message=None,
    )
