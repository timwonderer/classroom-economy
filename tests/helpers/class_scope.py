"""Class scope and seat creation helpers for tests."""

import uuid
from app.extensions import db
from app.models import User, Seat, ClassEconomy, IdentityProfile
from app.feats.base import FEATContext
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_canonical_student


def create_class_scope(
    teacher_user: User | None = None,
    join_code: str | None = None,
    display_name: str = "Test Class",
    section: str = "A",
) -> ClassEconomy:
    """
    Create a canonical class scope with User, Seat, ClassEconomy, IdentityProfile.

    Args:
        teacher_user: Optional teacher User; creates one if not provided
        join_code: Optional join_code; generates if not provided
        display_name: Display name for class
        section: Section/period identifier

    Returns:
        ClassEconomy instance
    """
    unique_id = str(uuid.uuid4().hex[:8])

    # Use FEAT context for test setup
    with FEATContext("FEAT-BYPASS-LEGACY", idempotency_key=f"create_class_scope:{unique_id}"):
        # Create teacher if not provided
        if not teacher_user:
            teacher_user = seed_canonical_admin(f"teacher_{unique_id}").user

        # Create join_code if not provided
        if not join_code:
            join_code = f"TEST{uuid.uuid4().hex[:6].upper()}"

        # Create ClassEconomy
        class_row = ClassEconomy(
            class_id=str(uuid.uuid4()),
            join_code=join_code,
            user_id=teacher_user.id,
            display_name=display_name,
            section=section,
        )
        db.session.add(class_row)
        db.session.flush()

        # Create teacher seat for class
        teacher_seat = Seat(
            user_id=teacher_user.id,
            class_id=class_row.class_id,
            role="teacher",
        )
        db.session.add(teacher_seat)
        db.session.flush()

        # Create teacher identity profile
        teacher_profile = IdentityProfile(
            seat_id=teacher_seat.id,
            class_id=class_row.class_id,
            profile_type="teacher",
            first_name="Teacher",
            last_name=f"S{section}",
        )
        db.session.add(teacher_profile)
        db.session.flush()

        # Save IDs before exiting context
        class_id = class_row.class_id
        db.session.commit()

    # Retrieve and return the class row
    return db.session.query(ClassEconomy).filter_by(class_id=class_id).first()


def make_student_seat(
    class_scope: ClassEconomy | None = None,
    user_id: int | None = None,
    role: str = "student",
) -> Seat:
    """
    Create a student seat in a class.

    Args:
        class_scope: ClassEconomy instance; creates if not provided
        user_id: User ID for seat; creates student user if not provided
        role: Seat role ("student" or "teacher")

    Returns:
        Seat instance
    """
    unique_id = str(uuid.uuid4().hex[:8])

    with FEATContext("FEAT-BYPASS-LEGACY", idempotency_key=f"make_student_seat:{unique_id}"):
        # Create class if not provided
        if not class_scope:
            class_scope = create_class_scope()

        # Create user if not provided
        if not user_id:
            student_user = seed_canonical_student(f"student_{unique_id}")
            user_id = student_user.id

        # Create seat
        seat = Seat(
            user_id=user_id,
            class_id=class_scope.class_id,
            role=role,
        )
        db.session.add(seat)
        db.session.flush()

        # Save ID before exiting context
        seat_id = seat.id
        db.session.commit()

    # Retrieve and return the seat
    return db.session.query(Seat).filter_by(id=seat_id).first()


def make_student_identity(
    class_id: str,
    user_id: int | None = None,
    first_name: str = "Student",
    last_name: str = "Test",
) -> Seat:
    """
    Create a complete student identity (User, Seat, IdentityProfile).

    Args:
        class_id: Class ID for the seat
        user_id: Optional User ID; creates if not provided
        first_name: First name for identity profile
        last_name: Last name for identity profile

    Returns:
        Seat instance with associated IdentityProfile
    """
    unique_id = str(uuid.uuid4().hex[:8])

    with FEATContext("FEAT-BYPASS-LEGACY", idempotency_key=f"make_student_identity:{unique_id}"):
        # Create user if not provided
        if not user_id:
            student_user = seed_canonical_student(f"student_{unique_id}")
            user_id = student_user.id

        # Create seat
        seat = Seat(
            user_id=user_id,
            class_id=class_id,
            role="student",
        )
        db.session.add(seat)
        db.session.flush()

        # Create identity profile
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_id,
            profile_type="student",
            first_name=first_name,
            last_name=last_name,
        )
        db.session.add(profile)
        db.session.flush()

        # Save ID before exiting context
        seat_id = seat.id
        db.session.commit()

    # Retrieve and return the seat
    return db.session.query(Seat).filter_by(id=seat_id).first()
