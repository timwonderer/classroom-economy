from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import ClassEconomy, ClassMembership, Seat, Student, StudentTeacher, AttendanceSession
from tests.helpers.v2_fixtures import make_admin


def _setup_scoped_student(with_seat: bool = True):
    teacher = make_admin("tap_inv_teacher", "secret")
    db.session.add(teacher)
    db.session.flush()

    cls = ClassEconomy(
        join_code="TINV01",
        teacher_id=teacher.id,
        status="active",
        created_by_admin_id=teacher.id,
    )
    db.session.add(cls)
    db.session.flush()

    db.session.add(
        ClassMembership(
            join_code=cls.join_code,
            class_id=cls.class_id,
            admin_id=teacher.id,
            role="admin",
        )
    )

    student = Student(first_name="Tap", last_initial="I", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.add(
        ClassMembership(
            join_code=cls.join_code,
            class_id=cls.class_id,
            student_id=student.id,
            role="student",
        )
    )

    seat = None
    if with_seat:
        seat = Seat(
            student_id=student.id,
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


def test_attendance_session_rejects_missing_class_id_and_seat_id():
    """AttendanceSession without class_id and seat_id fails at DB level (NOT NULL)."""
    import sqlalchemy

    student_id, _seat_id, _class_id = _setup_scoped_student(with_seat=False)

    db.session.add(
        AttendanceSession(
            student_id=student_id,
            period="A",
            started_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.session.flush()

    db.session.rollback()


def test_attendance_session_requires_seat_even_when_class_is_present():
    """AttendanceSession with class_id but without seat_id fails at DB level (NOT NULL)."""
    import sqlalchemy

    student_id, _seat_id, class_id = _setup_scoped_student(with_seat=False)

    db.session.add(
        AttendanceSession(
            student_id=student_id,
            class_id=class_id,
            period="A",
            started_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.session.flush()

    db.session.rollback()
