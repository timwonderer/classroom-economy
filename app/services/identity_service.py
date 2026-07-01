from __future__ import annotations

from app.extensions import db
from app.models import Seat, User, EntitlementEvent
import sqlalchemy as sa
from app.utils.time import utc_now


def _resolve_seat(identity, *, seat=None) -> Seat | None:
    if seat is not None:
        return seat
    if isinstance(identity, Seat):
        return identity
    if isinstance(identity, User):
        return (
            Seat.query
            .filter(Seat.user_id == identity.id)
            .order_by(Seat.id.asc())
            .first()
        )
    return None


def add_hall_passes(identity, quantity: int, *, seat=None) -> int:
    """Canonical seat-owned mutation for hall-pass counters."""
    resolved_seat = _resolve_seat(identity, seat=seat)
    if not resolved_seat:
        return 0
    current_total = max(0, int(resolved_seat.hall_passes or 0))
    resolved_seat.hall_passes = current_total + int(quantity)
    db.session.add(resolved_seat)
    return resolved_seat.hall_passes


def reconcile_rent_hall_pass_top_off(
    *,
    seat=None,
    identity=None,
    target_rent_passes: int,
):
    """Canonical seat-owned mutation for rent-provided hall passes."""
    resolved_seat = _resolve_seat(identity, seat=seat)
    if not resolved_seat:
        return 0, 0, False

    current_rent_passes = db.session.query(
        sa.func.sum(EntitlementEvent.quantity_delta)
    ).filter_by(
        seat_id=resolved_seat.id,
        class_id=resolved_seat.class_id,
    ).scalar() or 0

    state_changed = False
    target_rent_passes = max(0, int(target_rent_passes or 0))

    current_total_passes = max(0, int(resolved_seat.hall_passes or 0))
    effective_rent_passes = min(current_rent_passes, current_total_passes)
    delta = target_rent_passes - effective_rent_passes
    passes_awarded = max(0, delta)
    passes_revoked = max(0, -delta)

    if delta != 0:
        resolved_seat.hall_passes = current_total_passes + delta
        db.session.add(resolved_seat)
        state_changed = True

        event = EntitlementEvent(
            seat_id=resolved_seat.id,
            class_id=resolved_seat.class_id,
            quantity_delta=delta,
            event_type="GRANT" if delta > 0 else "REVOCATION",
            trigger_id=f"rent_top_off_{resolved_seat.id}_{utc_now().isoformat()}",
            occurred_at=utc_now(),
        )
        db.session.add(event)

    return passes_awarded, passes_revoked, state_changed
