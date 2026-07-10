"""Entitlement service — canonical hall pass balance via EntitlementEvent.

Hall pass balance is derived from the append-only EntitlementEvent log.
No seat-level counter column exists; every read is a live aggregate.
"""

from __future__ import annotations

import sqlalchemy as sa

from app.extensions import db
from app.models import EntitlementEvent, Seat
from app.utils.time import utc_now


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
    event_type: str = "GRANT",
) -> int:
    """Grant hall passes by appending an EntitlementEvent. Returns new balance."""
    now = utc_now()
    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=int(quantity),
        event_type=event_type,
        trigger_id=trigger_id or f"grant_{seat.id}_{now.isoformat()}",
        occurred_at=now,
    )
    db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat.id, seat.class_id)


def consume_hall_pass(seat_id: int, class_id: str, *, trigger_id: str) -> int:
    """Deduct one hall pass by appending a CONSUME EntitlementEvent. Returns new balance."""
    now = utc_now()
    event = EntitlementEvent(
        seat_id=seat_id,
        class_id=class_id,
        quantity_delta=-1,
        event_type="CONSUME",
        trigger_id=trigger_id,
        occurred_at=now,
    )
    db.session.add(event)
    db.session.flush()
    return get_hall_pass_balance(seat_id, class_id)


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
    now = utc_now()
    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=int(delta),
        event_type="GRANT" if delta > 0 else "REVOCATION",
        trigger_id=trigger_id or f"adjust_{seat.id}_{now.isoformat()}",
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
    now = utc_now()

    event = EntitlementEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        quantity_delta=delta,
        event_type="GRANT" if delta > 0 else "REVOCATION",
        trigger_id=f"rent_top_off_{seat.id}_{now.isoformat()}",
        occurred_at=now,
    )
    db.session.add(event)

    return passes_awarded, passes_revoked, True
