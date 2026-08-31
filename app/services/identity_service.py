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


def get_enrolled_student_seat_ids(class_id: str) -> list[int]:
    """Return the enrolled student seat ids for a class, ascending.

    Read-only Identity-domain surface consumed by the Interpretation domain
    (SPEC-ITR-001 §5.3, §6.4: "enrollment status during the window") as the
    denominator population for class-aggregate observations. Enrollment is
    expressed by the existence of a claimed student ``Seat`` bound to the
    class; ``block``/``period`` is never a scoping key (INV-ARC-019).

    This is deliberately a pure read (no writes, INV-ARC-007) and performs no
    time-windowing: a seat is enrolled for the class, not for a sub-interval.
    """
    if not class_id:
        return []
    rows = (
        Seat.query
        .with_entities(Seat.id)
        .filter(
            Seat.class_id == class_id,
            Seat.role == "student",
            Seat.claimed_at.isnot(None),
        )
        .order_by(Seat.id.asc())
        .all()
    )
    return [row.id for row in rows]
