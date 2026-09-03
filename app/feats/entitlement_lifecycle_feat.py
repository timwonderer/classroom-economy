from __future__ import annotations

from typing import Any

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import PendingAction


@requires_feat_context("FEAT-STOR-002")
def execute_use_item_immediate(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    product_id: int,
    entitlement_type: str,
    acquisition_type: str,
    item_type: str,
    details: str | None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Execute immediate item consumption."""
    from app.services.inventory_service import consume_entitlement

    consume_entitlement(
        entitlement_id=entitlement_id,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=target_seat_id,
        product_id=product_id,
        entitlement_type=entitlement_type,
        acquisition_type=acquisition_type,
        correlation_id=correlation_id or f"immediate_use_{entitlement_id}",
        payload={
            "outcome": "APPROVED",
            "source": "api.use_item",
            "item_type": item_type,
            "details": details,
        },
    )


@requires_feat_context("FEAT-STOR-002")
def execute_use_item_request(
    *,
    class_id: str,
    seat_id: int,
    entitlement_id: str,
    action_payload: dict[str, Any],
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Create a pending action for item use request."""
    pending_action = PendingAction(
        class_id=class_id,
        seat_id=seat_id,
        entitlement_id=entitlement_id,
        correlation_id=correlation_id or idempotency_key or f"pending_{entitlement_id}",
        authoritative_feat="FEAT-STOR-002",
        payload=action_payload,
    )
    db.session.add(pending_action)


@requires_feat_context("FEAT-STOR-002")
def execute_approve_redemption(
    *,
    entitlement: Any,
    store_item: Any,
    pending_action: PendingAction,
    ctx: Any,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Execute approval of a pending redemption."""
    from app.feats.prod import _record_hall_pass_log_impl as record_hall_pass_log_command
    from app.services.inventory_service import consume_entitlement

    if store_item.item_type == 'hall_pass':
        record_hall_pass_log_command(
            ctx=ctx,
            requested_by_seat_id=entitlement.target_seat_id,
            approved_by_seat_id=ctx.seat_id,
            destination=str((pending_action.payload or {}).get("destination") or "Hall Pass"),
            reason=str((pending_action.payload or {}).get("details") or ""),
            idempotency_key=pending_action.correlation_id,
        )
    else:
        consume_entitlement(
            entitlement_id=entitlement.entitlement_id,
            class_id=entitlement.class_id,
            target_seat_id=entitlement.target_seat_id,
            actor_seat_id=ctx.seat_id,
            product_id=entitlement.product_id,
            entitlement_type=entitlement.entitlement_type,
            acquisition_type=entitlement.acquisition_type,
            correlation_id=pending_action.correlation_id,
            payload={
                "outcome": "APPROVED",
                "source": "api.approve_redemption",
                "item_type": store_item.item_type,
                "details": (pending_action.payload or {}).get("details") or None,
            },
        )
    db.session.delete(pending_action)


@requires_feat_context("FEAT-STOR-002")
def execute_reject_redemption(
    *,
    pending_action: PendingAction,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Execute rejection of a pending redemption (delete pending action without consumption)."""
    db.session.delete(pending_action)
