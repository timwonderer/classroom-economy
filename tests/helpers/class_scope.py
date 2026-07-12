"""Test helpers delegating to the canonical production service.

Only the V2 canonical identity model is supported:
  User (role=TEACHER) → ClassEconomy (class_id UUID) → Seat (role='teacher')
  User (role=STUDENT) → Seat (class_id, role='student') → IdentityProfile

No Admin objects, no legacy bridge patterns.
"""

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
    # Convenience: add a student immediately after creating the class
    student_first_name: str | None = None,
    student_last_name: str | None = None,
) -> ClassEconomy:
    """Create a canonical class, delegating entirely to the production service.

    Args:
        teacher_user: V2 canonical User with role=TEACHER.
        join_code: user-facing alias; auto-generated UUID fragment if omitted.
        display_name: display metadata only, not an identity anchor.
        section: display metadata only (e.g. "Period 1").
        student_first_name / student_last_name: if both provided, also
            creates one student identity in the new class.

    Returns the ClassEconomy row. Flushes but does NOT commit.
    """
    from app.services.classroom_setup import create_class, create_student
    from uuid import uuid4

    resolved_join_code = join_code or f"CLS{uuid4().hex[:8].upper()}"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"create_class_scope:{resolved_join_code}"):
        existing = ClassEconomy.query.filter_by(join_code=resolved_join_code).first()
        if existing:
            class_row = existing
        else:
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
    block: str | None = None,
    join_code: str | None = None,
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
            if not join_code:
                raise TypeError("make_student_identity() requires class_id or join_code")
            class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
            if not class_row:
                raise LookupError(f"No class found for join_code={join_code!r}")
            resolved_class_id = class_row.class_id

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
        if block:
            # Preserve older helper call sites that supplied block metadata.
            # The canonical model derives scope from class_id; this field is display-only.
            seat.block = block
            db.session.flush()
    return seat
