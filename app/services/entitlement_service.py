"""Entitlement service — canonical hall pass balance via EntitlementEvent.

Hall pass balance is derived from the append-only EntitlementEvent log.
No seat-level counter column exists; every read is a live aggregate.
"""

from __future__ import annotations

import sqlalchemy as sa

from app.extensions import db
from app.models import EntitlementEvent, Seat
from app.feats.base import generate_correlation_id
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
    return max(
        0,
        db.session.query(sa.func.sum(EntitlementEvent.quantity_delta))
        .filter_by(seat_id=seat_id, class_id=class_id)
        .scalar()
        or 0,
    )


def grant_hall_passes(
    seat: Seat,
    quantity: int,
    *,
    trigger_id: str | None = None,
    correlation_id: str | None = None,
    event_type: str = "GRANT",
) -> int:
    """Grant hall passes by appending an EntitlementEvent. Returns new balance."""
    now = _current_utc()
    grant_correlation_id = correlation_id or generate_correlation_id()
    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=int(quantity),
        event_type=event_type,
        trigger_id=trigger_id or f"grant_{seat.id}_{now.isoformat()}",
        correlation_id=grant_correlation_id,
        occurred_at=now,
    )
    db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def _available_hall_pass_grant(seat_id: int, class_id: str) -> EntitlementEvent | None:
    grants = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.quantity_delta > 0,
            EntitlementEvent.correlation_id.isnot(None),
        )
        .order_by(EntitlementEvent.occurred_at.asc(), EntitlementEvent.id.asc())
        .all()
    )
    for grant in grants:
        consumed = (
            db.session.query(sa.func.coalesce(sa.func.sum(EntitlementEvent.quantity_delta), 0))
            .filter(
                EntitlementEvent.seat_id == seat_id,
                EntitlementEvent.class_id == class_id,
                EntitlementEvent.correlation_id == grant.correlation_id,
                EntitlementEvent.quantity_delta < 0,
            )
            .scalar()
            or 0
        )
        if int(grant.quantity_delta) + int(consumed) > 0:
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
        seat_id=seat_id,
        class_id=class_id,
        quantity_delta=-1,
        event_type="CONSUME",
        trigger_id=trigger_id,
        correlation_id=grant.correlation_id,
        occurred_at=now,
    )
    db.session.add(event)
    db.session.flush()
    return event, get_hall_pass_balance(seat_id, class_id)


def adjust_hall_passes(
    seat: Seat,
    delta: int,
    *,
    trigger_id: str | None = None,
) -> int:
    """Apply a signed delta (positive = grant, negative = revoke). Returns new balance.

    Used by admin set/add/subtract operations.
    """
    if delta == 0:
        return get_hall_pass_balance(seat.id, seat.class_id)
    now = _current_utc()
    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=int(delta),
        event_type="GRANT" if delta > 0 else "REVOCATION",
        trigger_id=trigger_id or f"adjust_{seat.id}_{now.isoformat()}",
        correlation_id=generate_correlation_id() if delta > 0 else None,
        occurred_at=now,
    )
    db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def reconcile_rent_hall_pass_top_off(
    *,
    seat: Seat,
    target_rent_passes: int,
) -> tuple[int, int, bool]:
    """Adjust the rent-sourced hall pass entitlement to match target_rent_passes.

    Only events with trigger_id starting with 'rent_top_off_' are included in
    the reconciliation to isolate the rent-granted portion from admin/store grants.

    Returns (passes_awarded, passes_revoked, state_changed).
    """
    current_rent_passes = max(
        0,
        db.session.query(sa.func.sum(EntitlementEvent.quantity_delta))
        .filter(
            EntitlementEvent.seat_id == seat.id,
            EntitlementEvent.class_id == seat.class_id,
            EntitlementEvent.trigger_id.like("rent_top_off_%"),
        )
        .scalar()
        or 0,
    )

    target = max(0, int(target_rent_passes or 0))
    delta = target - current_rent_passes

    if delta == 0:
        return 0, 0, False

    passes_awarded = max(0, delta)
    passes_revoked = max(0, -delta)
    now = _current_utc()

    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=delta,
        event_type="GRANT" if delta > 0 else "REVOCATION",
        trigger_id=f"rent_top_off_{seat.id}_{now.isoformat()}",
        correlation_id=generate_correlation_id() if delta > 0 else None,
        occurred_at=now,
    )
    db.session.add(event)

    return passes_awarded, passes_revoked, True
