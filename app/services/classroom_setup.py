"""Canonical classroom setup service.

Single authoritative path for creating teachers, classes, and students.
Both production routes and tests call these functions — there is no
separate test-only fixture assembly.

Canonical creation order for a class:
  1. user_id (Teacher User, pre-existing) + generated class_id (UUID) → ClassEconomy
     join_code is a user-facing alias bound at creation time; it is ingress/display metadata, not runtime authority.
     display_name / section are display metadata only, never identity anchors.
  2. Seat (seat_id generated, user_id + class_id bound, role='teacher')
  3. User.last_active_class_id = class_id, User.last_active_seat_id = seat_id

All functions flush but do NOT commit. Callers own the transaction boundary.
"""

import secrets
import uuid

from app.extensions import db
from app.models import ClassEconomy, IdentityProfile, Seat, User, UserRole
from app.utils.auth_username import build_hashed_username_fields


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------

def create_teacher(username: str, *, totp_secret: str | None = None) -> User:
    """Create a canonical teacher User (role=TEACHER).

    Returns the flushed User instance. Does NOT create a class or seat —
    call create_class() next to complete the teacher identity.
    """
    from app.utils.encryption import normalize_totp_for_storage
    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    teacher = User(
        user_role=UserRole.TEACHER,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        totp_secret_encrypted=normalize_totp_for_storage(totp_secret) if totp_secret else None,
    )
    db.session.add(teacher)
    db.session.flush()
    return teacher


# ---------------------------------------------------------------------------
# Class
# ---------------------------------------------------------------------------

def create_class(
    user_id: int,
    *,
    join_code: str,
    display_name: str | None = None,
    section: str | None = None,
    class_timezone: str = "UTC",
) -> ClassEconomy:
    """Create a class and wire the teacher's canonical context.

    Canonical order:
      1. ClassEconomy (class_id UUID generated, join_code alias bound)
      2. Teacher Seat (seat_id generated, user_id + class_id bound, role='teacher')
      3. User updated: last_active_class_id, last_active_seat_id

    Returns the ClassEconomy instance (economy.class_id is the canonical anchor).
    """
    class_id = str(uuid.uuid4())

    economy = ClassEconomy(
        class_id=class_id,
        join_code=join_code,
        user_id=user_id,
        created_by_user_id=user_id,
        display_name=display_name,
        section=section,
        class_timezone=class_timezone,
    )
    db.session.add(economy)
    db.session.flush()

    teacher_seat = Seat(
        user_id=user_id,
        class_id=class_id,
        role="teacher",
    )
    db.session.add(teacher_seat)
    db.session.flush()

    teacher = db.session.get(User, user_id)
    teacher.last_active_class_id = class_id
    teacher.last_active_seat_id = teacher_seat.id
    db.session.flush()

    return economy


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------

def create_student(
    class_id: str,
    *,
    first_name: str,
    last_name: str,
    username: str | None = None,
    pin: str | None = None,
    claimed: bool = True,
) -> tuple[User, Seat, IdentityProfile]:
    """Create a canonical student identity within a class.

    Creates User (role=STUDENT) → Seat (class_id bound, role='student') →
    IdentityProfile (seat_id bound). Updates User.last_active_class_id and
    User.last_active_seat_id.

    Returns (user, seat, profile).
    """
    from app.utils.time import utc_now
    from werkzeug.security import generate_password_hash

    if username:
        _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    else:
        _token = secrets.token_hex(12)
        u_hash = f"prov_{_token}"
        u_lookup = None

    student = User(
        user_role=UserRole.STUDENT,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        pin_hash=generate_password_hash(pin) if pin else None,
    )
    db.session.add(student)
    db.session.flush()

    seat = Seat(
        user_id=student.id,
        class_id=class_id,
        role="student",
        claimed_at=utc_now() if claimed else None,
    )
    db.session.add(seat)
    db.session.flush()

    profile = IdentityProfile(
        seat_id=seat.id,
        class_id=class_id,
        profile_type="student_claimed" if claimed else "student_unclaimed",
        first_name=first_name,
        last_name=last_name,
    )
    db.session.add(profile)
    db.session.flush()

    student.last_active_class_id = class_id
    student.last_active_seat_id = seat.id
    db.session.flush()

    return student, seat, profile
