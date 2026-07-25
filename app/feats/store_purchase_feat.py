"""
FEAT-STOR-001: Store Purchase and Entitlement Grant (v2.0)

The single lawful orchestration path for purchasing a configured Store
capability and granting the resulting atomic entitlements.

Coordinates:
  - canonical request context
  - Class Configuration purchase directives
  - Ledger financial resolution and posting
  - Store and Entitlements atomic grant creation

Does NOT persist: purchase quantity, remaining-use balance, mutable
purchase status, or a second purchase-authority record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.extensions import db
from app.feats.base import requires_feat_context, generate_correlation_id
from app.feats.ledger_resolution_feat import (
    apply_resolved_ledger_plan,
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
)
from app.models import Entitlement, GrantType
from app.services.context_resolver import CanonicalContext
from app.services.store_entitlement_service import (
    consume_entitlement,
    grant_entitlement,
)
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StorePurchaseResult:
    """Result of a successful FEAT-STOR-001 execution."""
    correlation_id: str
    entitlement_ids: list[str] = field(default_factory=list)
    ledger_transaction_id: int | None = None
    success_message: str = ""


class StorePurchaseError(Exception):
    """Raised when a purchase precondition or mutation fails."""
    pass


# ---------------------------------------------------------------------------
# FEAT-STOR-001 — Store Purchase and Entitlement Grant
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-STOR-001")
def execute_store_purchase(
    *,
    ctx: CanonicalContext,
    seat,
    item,
    quantity: int,
    total_price: Decimal,
    purchase_description: str,
    banking_settings,
    idempotency_key: str | None = None,
    is_instant_use: bool = False,
) -> StorePurchaseResult:
    """Execute a canonical store purchase per FEAT-STOR-001 v2.0.

    Phases:
      1. Validation (read-only)
      2. Ledger execution
      3. Atomic entitlement grants
      4. Optional instant-use consumption

    All writes are coordinated in one transaction boundary.
    """
    class_id = ctx.class_id
    correlation_id = idempotency_key or generate_correlation_id()

    # -----------------------------------------------------------------------
    # Phase 1: Read-only validation (§VI)
    # -----------------------------------------------------------------------
    if quantity < 1:
        raise StorePurchaseError("QUANTITY_NOT_ALLOWED: quantity must be >= 1")

    if total_price < Decimal("0"):
        raise StorePurchaseError("INVALID_PRICE: total_price must be >= 0")

    # -----------------------------------------------------------------------
    # Phase 2: Ledger execution (§VII.A)
    # -----------------------------------------------------------------------
    from app.services import ledger_service

    if idempotency_key:
        purchase_tx, created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=idempotency_key,
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=-total_price,
            account_type="checking",
            type="purchase",
            description=purchase_description,
        )
        if not created:
            # Idempotent replay — reconstruct result from existing grants
            existing = Entitlement.query.filter_by(correlation_id=correlation_id).all()
            return StorePurchaseResult(
                correlation_id=correlation_id,
                entitlement_ids=[e.entitlement_id for e in existing],
                ledger_transaction_id=purchase_tx.id,
                success_message=f"{item.name} purchase already recorded.",
            )
    else:
        purchase_tx = ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=-total_price,
            account_type="checking",
            type="purchase",
            description=purchase_description,
        )

    db.session.flush()

    # Ledger resolution (overdraft/recovery handling)
    if total_price > Decimal("0"):
        intended_plan = build_intended_ledger_plan(
            seat_id=seat.id,
            class_id=class_id,
            user_id=getattr(seat, "user_id", None),
            debit_amount=total_price,
            description=purchase_description,
            source_account="checking",
            target_account="store",
        )
        resolved_plan = resolve_intended_ledger_plan(
            plan=intended_plan,
            banking_settings=banking_settings,
            idempotency_key=idempotency_key or f"feat:store:purchase:{seat.id}:{class_id}:{item.id}:resolve",
            force_overdraft_fee=False,
            allow_recovery_transfer=True,
        )
        apply_resolved_ledger_plan(
            resolved_plan=resolved_plan,
            banking_settings=banking_settings,
            idempotency_key=(
                f"{idempotency_key}:overdraft"
                if idempotency_key
                else f"feat:store:purchase:{seat.id}:{class_id}:{item.id}:overdraft"
            ),
        )

    # -----------------------------------------------------------------------
    # Phase 3: Atomic entitlement grants (§VII.B)
    # -----------------------------------------------------------------------
    entitlement_ids: list[str] = []
    for _ in range(quantity):
        ent = grant_entitlement(
            entitlement_item_id=item.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            class_id=class_id,
            grant_type=GrantType.PURCHASE,
            correlation_id=correlation_id,
        )
        entitlement_ids.append(ent.entitlement_id)

    # -----------------------------------------------------------------------
    # Phase 4: Instant-use consumption if applicable (§VII.C)
    # -----------------------------------------------------------------------
    if is_instant_use:
        for eid in entitlement_ids:
            consume_entitlement(
                entitlement_id=eid,
                class_id=class_id,
                target_seat_id=seat.id,
                actor_seat_id=seat.id,
                correlation_id=correlation_id,
            )

    # -----------------------------------------------------------------------
    # Phase 5: Inventory decrement (Class Configuration concern, bridge)
    # -----------------------------------------------------------------------
    from app.services import store_service
    store_service.decrement_inventory(item, quantity)

    # Build success message
    success_message = f"You purchased {item.name}!"
    if quantity > 1:
        success_message = f"You purchased {quantity}x {item.name}!"
    if getattr(item, 'bulk_discount_enabled', False) and getattr(item, 'bulk_discount_quantity', None) and getattr(item, 'bulk_discount_percentage', None):
        if quantity >= item.bulk_discount_quantity:
            success_message += f" (Saved {item.bulk_discount_percentage}% with bulk discount!)"

    return StorePurchaseResult(
        correlation_id=correlation_id,
        entitlement_ids=entitlement_ids,
        ledger_transaction_id=purchase_tx.id,
        success_message=success_message,
    )


# ---------------------------------------------------------------------------
# FEAT-STOR-001 — Manual Grant (teacher-initiated)
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-STOR-001")
def execute_manual_grant(
    *,
    ctx: CanonicalContext,
    teacher_seat,
    target_seat,
    item,
    quantity: int,
    correlation_id: str | None = None,
) -> StorePurchaseResult:
    """Grant entitlements without monetary exchange (teacher action).

    Per DOM-STORE-001 v3.0 §VII.A, actor_seat_id is the teacher seat.
    """
    class_id = ctx.class_id
    corr = correlation_id or generate_correlation_id()

    if quantity < 1:
        raise StorePurchaseError("QUANTITY_NOT_ALLOWED: quantity must be >= 1")

    entitlement_ids: list[str] = []
    for _ in range(quantity):
        ent = grant_entitlement(
            entitlement_item_id=item.id,
            target_seat_id=target_seat.id,
            actor_seat_id=teacher_seat.id,
            class_id=class_id,
            grant_type=GrantType.MANUAL_GRANT,
            correlation_id=corr,
        )
        entitlement_ids.append(ent.entitlement_id)

    return StorePurchaseResult(
        correlation_id=corr,
        entitlement_ids=entitlement_ids,
        success_message=f"Granted {quantity}x {item.name}.",
    )


# ---------------------------------------------------------------------------
# FEAT-STOR-001 — Obligation Grant (system/obligation-initiated)
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-STOR-001")
def execute_obligation_grant(
    *,
    class_id: str,
    teacher_seat,
    target_seat,
    item,
    quantity: int,
    correlation_id: str | None = None,
) -> StorePurchaseResult:
    """Grant entitlements from an obligation lifecycle.

    Per DOM-STORE-001 v3.0 §XII.D, actor_seat_id is the teacher seat
    resolved lawfully from class authority.
    """
    corr = correlation_id or generate_correlation_id()

    if quantity < 1:
        raise StorePurchaseError("QUANTITY_NOT_ALLOWED: quantity must be >= 1")

    entitlement_ids: list[str] = []
    for _ in range(quantity):
        ent = grant_entitlement(
            entitlement_item_id=item.id,
            target_seat_id=target_seat.id,
            actor_seat_id=teacher_seat.id,
            class_id=class_id,
            grant_type=GrantType.OBLIGATION,
            correlation_id=corr,
        )
        entitlement_ids.append(ent.entitlement_id)

    return StorePurchaseResult(
        correlation_id=corr,
        entitlement_ids=entitlement_ids,
        success_message=f"Granted {quantity}x {item.name} (obligation).",
    )
