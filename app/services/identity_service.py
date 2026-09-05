"""Identity service — canonical User/Seat resolution helpers.

Scope: resolving who an actor is. No domain logic (balances, entitlements, etc.).
"""

from __future__ import annotations

from app.models import Seat

# Removed: ``_resolve_seat(identity, seat=None)``. Given a ``User`` it returned
# ``Seat.query.filter(Seat.user_id == ...).order_by(Seat.id.asc()).first()`` —
# the lowest-id seat across every class the user participates in, with no
# ``class_id`` filter. Under DOM-IDEN-001 §VI a ``User`` holds one ``Seat`` per
# ``Class``, so "the seat for a user" is not a well-formed question: without a
# class it silently answers with whichever class the user joined first. It had
# no callers, so rather than re-express the same unanswerable question with a
# class argument, it is deleted. Callers that need a seat must resolve it from
# a canonical context that already carries ``class_id``.


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
