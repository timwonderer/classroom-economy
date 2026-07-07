from datetime import datetime, timezone

from app import db
from app.models import ClassEconomy, Seat, AttendanceSession, User, UserRole
from tests.helpers.class_scope import make_student_identity, create_class_scope


def _student():
    return make_student_identity(block="A", first_name="Attend", last_name="A")


def _ensure_class_scope(join_code: str, class_id: str) -> ClassEconomy:
    class_scope = ClassEconomy.query.filter_by(join_code=join_code).first()
    if class_scope:
        return class_scope

    teacher_user = User(
        user_role=UserRole.TEACHER,
        username_hash=f"teacher_{join_code.lower()}_hash",
        username_lookup_hash=f"teacher_{join_code.lower()}_lookup",
        password_hash="secret",
    )
    db.session.add(teacher_user)
    db.session.flush()

    class_scope = create_class_scope(
        teacher=teacher_user,
        teacher_user_id=teacher_user.id,
        join_code=join_code,
        student=None,
        block="A",
        display_name=f"Scope {join_code}",
    )
    return class_scope


def test_attendance_session_records_seat_id(client):
    """AttendanceSession records seat_id correctly."""
    student = _student()
    db.session.add(student)
    db.session.flush()

    class_scope = _ensure_class_scope("JOIN_TAP", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    user = User(username_hash=f"tap_user_{student.id}", username_lookup_hash=f"tap_lookup_{student.id}", password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(
        user_id=user.id,
        class_id=class_scope.class_id,
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
