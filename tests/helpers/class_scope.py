from app.extensions import db
from app.models import ClassEconomy, ClassMembership, Seat, IdentityProfile, User
from datetime import datetime, timezone
from uuid import uuid4
from werkzeug.security import generate_password_hash


def _ensure_user(user_id, role="teacher"):
    """Return user_id if a User row exists, otherwise auto-create one."""
    if user_id is not None:
        existing = db.session.get(User, user_id)
        if existing:
            return user_id
    # Auto-create a minimal User so the FK is satisfied
    user = User(
        username_hash=f"auto_{uuid4().hex[:12]}",
        username_lookup_hash=f"auto_lookup_{uuid4().hex[:12]}",
        password_hash=generate_password_hash("testpass"),
        user_role=role,
        has_completed_setup=True,
    )
    db.session.add(user)
    db.session.flush()
    return user.id


def create_class_scope(
    *,
    teacher,
    join_code,
    student=None,
    block="A",
    display_name=None,
    class_status="active",
    create_teacher_membership=True,
    create_student_membership=True,
    create_seat=True,
    teacher_user_id=None,
    student_user_id=None,
    # Legacy param names kept for caller compatibility during migration
    create_claimed_teacher_block=False,
    teacher_block_teacher=None,
    teacher_block_student=None,
    teacher_block_claimed=False,
):
    """Create canonical class scope for tests under the v2 model.

    Uses Seat + IdentityProfile exclusively. The teacher_block_* params
    are accepted for backward compatibility but only affect seat claimed state.

    If teacher_user_id is not provided, a User row is auto-created so that
    the Seat.user_id FK constraint is always satisfied.
    """
    claimed = teacher_block_claimed or create_claimed_teacher_block

    resolved_teacher_user_id = _ensure_user(teacher_user_id, role="teacher")
    class_row = ClassEconomy(
        class_id=str(uuid4()),
        join_code=join_code,
        teacher_id=teacher.id,
        display_name=display_name,
        section=block,
        status=class_status,
        created_by_user_id=resolved_teacher_user_id,
    )
    db.session.add(class_row)
    db.session.flush()

    if create_teacher_membership:
        db.session.add(ClassMembership(
            class_id=class_row.class_id,
            join_code=join_code,
            admin_id=teacher.id,
            role="admin",
        ))
        t_seat = Seat(
            user_id=resolved_teacher_user_id,
            class_id=class_row.class_id,
            join_code=join_code,
            role="teacher",
        )
        db.session.add(t_seat)
        db.session.flush()
        db.session.add(IdentityProfile(
            seat_id=t_seat.id,
            profile_type='teacher_primary',
            first_name='Teacher',
            last_name='Teacher',
        ))

    if student is not None and create_student_membership:
        db.session.add(ClassMembership(
            class_id=class_row.class_id,
            join_code=join_code,
            student_id=student.id,
            role="student",
        ))

    if student is not None and create_seat:
        resolved_student_user_id = _ensure_user(student_user_id, role="student")
        s_seat = Seat(
            user_id=resolved_student_user_id,
            class_id=class_row.class_id,
            join_code=join_code,
            block=block,
            block_identifier=block,
            role="student",
            claimed_at=datetime.now(timezone.utc) if claimed else None,
        )
        db.session.add(s_seat)
        db.session.flush()
        db.session.add(IdentityProfile(
            seat_id=s_seat.id,
            profile_type='student_claimed' if claimed else 'student_unclaimed',
            first_name=getattr(student, 'display_first_name', 'Student'),
            last_name=getattr(student, 'display_last_name', 'Test'),
        ))

    return class_row
