"""Identity service — canonical User/Seat resolution helpers.

Scope: resolving who an actor is. No domain logic (balances, entitlements, etc.).
"""

from __future__ import annotations

from app.extensions import db
from app.models import Seat, User


def _resolve_seat(identity, *, seat: Seat | None = None) -> Seat | None:
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
