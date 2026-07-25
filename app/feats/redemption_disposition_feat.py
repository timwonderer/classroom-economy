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
from app.models import Entitlement, RedemptionEvent, RedemptionEventAction, RedemptionEventSource
from app.services.store_entitlement_service import consume_entitlement
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver


@dataclass
class RedemptionDispositionResult:
    disposition: str
    entitlement_id: str
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
    entitlement_id: str,
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


@requires_feat_context("FEAT-STOR-002")
def execute_redemption_approval(
    *,
    entitlement: Entitlement,
    actor_user_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    seat = entitlement.target_seat
    seat_display = seat.identity_profile.full_name if seat and seat.identity_profile else "Unknown Seat"

    event_id = record_live_redemption_event(
        entitlement_id=entitlement.entitlement_id,
        seat_id=entitlement.target_seat_id,
        class_id=entitlement.class_id,
        action=RedemptionEventAction.APPROVED,
        initiated_by_user_id=actor_user_id,
        seat_display_name=seat_display,
        class_display_label=_resolve_class_display_label(entitlement.class_id, None),
        notes=notes,
    )
    consume_entitlement(
        entitlement_id=entitlement.entitlement_id,
        class_id=entitlement.class_id,
        target_seat_id=entitlement.target_seat_id,
        actor_seat_id=entitlement.target_seat_id,
        correlation_id=entitlement.correlation_id,
    )
    db.session.flush()
    return RedemptionDispositionResult(
        disposition="approved",
        entitlement_id=entitlement.entitlement_id,
        redemption_event_id=event_id,
        message="Redemption approved.",
    )


@requires_feat_context("FEAT-STOR-002")
def execute_redemption_rejection(
    *,
    entitlement: Entitlement,
    actor_user_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    seat = entitlement.target_seat
    seat_display = seat.identity_profile.full_name if seat and seat.identity_profile else "Unknown Seat"

    event_id = record_live_redemption_event(
        entitlement_id=entitlement.entitlement_id,
        seat_id=entitlement.target_seat_id,
        class_id=entitlement.class_id,
        action=RedemptionEventAction.REJECTED,
        initiated_by_user_id=actor_user_id,
        seat_display_name=seat_display,
        class_display_label=_resolve_class_display_label(entitlement.class_id, None),
        notes=notes,
    )
    db.session.flush()
    return RedemptionDispositionResult(
        disposition="rejected",
        entitlement_id=entitlement.entitlement_id,
        redemption_event_id=event_id,
        message="Redemption rejected. The entitlement remains available.",
    )
