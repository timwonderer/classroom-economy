"""Helpers for strict seat-scoped queries."""

import sqlalchemy as sa



def get_seat_ids_for_student_class(student_id: int, class_id: str) -> list[int]:
    """Return seat IDs bound to a student and class ID."""
    from app.models import IdentityProfile, Seat, Student

    return [
        row[0]
        for row in Seat.query.with_entities(Seat.id).join(
            IdentityProfile, IdentityProfile.seat_id == Seat.id
        ).join(
            Student, Student.identity_id == IdentityProfile.id
        ).filter(
            Student.id == student_id,
            Seat.class_id == class_id,
        ).all()
    ]


def get_seat_id_for_class(student_id: int, class_id: str) -> int | None:
    """Return the primary seat ID bound to a student and class ID."""
    from app.models import IdentityProfile, Seat, Student
    seat = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Student.id == student_id, Seat.class_id == class_id)
        .first()
    )
    return seat.id if seat else None


def resolve_active_teacher_seat(teacher_id: int, class_id: str):
    """Resolve the canonical teacher seat for a given class context."""
    from app.models import Seat

    return Seat.query.filter_by(role='teacher', class_id=class_id).first()


def transaction_scope_filter(TransactionModel, seat_or_student_id: int, seat_ids: list[int] | None = None):
    """Return a seat-scoped filter, with a legacy fallback for old call sites."""
    if seat_ids is not None:
        if seat_ids:
            return sa.and_(TransactionModel.seat_id.in_(seat_ids), TransactionModel.seat_id.is_not(None))
        return sa.false()
    return sa.and_(TransactionModel.seat_id == seat_or_student_id, TransactionModel.seat_id.is_not(None))


def seat_scoped_filter(Model, seat_id: int, seat_field: str = "seat_id"):
    """Return a strict seat-scoped filter for models that carry seat references."""
    seat_col = getattr(Model, seat_field)
    return sa.and_(seat_col == seat_id, seat_col.is_not(None))
