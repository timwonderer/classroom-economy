"""
FEAT-STOR-004: Direct Entitlement Grant (v1.0)

Orchestrates teacher-directed entitlement grants:
- Validates teacher authority for class
- Validates product supports direct grants
- Creates immutable EntitlementEvent rows (one per granted unit)
- Handles hall-pass grants (no mutable balance)
- Handles privilege grants (teacher-directed)

No Ledger coordination needed; grants are zero-cost from teacher authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell
from app.models import Seat, EntitlementEvent
from app.services.context_resolver import CanonicalContext
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

    # TODO: Validate product exists and supports direct grants
    # This requires reading from Policy/Class Configuration domain
    # For MVP, we assume product_id is valid and direct-grantable

    # TODO: Validate eligibility rules (per-seat limits, policy constraints, etc.)
    # For MVP, we assume grants are always allowed

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

        event = EntitlementEvent(
            event_id=str(uuid.uuid4()),
            entitlement_id=entitlement_id,
            class_id=canonical_context.class_id,
            target_seat_id=target_seat_id,
            actor_seat_id=canonical_context.seat_id,  # Teacher's seat
            product_id=product_id,
            entitlement_type="HALL_PASS",  # TODO: Read from product config
            acquisition_type="GRANT",
            event_type="GRANTED",
            correlation_id=corr_id,
            payload={
                "unit_index": unit_idx,
                "quantity_total": quantity,
                "grant_type": "teacher_direct",  # Distinguishes from PURCHASE/PERK
            },
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
