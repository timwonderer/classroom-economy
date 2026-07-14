from datetime import datetime, timezone

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, AttendanceSession, User, UserRole
from tests.helpers.class_scope import make_student_identity, create_class_scope
from tests.helpers.v2_fixtures import make_teacher


def test_attendance_session_records_seat_id(client):
    """AttendanceSession records seat_id correctly."""
    teacher = make_teacher("att_scope_teacher")
    db.session.flush()
    class_scope = create_class_scope(teacher_user=teacher)
    student = make_student_identity(class_id=class_scope.class_id, first_name="Attend", last_name="A")

    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_scope.class_id, role="student").first()
    assert seat is not None

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance_seat_scope:records"):
        event = AttendanceSession(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(event)
        db.session.flush()

    db.session.refresh(event)
    assert event.seat_id == seat.id


def test_attendance_session_requires_seat_id(client):
    """AttendanceSession requires seat_id — inserting without it must fail at DB level."""
    import sqlalchemy

    teacher = make_teacher("att_scope_teacher2")
    db.session.flush()
    class_scope = create_class_scope(teacher_user=teacher)

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance_seat_scope:requires"):
        event = AttendanceSession(
            seat_id=None,
            class_id=class_scope.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(event)
        with __import__('pytest').raises(sqlalchemy.exc.IntegrityError):
            db.session.flush()
        db.session.rollback()
