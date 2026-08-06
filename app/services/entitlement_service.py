"""Entitlement service — canonical hall pass balance via EntitlementEvent.

Hall pass balance is derived from the append-only EntitlementEvent log.
No seat-level counter column exists; every read is a live aggregate.
"""

from __future__ import annotations

import secrets

from app.extensions import db
from app.models import EntitlementEvent, Seat
from app.feats.base import generate_correlation_id
from app.services.entitlement_read_service import (
    get_entitlement_balance,
    get_entitlement_lineage_terminal_event,
)
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


def _current_utc():
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
    ).canonical_now_utc


def get_hall_pass_balance(seat_id: int, class_id: str) -> int:
    """Return the derived hall pass balance for a seat in a class."""
    return get_entitlement_balance(
        seat_id=seat_id,
        class_id=class_id,
        entitlement_type="HALL_PASS",
    )


def _generate_entitlement_id() -> str:
    return f"hpent_{secrets.token_urlsafe(16)}"


def grant_hall_passes(
    seat: Seat,
    quantity: int,
    *,
    actor_seat_id: int | None = None,
    trigger_id: str | None = None,
    correlation_id: str | None = None,
    acquisition_type: str = "GRANT",
) -> int:
    """Grant hall passes by appending one EntitlementEvent per pass.

    Per DOM-STORE-001 §VII and FEAT-STOR-001 §VII.B: one event per unit,
    same correlation_id across the batch.

    Args:
        seat: Target seat receiving passes.
        quantity: Number of passes to grant (must be positive).
        actor_seat_id: Seat performing the action. Defaults to target seat.
        trigger_id: Optional trigger identifier for payload lineage.
        correlation_id: Cross-domain lineage ID. Generated if not provided.
        acquisition_type: GRANT (teacher direct), PURCHASE, or PERK (rent).
    """
    _VALID_ACQUISITION_TYPES = ("GRANT", "PURCHASE", "PERK")
    if acquisition_type not in _VALID_ACQUISITION_TYPES:
        raise ValueError(f"acquisition_type must be one of {_VALID_ACQUISITION_TYPES}")

    grant_quantity = int(quantity)
    if grant_quantity <= 0:
        raise ValueError("Hall-pass grant quantity must be positive")

    now = _current_utc()
    grant_correlation_id = correlation_id or generate_correlation_id()
    resolved_actor = actor_seat_id if actor_seat_id is not None else seat.id
    for index in range(grant_quantity):
        entitlement_id = _generate_entitlement_id()
        event = EntitlementEvent(
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=resolved_actor,
            entitlement_id=entitlement_id,
            product_id=None,
            entitlement_type="HALL_PASS",
            acquisition_type=acquisition_type,
            event_type="GRANTED",
            correlation_id=grant_correlation_id,
            payload={
                "source": "grant_hall_passes",
                "trigger_id": f"{trigger_id}:{index + 1}" if trigger_id else entitlement_id,
            },
            timestamp=now,
        )
        db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def remove_hall_passes(
    seat: Seat,
    quantity: int,
) -> int:
    """Remove available hall passes by appending REVOKED events.

    Reuses the entitlement_id from the grant being revoked to maintain
    lineage per DOM-STORE-001 §VII.
    """
    quantity_to_remove = int(quantity or 0)
    if quantity_to_remove <= 0:
        raise ValueError("Hall-pass removal quantity must be positive")

    current_balance = get_hall_pass_balance(seat.id, seat.class_id)
    if quantity_to_remove > current_balance:
        raise ValueError("Cannot remove more hall passes than the current available balance")

    remaining = quantity_to_remove
    while remaining:
        grant = _available_hall_pass_grant(seat.id, seat.class_id)
        if grant is None:
            break
        event = EntitlementEvent(
            class_id=seat.class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            entitlement_id=grant.entitlement_id,
            product_id=grant.product_id,
            entitlement_type="HALL_PASS",
            acquisition_type=grant.acquisition_type,
            event_type="REVOKED",
            correlation_id=grant.correlation_id,
            payload={
                "source": "remove_hall_passes",
            },
            timestamp=_current_utc(),
        )
        db.session.add(event)
        db.session.flush()
        remaining -= 1

    if remaining:
        raise ValueError("Unable to find enough unconsumed hall-pass entitlements to reverse")

    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def _available_hall_pass_grant(seat_id: int, class_id: str) -> EntitlementEvent | None:
    """Find the oldest exercisable hall pass grant (FIFO)."""
    grants = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_type == "HALL_PASS",
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.entitlement_id.isnot(None),
        )
        .order_by(EntitlementEvent.timestamp.asc(), EntitlementEvent.event_id.asc())
        .all()
    )
    for grant in grants:
        terminal_event = get_entitlement_lineage_terminal_event(grant.entitlement_id, class_id)
        if terminal_event is None:
            return grant
    return None


def consume_hall_pass(
    seat_id: int,
    class_id: str,
    *,
    trigger_id: str,
) -> tuple[EntitlementEvent, int]:
    """Consume one hall pass from an existing grant and return (event, balance)."""
    grant = _available_hall_pass_grant(seat_id, class_id)
    if grant is None:
        raise ValueError("No available hall-pass entitlement grant to consume")

    now = _current_utc()
    event = EntitlementEvent(
        class_id=class_id,
        target_seat_id=seat_id,
        actor_seat_id=seat_id,
        entitlement_id=grant.entitlement_id,
        product_id=grant.product_id,
        entitlement_type="HALL_PASS",
        acquisition_type=grant.acquisition_type,
        event_type="CONSUMED",
        correlation_id=grant.correlation_id,
        payload={
            "source": "consume_hall_pass",
            "trigger_id": trigger_id,
        },
        timestamp=now,
    )
    db.session.add(event)
    db.session.flush()
    return event, get_hall_pass_balance(seat_id, class_id)


def expire_rent_hall_passes(
    *,
    correlation_id: str,
    class_id: str,
    actor_seat_id: int,
) -> int:
    """Expire perk-based hall passes at rent cycle boundary.

    Per DOM-OBL-001 §IX.9: "At rent boundary, previously granted rent perks
    expire regardless of same policy UUID."
    Per DOM-STORE-001 §VIII.6: hall passes with acquisition_type=PERK get
    EXPIRED at rent period end.

    Finds all active PERK hall pass grants sharing the correlation_id from
    the rent obligation and writes EXPIRED events for each.

    Returns the count of passes expired.
    """
    grants = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.correlation_id == correlation_id,
            EntitlementEvent.entitlement_type == "HALL_PASS",
            EntitlementEvent.acquisition_type == "PERK",
            EntitlementEvent.event_type == "GRANTED",
        )
        .all()
    )

    now = _current_utc()
    expired_count = 0
    for grant in grants:
        terminal = get_entitlement_lineage_terminal_event(
            grant.entitlement_id, class_id,
        )
        if terminal is not None:
            continue
        event = EntitlementEvent(
            class_id=class_id,
            target_seat_id=grant.target_seat_id,
            actor_seat_id=actor_seat_id,
            entitlement_id=grant.entitlement_id,
            product_id=grant.product_id,
            entitlement_type="HALL_PASS",
            acquisition_type="PERK",
            event_type="EXPIRED",
            correlation_id=correlation_id,
            payload={
                "source": "expire_rent_hall_passes",
            },
            timestamp=now,
        )
        db.session.add(event)
        expired_count += 1

    if expired_count:
        db.session.flush()
    return expired_count
