from datetime import datetime, timezone

from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession
from tests.helpers.classroom_initializer import initialize


def test_DOM_ATT_001__attendance_session_records_seat_id(client):
    """AttendanceSession records seat_id correctly."""
    classroom = initialize("chemistry_p1", client.application)
    seat = classroom.students[0].seat

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance_seat_scope:records"):
        event = AttendanceSession(
            target_seat_id=seat.id,
            class_id=classroom.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(event)
        db.session.flush()

    db.session.refresh(event)
    assert event.target_seat_id == seat.id


def test_DOM_ATT_001__attendance_session_requires_seat_id(client):
    """AttendanceSession requires seat_id — inserting without it must fail at DB level."""
    import sqlalchemy

    classroom = initialize("chemistry_p1", client.application)

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance_seat_scope:requires"):
        event = AttendanceSession(
            target_seat_id=None,
            class_id=classroom.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(event)
        with __import__('pytest').raises(sqlalchemy.exc.IntegrityError):
            db.session.flush()
        db.session.rollback()
