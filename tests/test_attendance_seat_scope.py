from datetime import datetime, timezone

from app import db
from app.hash_utils import get_random_salt, hash_username_lookup
from app.models import Admin, ClassEconomy, Seat, StudentBlock, AttendanceSession, User
from tests.helpers.class_scope import make_student_identity


def _student() -> Student:
    return make_student_identity(block="A", first_name="Attend", last_name="A")


def _ensure_class_scope(join_code: str, class_id: str) -> ClassEconomy:
    class_scope = ClassEconomy.query.filter_by(join_code=join_code).first()
    if class_scope:
        return class_scope

    admin = Admin.query.first()
    if not admin:
        admin = Admin(totp_secret="JBSWY3DPEHPK3PXP", teacher_public_id=f"teacher_{join_code.lower()}")
        db.session.add(admin)
        db.session.flush()

    class_scope = ClassEconomy(
        user_id=admin.id,
        join_code=join_code,
        class_id=class_id,
        display_name=f"Scope {join_code}",
    )
    db.session.add(class_scope)
    db.session.flush()
    return class_scope


def test_attendance_session_requires_seat_id(client):
    """AttendanceSession requires seat_id — inserting without it must fail."""
    import pytest

    student = _student()
    db.session.add(student)
    db.session.flush()

    class_scope = _ensure_class_scope("JOIN_TAP", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    user = User(username_hash=hash_username_lookup(f"tap_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(
        user_id=user.id,
        class_id=class_scope.class_id,
        join_code="JOIN_TAP",
        block="A",
    )
    db.session.add(seat)
    db.session.flush()

    event = AttendanceSession(
        seat_id=seat.id,
        class_id=class_scope.class_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    db.session.commit()

    db.session.refresh(event)
    assert event.seat_id == seat.id


def test_student_block_autofills_seat_id_from_class_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    class_scope = _ensure_class_scope("JOIN_SB", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    user = User(username_hash=hash_username_lookup(f"sb_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(
        user_id=user.id,
        class_id=class_scope.class_id,
        join_code="JOIN_SB",
        block="A",
    )
    db.session.add(seat)
    db.session.flush()

    student_block = StudentBlock(
        user_id=student.user_id,
        class_id=class_scope.class_id,
        join_code="JOIN_SB",
        period="A",
    )
    db.session.add(student_block)
    db.session.commit()

    db.session.refresh(student_block)
    assert student_block.seat_id == seat.id


def test_attendance_session_requires_seat_id(client):
    """AttendanceSession requires seat_id — inserting without it must fail at DB level."""
    import sqlalchemy

    class_scope = _ensure_class_scope("JOIN_SCOPE", "cccccccc-cccc-cccc-cccc-cccccccccccc")

    event = AttendanceSession(
        seat_id=None,
        class_id=class_scope.class_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    with __import__('pytest').raises(sqlalchemy.exc.IntegrityError):
        db.session.flush()
    db.session.rollback()
