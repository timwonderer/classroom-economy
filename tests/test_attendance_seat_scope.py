from datetime import datetime, timezone

from app import db
from app.models import ClassEconomy, Seat, AttendanceSession, User, UserRole
from tests.helpers.class_scope import make_student_identity, create_class_scope
from tests.helpers.v2_fixtures import make_teacher


def test_attendance_session_records_seat_id(client):
    """AttendanceSession records seat_id correctly."""
    teacher = make_teacher("att_scope_teacher")
    db.session.flush()
    class_scope = create_class_scope(teacher_user=teacher, join_code="JOIN_TAP")
    student = make_student_identity(class_id=class_scope.class_id, first_name="Attend", last_name="A")
    db.session.commit()

    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_scope.class_id, role="student").first()
    assert seat is not None

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

    teacher = make_teacher("att_scope_teacher2")
    db.session.flush()
    class_scope = create_class_scope(teacher_user=teacher, join_code="JOIN_SCOPE")
    db.session.commit()

    event = AttendanceSession(
        seat_id=None,
        class_id=class_scope.class_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(event)
    with __import__('pytest').raises(sqlalchemy.exc.IntegrityError):
        db.session.flush()
    db.session.rollback()
