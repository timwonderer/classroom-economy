"""Test helpers delegating to the canonical production service.

Only the V2 canonical identity model is supported:
  User (role=TEACHER) → ClassEconomy (class_id UUID) → Seat (role='teacher')
  User (role=STUDENT) → Seat (class_id, role='student') → IdentityProfile

No Admin objects, no legacy bridge patterns.
"""

from __future__ import annotations

import uuid

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, User
from werkzeug.security import generate_password_hash


def create_class_scope(
    *,
    teacher_user: User,
    join_code: str | None = None,
    display_name: str | None = None,
    section: str | None = None,
    feature_names: list[str] | tuple[str, ...] | None = None,
    # Convenience: add a student immediately after creating the class
    student_first_name: str | None = None,
    student_last_name: str | None = None,
) -> ClassEconomy:
    """Create a canonical class, delegating entirely to the production service.

    Args:
        teacher_user: V2 canonical User with role=TEACHER.
        join_code: user-facing alias supplied by the caller.
        display_name: display metadata only, not an identity anchor.
        section: display metadata only (e.g. "Period 1").
        student_first_name / student_last_name: if both provided, also
            creates one student identity in the new class.

    Returns the ClassEconomy row. Flushes but does NOT commit.
    """
    from app.services.classroom_setup import create_class, create_student

    resolved_join_code = join_code or f"AUTO{uuid.uuid4().hex[:8].upper()}"
    idempotency_key = "create_class_scope:" + ":".join(
        [
            str(teacher_user.id),
            resolved_join_code,
            display_name or "",
            section or "",
            student_first_name or "",
            student_last_name or "",
        ]
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key=idempotency_key):
        class_row = create_class(
            teacher_user.id,
            join_code=resolved_join_code,
            display_name=display_name,
            section=section,
        )

        if student_first_name and student_last_name:
            create_student(
                class_row.class_id,
                first_name=student_first_name,
                last_name=student_last_name,
            )

    return class_row


def make_student_identity(
    *,
    class_id: str | None = None,
    first_name: str = "Student",
    last_name: str = "Test",
    claimed: bool = True,
    username: str | None = None,
    pin: str | None = None,
) -> Seat:
    """Create a canonical student identity (User → Seat → IdentityProfile).

    Delegates entirely to app/services/classroom_setup.create_student().
    Returns the Seat so callers can do seat.id, seat.user_id, etc.
    """
    from app.services.classroom_setup import create_student
    from app.models import ClassEconomy

    resolved_class_id = class_id
    with FEATContext(
        "FEAT-IDEN-001",
        idempotency_key=f"make_student_identity:{resolved_class_id}:{username or first_name}:{last_name}",
    ):
        if resolved_class_id is None:
            raise TypeError("make_student_identity() requires class_id")

        _user, seat, _profile = create_student(
            resolved_class_id,
            first_name=first_name,
            last_name=last_name,
            claimed=claimed,
            username=username,
            pin=pin,
        )
        if seat.user and not seat.user.passphrase_hash:
            seat.user.passphrase_hash = generate_password_hash("password")
    return seat
