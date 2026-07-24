"""
FEAT-STOR-002: Entitlement Terminal Lifecycle

Canonical Store-owned terminal lifecycle orchestration for entitlements.
This module preserves the legacy route entrypoints while routing all actual
mutation through the v3 entitlement primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import Entitlement, EntitlementConsumption, Disposition, RedemptionEvent, RedemptionEventAction, RedemptionEventSource, StorePurchase
from app.services.store_entitlement_service import consume_entitlement
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver


@dataclass
class RedemptionDispositionResult:
    disposition: str
    purchase_id: int
    redemption_event_id: str
    message: str = ""


class RedemptionDispositionError(Exception):
    pass


def _now_utc():
    return canonical_temporal_resolver(SYSTEM_LEVEL_EVALUATION, primitive="current_time").canonical_now_utc


def _resolve_class_display_label(class_id, fallback_block):
    from app.models import ClassEconomy

    if class_id:
        economy = ClassEconomy.query.filter_by(class_id=class_id).first()
        if economy:
            return economy.display_name or economy.join_code
    return fallback_block or "Unknown Class"


def record_live_redemption_event(
    *,
    purchase_id: int,
    entitlement_id: str | None,
    seat_id: int | None,
    class_id: str | None,
    action: RedemptionEventAction,
    initiated_by_user_id: int,
    seat_display_name: str,
    class_display_label: str,
    notes: Optional[str] = None,
) -> str:
    event = RedemptionEvent(
        id=str(uuid4()),
        purchase_id=purchase_id,
        entitlement_id=entitlement_id,
        seat_id=seat_id,
        class_id=class_id,
        action=action,
        source=RedemptionEventSource.LIVE,
        initiated_by_user_id=initiated_by_user_id,
        seat_display_name=seat_display_name,
        class_display_label=class_display_label,
        notes=notes if notes else None,
        timestamp=_now_utc(),
    )
    db.session.add(event)
    db.session.flush()
    return event.id


def _resolve_entitlement_for_purchase(purchase: StorePurchase) -> Entitlement | None:
    return (
        Entitlement.query.filter_by(
            target_seat_id=purchase.seat_id,
            class_id=purchase.class_id,
            entitlement_item_id=purchase.store_item_id,
        )
        .outerjoin(
            EntitlementConsumption,
            EntitlementConsumption.entitlement_id == Entitlement.entitlement_id,
        )
        .filter(EntitlementConsumption.consumption_id.is_(None))
        .order_by(Entitlement.granted_at.desc(), Entitlement.id.desc())
        .first()
    )


@requires_feat_context("FEAT-STOR-002")
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

    entitlement = _resolve_entitlement_for_purchase(purchase)
    if entitlement is None:
        raise RedemptionDispositionError("No available entitlement exists for this redemption.")

    event_id = record_live_redemption_event(
        purchase_id=purchase.id,
        entitlement_id=entitlement.entitlement_id,
        seat_id=purchase.seat_id,
        class_id=purchase.class_id,
        action=RedemptionEventAction.APPROVED,
        initiated_by_user_id=actor_user_id,
        seat_display_name=purchase.seat.identity_profile.full_name if purchase.seat and purchase.seat.identity_profile else "Unknown Seat",
        class_display_label=_resolve_class_display_label(purchase.class_id, None),
        notes=notes,
    )
    consume_entitlement(
        entitlement_id=entitlement.entitlement_id,
        class_id=purchase.class_id,
        target_seat_id=purchase.seat_id,
        actor_seat_id=purchase.seat_id,
        correlation_id=entitlement.correlation_id,
    )
    db.session.flush()
    return RedemptionDispositionResult(
        disposition="approved",
        purchase_id=purchase.id,
        redemption_event_id=event_id,
        message="Redemption approved.",
    )


@requires_feat_context("FEAT-STOR-002")
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

    entitlement = _resolve_entitlement_for_purchase(purchase)
    event_id = record_live_redemption_event(
        purchase_id=purchase.id,
        entitlement_id=entitlement.entitlement_id if entitlement else None,
        seat_id=purchase.seat_id,
        class_id=purchase.class_id,
        action=RedemptionEventAction.REJECTED,
        initiated_by_user_id=actor_user_id,
        seat_display_name=purchase.seat.identity_profile.full_name if purchase.seat and purchase.seat.identity_profile else "Unknown Seat",
        class_display_label=_resolve_class_display_label(purchase.class_id, None),
        notes=notes,
    )
    db.session.flush()
    return RedemptionDispositionResult(
        disposition="rejected",
        purchase_id=purchase.id,
        redemption_event_id=event_id,
        message="Redemption rejected. The entitlement remains available.",
    )
