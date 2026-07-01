"""Helpers for strict seat-scoped queries."""

import sqlalchemy as sa


def get_seat_ids_for_student_join(student_id: int, join_code: str) -> list[int]:
    """Legacy compatibility shim while callers migrate from join_code to class_id."""
    from app.models import ClassEconomy, IdentityProfile, Seat, Student

    if not student_id or not join_code:
        return []

    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    query = Seat.query.with_entities(Seat.id).join(IdentityProfile, IdentityProfile.seat_id == Seat.id).join(Student, Student.identity_id == IdentityProfile.id).filter(Student.id == student_id)
    if not class_row:
        return []
    query = query.filter(Seat.class_id == class_row.class_id)
    query = query.join(IdentityProfile, IdentityProfile.seat_id == Seat.id).join(Student, Student.identity_id == IdentityProfile.id)
    return [row[0] for row in query.filter(Student.id == student_id).all()]


def get_seat_ids_for_student_class(student_id: int, class_id: str) -> list[int]:
    """Return seat IDs bound to a student and class ID."""
    from app.models import IdentityProfile, Seat, Student, User

    # Resolve via User (canonical V2 for shared students)
    v2_seats = Seat.query.with_entities(Seat.id).join(
        User, User.id == Seat.user_id
    ).join(
        Student, Student.username_hash == User.username_hash
    ).filter(
        Student.id == student_id,
        Seat.class_id == class_id,
        Seat.role == 'student'
    ).all()
    
    if v2_seats:
        return [row[0] for row in v2_seats]

    # Fallback to direct IdentityProfile link for legacy non-migrated records
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
    from app.models import IdentityProfile, Seat, Student, User
    
    # Try resolving via User link first (canonical V2)
    seat = (
        Seat.query
        .join(User, User.id == Seat.user_id)
        .join(Student, Student.username_hash == User.username_hash)
        .filter(Student.id == student_id, Seat.class_id == class_id, Seat.role == 'student')
        .first()
    )
    if seat:
        return seat.id
        
    # Fallback to legacy IdentityProfile direct link
    seat = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Student.id == student_id, Seat.class_id == class_id)
        .first()
    )
    return seat.id if seat else None


def resolve_active_teacher_seat(teacher_id: int, class_id: str):
    """Resolve the canonical teacher seat for a given admin and class context.

    In the V2 architecture, this relies on finding a Seat with role='teacher'
    bound to this class_id. In legacy contexts, this maps back to the admin_id,
    but the Seat itself must exist as the canonical activity anchor.
    """
    from app.models import Seat

    # Until the User/Seat identity migration fully populates user_id on teacher seats,
    # we resolve the teacher seat by class_id and role.
    # Once fully migrated, this should query by user_id = current_user.id.
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
