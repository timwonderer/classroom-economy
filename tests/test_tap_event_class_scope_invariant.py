from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import ClassEconomy, Seat, IdentityProfile, User, UserRole, TapEvent
from tests.helpers.class_scope import make_student_identity


def _setup_scoped_student(with_seat: bool = True):
    teacher = User(
        username_hash="tap_inv_teacher_hash",
        username_lookup_hash="tap_inv_teacher_lookup",
        user_role=UserRole.TEACHER,
        password_hash="secret",
    )
    db.session.add(teacher)
    db.session.flush()

    cls = ClassEconomy(join_code="TINV01", user_id=teacher.id, status="active")
    db.session.add(cls)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Tap", last_name="I")
    db.session.add(profile)
    db.session.flush()
    student = make_student_identity(first_name="Tap", last_name="I", block="A", claimed=True)
    student_user = User(username_hash=f"tap_{student.id}", username_lookup_hash=f"tap_lookup_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()

    seat = None
    if with_seat:
        seat = Seat(
            user_id=student_user.id,
            class_id=cls.class_id,
            join_code=cls.join_code,
            role="student",
            block_identifier="A",
            block="A",
        )
        db.session.add(seat)
    student_id = student.id
    class_id = cls.class_id
    db.session.flush()
    return student_id, seat.id if seat else None, class_id


def test_tap_event_rejects_missing_class_id_and_seat_id():
    student_id, _seat_id, _class_id = _setup_scoped_student(with_seat=False)

    db.session.add(
        TapEvent(
            seat_id=None,
            period="A",
            status="active",
            timestamp=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(ValueError, match="class_id is required"):
        db.session.flush()

    db.session.rollback()


def test_tap_event_requires_seat_even_when_class_is_present():
    student_id, _seat_id, class_id = _setup_scoped_student(with_seat=False)

    db.session.add(
        TapEvent(
            seat_id=None,
            class_id=class_id,
            period="A",
            status="active",
            timestamp=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(ValueError, match="seat_id is required"):
        db.session.flush()

    db.session.rollback()
