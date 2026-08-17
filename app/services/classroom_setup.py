"""Canonical classroom setup service.

Single authoritative path for creating teachers, classes, and students.
Both production routes and tests call these functions — there is no
separate test-only fixture assembly.

Canonical creation order for a class:
  1. user_id (Teacher User, pre-existing) + generated class_id (UUID) → ClassEconomy
     join_code is a user-facing alias bound at creation time; it is ingress/display metadata only.
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
from app.utils.canonical_temporal_resolver import utc_now


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------

def create_teacher(username: str, *, totp_secret: str | None = None) -> User:
    """Create a canonical teacher User (role=TEACHER), or return existing.

    Idempotent: if a teacher with this username already exists, returns them.
    Concurrent-safe: uses a savepoint to handle unique constraint races on
    username_lookup_hash — if a concurrent caller wins the insert, re-queries
    and returns the winner's row.

    Returns the flushed User instance. Does NOT create a class or seat —
    call create_class() next to complete the teacher identity.
    """
    from sqlalchemy.exc import IntegrityError
    from app.utils.encryption import normalize_totp_for_storage

    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    existing = User.query.filter_by(username_lookup_hash=u_lookup).first()
    if existing is not None:
        if existing.user_role != UserRole.TEACHER:
            raise ValueError("Username belongs to a non-teacher user")
        return existing
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        totp_secret_encrypted=normalize_totp_for_storage(totp_secret) if totp_secret else None,
    )
    try:
        with db.session.begin_nested():
            db.session.add(user)
            db.session.flush()
    except IntegrityError:
        existing = User.query.filter_by(username_lookup_hash=u_lookup).first()
        if existing is not None:
            if existing.user_role != UserRole.TEACHER:
                raise ValueError("Username belongs to a non-teacher user")
            return existing
        raise
    return user


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
        teacher_user_id=user_id,
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


def create_class_without_user(
    *,
    join_code: str,
    display_name: str | None = None,
    section: str | None = None,
    teacher_first_name: str | None = None,
    teacher_last_name: str | None = None,
) -> tuple[ClassEconomy, Seat]:
    """Create a class and teacher seat with NO user yet.

    Used during the teacher signup flow where the class is created first,
    before the teacher creates their username and TOTP credentials.
    The teacher Seat is created with user_id=None (unclaimed).
    An IdentityProfile is attached if display name is provided.

    Returns (ClassEconomy, teacher Seat) so the caller can stash seat_id
    in the session for later binding when the User is created.
    """
    class_id = str(uuid.uuid4())

    economy = ClassEconomy(
        class_id=class_id,
        join_code=join_code,
        teacher_user_id=None,
        display_name=display_name,
        section=section,
    )
    db.session.add(economy)
    db.session.flush()

    teacher_seat = Seat(
        user_id=None,
        class_id=class_id,
        role="teacher",
    )
    db.session.add(teacher_seat)
    db.session.flush()

    if teacher_first_name:
        profile = IdentityProfile(
            seat_id=teacher_seat.id,
            class_id=class_id,
            profile_type="teacher",
            first_name=teacher_first_name,
            last_name=teacher_last_name or "",
        )
        db.session.add(profile)
        db.session.flush()

    return economy, teacher_seat


def bind_teacher_to_class(user: User, *, class_id: str, seat_id: int) -> None:
    """Bind a newly created User to an existing class and teacher seat.

    Called after the teacher completes credential setup (username + TOTP).
    Updates: Seat.user_id, ClassEconomy.teacher_user_id, User.last_active_*.
    """
    seat = db.session.get(Seat, seat_id)
    if not seat or seat.class_id != class_id:
        raise ValueError(f"Seat {seat_id} not found or does not belong to class {class_id}")

    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    if not economy:
        raise ValueError(f"Class {class_id} not found")

    seat.user_id = user.id
    seat.claimed_at = utc_now()
    economy.teacher_user_id = user.id
    user.last_active_class_id = class_id
    user.last_active_seat_id = seat_id
    db.session.flush()


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
    from app.utils.canonical_temporal_resolver import utc_now
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


def create_student_user_for_seat(
    seat: Seat,
    *,
    username: str,
    pin: str,
    passphrase: str,
) -> User:
    """Create the canonical student User and bind it to an already-claimed seat."""
    from werkzeug.security import generate_password_hash

    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    student = User(
        user_role=UserRole.STUDENT,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        pin_hash=generate_password_hash(pin),
        passphrase_hash=generate_password_hash(passphrase),
    )
    db.session.add(student)
    db.session.flush()

    seat.user_id = student.id
    seat.claimed_at = seat.claimed_at or utc_now()
    student.last_active_class_id = seat.class_id
    student.last_active_seat_id = seat.id
    db.session.flush()
    return student


def create_class_with_roster(
    *,
    user_id: int,
    join_code: str,
    class_name: str,
    section: str | None = None,
    rows: list[dict],
) -> ClassEconomy:
    """Create a class, teacher seat, and roster rows in canonical order.

    Each row must contain first_name, last_name, and notes.
    claim_first_name_hash and claim_last_name_hash are computed automatically
    so the claim flow can match students by name without plaintext storage.
    """
    from app.hash_utils import hash_username_lookup

    class_row = create_class(
        user_id,
        join_code=join_code,
        display_name=class_name,
        section=section,
    )

    for row in rows:
        first_name = row["first_name"]
        last_name = row["last_name"]
        notes = row.get("notes") or row.get("teacher_note")
        seat = Seat(
            class_id=class_row.class_id,
            role="student",
            claimed_at=None,
            claim_first_name_hash=hash_username_lookup(first_name.lower()),
            claim_last_name_hash=hash_username_lookup(last_name.lower()),
            roster_fingerprint=hash_username_lookup(
                f"{class_row.class_id}|{first_name.lower()}|{last_name.lower()}"
            ),
        )
        db.session.add(seat)
        db.session.flush()
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_row.class_id,
            profile_type="student",
            first_name=first_name,
            last_name=last_name,
            notes=notes,
        )
        db.session.add(profile)
        db.session.flush()

    return class_row


def create_student_seat_with_profile(
    *,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    student_id: int | None = None,
    claimed_at=None,
) -> Seat:
    """Create a canonical student seat and its identity profile."""
    seat = Seat(
        class_id=class_id,
        role="student",
        user_id=student_id,
    )
    db.session.add(seat)
    db.session.flush()

    _set_claim_hashes(seat, first_name, last_name)

    profile = IdentityProfile(
        seat_id=seat.id,
        class_id=class_id,
        profile_type="student",
        first_name=first_name,
        last_name=last_name,
        notes=notes,
    )
    db.session.add(profile)
    db.session.flush()
    return seat


def _set_claim_hashes(seat: Seat, first_name: str, last_name: str) -> None:
    """Set claim lookup hashes on a seat so the claim flow can match by name."""
    from app.hash_utils import hash_username_lookup

    seat.claim_first_name_hash = hash_username_lookup(first_name.strip().lower())
    seat.claim_last_name_hash = hash_username_lookup(last_name.strip().lower())


def update_or_create_roster_seat(
    *,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    existing_seat: Seat | None = None,
) -> Seat:
    """Update an existing roster seat or create a new canonical student seat."""
    if existing_seat:
        profile = IdentityProfile.query.filter_by(seat_id=existing_seat.id).first()
        if profile:
            profile.first_name = first_name
            profile.last_name = last_name
            profile.notes = notes
        else:
            profile = IdentityProfile(
                seat_id=existing_seat.id,
                class_id=class_id,
                profile_type="student",
                first_name=first_name,
                last_name=last_name,
                notes=notes,
            )
            db.session.add(profile)
        _set_claim_hashes(existing_seat, first_name, last_name)
        db.session.flush()
        return existing_seat

    return create_student_seat_with_profile(
        class_id=class_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
    )


def create_pending_student_seat(
    *,
    class_id: str,
    dedupe_code: str,
    has_received_rent_exemption: bool = False,
    block: str | None = None,
    claimed_at=None,
) -> Seat:
    """Create a canonical pending student seat without binding a user."""
    seat = Seat(
        class_id=class_id,
        dedupe_code=dedupe_code,
        has_received_rent_exemption=has_received_rent_exemption,
        block=block,
        claimed_at=claimed_at,
    )
    db.session.add(seat)
    db.session.flush()
    return seat


def create_roster_student_seat(
    *,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    dedupe_code: str | None = None,
    block: str | None = None,
    claim_first_name_hash=None,
    claim_last_name_hash=None,
    roster_fingerprint=None,
    claimed_at=None,
) -> Seat:
    """Create a canonical roster seat for import/edit flows."""
    seat = Seat(
        class_id=class_id,
        role="student",
        claim_first_name_hash=claim_first_name_hash,
        claim_last_name_hash=claim_last_name_hash,
        roster_fingerprint=roster_fingerprint,
        dedupe_code=dedupe_code,
        block=block,
        claimed_at=claimed_at,
    )
    db.session.add(seat)
    db.session.flush()

    profile = IdentityProfile(
        seat_id=seat.id,
        class_id=class_id,
        profile_type="student",
        first_name=first_name,
        last_name=last_name,
        notes=notes,
    )
    db.session.add(profile)
    db.session.flush()
    return seat


def delete_seat_with_profile(seat: Seat) -> None:
    """Delete a seat and its identity profile in canonical order."""
    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    if profile:
        db.session.delete(profile)
    db.session.delete(seat)
