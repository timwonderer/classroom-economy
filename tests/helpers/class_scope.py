from app.extensions import db
from app.models import ClassEconomy, ClassMembership, Seat, IdentityProfile
from datetime import datetime, timezone
from uuid import uuid4


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
    """
    claimed = teacher_block_claimed or create_claimed_teacher_block

    resolved_teacher_user_id = teacher_user_id or teacher.id
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
        s_seat = Seat(
            user_id=student_user_id or getattr(student, "user_id", None),
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
            first_name=student.display_first_name,
            last_name=student.display_last_name,
        ))

    return class_row
