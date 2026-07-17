"""
FEAT-STOR-006: Redemption Disposition

Owns the canonical mutation path for resolving a pending redemption request.
The canonical store object is StorePurchase; the live audit trail is
RedemptionEvent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from flask import current_app

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import (
    RedemptionEvent,
    RedemptionEventAction,
    RedemptionEventSource,
    StorePurchase,
    Transaction,
)
from app.services.ledger_service import create_pending_transaction_idempotent
from app.utils.time import ensure_utc, utc_now, UTC_MIN
from app.utils.transaction_idempotency import store_purchase_refund_key


@dataclass
class RedemptionDispositionResult:
    disposition: str
    purchase_id: int
    redemption_event_id: str
    refund_transaction_id: Optional[int] = None
    refund_amount: Optional[Decimal] = None
    message: str = ""


class RedemptionDispositionError(Exception):
    pass


def _resolve_class_display_label(class_id, fallback_block):
    from app.models import ClassEconomy
    if class_id:
        economy = ClassEconomy.query.filter_by(class_id=class_id).first()
        if economy:
            return economy.display_name or economy.join_code
    return fallback_block or "Unknown Class"


def _write_event(*, purchase: StorePurchase, actor_user_id: int, action: str, notes: Optional[str]) -> str:
    action_map = {
        "approved": RedemptionEventAction.APPROVED,
        "rejected": RedemptionEventAction.REJECTED,
    }
    if action not in action_map:
        raise RedemptionDispositionError(f"Unsupported disposition action: {action}")

    label = _resolve_class_display_label(purchase.class_id, None)
    event = RedemptionEvent(
        id=str(uuid4()),
        purchase_id=purchase.id,
        seat_id=purchase.seat_id,
        class_id=purchase.class_id,
        action=action_map[action],
        source=RedemptionEventSource.LIVE,
        initiated_by_user_id=actor_user_id,
        seat_display_name=(purchase.seat.identity_profile.full_name if purchase.seat and purchase.seat.identity_profile else "Unknown Seat"),
        class_display_label=label,
        notes=notes if notes else None,
        timestamp=utc_now(),
    )
    db.session.add(event)
    db.session.flush()
    return event.id


def record_live_redemption_event(
    *,
    purchase_id: int,
    seat_id: int | None,
    class_id: str | None,
    action: RedemptionEventAction,
    initiated_by_user_id: int,
    seat_display_name: str,
    class_display_label: str,
    notes: Optional[str] = None,
) -> str:
    """Persist a live redemption audit event through the canonical FEAT-owned path."""
    event = RedemptionEvent(
        id=str(uuid4()),
        purchase_id=purchase_id,
        seat_id=seat_id,
        class_id=class_id,
        action=action,
        source=RedemptionEventSource.LIVE,
        initiated_by_user_id=initiated_by_user_id,
        seat_display_name=seat_display_name,
        class_display_label=class_display_label,
        notes=notes if notes else None,
        timestamp=utc_now(),
    )
    db.session.add(event)
    db.session.flush()
    return event.id


def _find_original_purchase_tx(purchase: StorePurchase):
    item_name = purchase.store_item.name if purchase.store_item else None
    if not item_name:
        return None

    candidates = (
        Transaction.query.filter_by(
            seat_id=purchase.seat_id,
            class_id=purchase.class_id,
            type="purchase",
        )
        .filter(Transaction.description.like(f"Purchase: {item_name}%"))
        .all()
    )
    if not candidates:
        return None

    if purchase.purchased_at:
        target_ts = ensure_utc(purchase.purchased_at)

        def _distance(tx):
            if not tx.timestamp:
                return float("inf")
            return abs((ensure_utc(tx.timestamp) - target_ts).total_seconds())

        return min(candidates, key=_distance)

    return max(candidates, key=lambda tx: ensure_utc(tx.timestamp) if tx.timestamp else UTC_MIN)


def _compute_refund_amount(purchase: StorePurchase, purchase_tx) -> Decimal:
    if purchase_tx and purchase_tx.amount is not None:
        total_amount = abs(purchase_tx.amount)
        quantity = purchase.quantity or 1
        if purchase_tx.description:
            match = re.search(r"\(x(\d+)\)", purchase_tx.description)
            if match:
                try:
                    parsed = int(match.group(1))
                    if parsed > 0:
                        quantity = parsed
                except ValueError:
                    pass
        return total_amount / quantity
    return purchase.price_at_purchase


@requires_feat_context("FEAT-STOR-006")
def execute_redemption_approval(
    *,
    purchase: StorePurchase,
    actor_user_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    if purchase.status != "processing":
        raise RedemptionDispositionError(
            f"StorePurchase {purchase.id} is not in 'processing' state; cannot approve."
        )

    event_id = _write_event(
        purchase=purchase,
        actor_user_id=actor_user_id,
        action="approved",
        notes=notes,
    )
    purchase.status = "completed"
    redemption_tx = (
        Transaction.query.filter_by(
            seat_id=purchase.seat_id,
            class_id=purchase.class_id,
            type="redemption",
        )
        .order_by(Transaction.timestamp.desc())
        .first()
    )
    if redemption_tx and purchase.store_item:
        redemption_tx.description = f"Redeemed: {purchase.store_item.name}"

    db.session.flush()
    return RedemptionDispositionResult(
        disposition="approved",
        purchase_id=purchase.id,
        redemption_event_id=event_id,
        message="Redemption approved.",
    )


@requires_feat_context("FEAT-STOR-006")
def execute_redemption_rejection(
    *,
    purchase: StorePurchase,
    actor_user_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    if purchase.status != "processing":
        raise RedemptionDispositionError(
            f"StorePurchase {purchase.id} is not in 'processing' state; cannot reject."
        )
    if not purchase.class_id:
        current_app.logger.error("StorePurchase %s missing class_id during refund.", purchase.id)
        raise RedemptionDispositionError("Unable to resolve class for refund.")

    event_id = _write_event(
        purchase=purchase,
        actor_user_id=actor_user_id,
        action="rejected",
        notes=notes,
    )
    purchase_tx = _find_original_purchase_tx(purchase)
    refund_amount = _compute_refund_amount(purchase, purchase_tx)
    refund_tx, _created = create_pending_transaction_idempotent(
        idempotency_key=store_purchase_refund_key(purchase.id, "redemption-rejected"),
        seat_id=purchase.seat_id,
        class_id=purchase.class_id,
        user_id=purchase.seat.user_id if purchase.seat else actor_user_id,
        amount=refund_amount,
        account_type="checking",
        type="refund",
        original_transaction_id=purchase_tx.id if purchase_tx else None,
        description=f"Refund: {purchase.store_item.name if purchase.store_item else 'Store Item'} (Redemption Rejected)",
    )
    if purchase_tx:
        purchase_tx.reversal_transaction_id = refund_tx.id

    purchase.status = "rejected"
    db.session.flush()

    return RedemptionDispositionResult(
        disposition="rejected",
        purchase_id=purchase.id,
        redemption_event_id=event_id,
        refund_transaction_id=refund_tx.id,
        refund_amount=refund_amount,
        message="Redemption rejected and refunded.",
    )
