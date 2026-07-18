from datetime import datetime, timezone

from flask import g
from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, AttendanceSession, User
from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import api_delete_tap_entry, api_get_tap_entry


def _setup_shared_student_with_split_membership():
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-admin-tap-scope:seed"):
        class_a = initialize("chemistry_p1", None)
        class_b = initialize("biology_block_a", None)
        teacher_a = class_a.teacher_user
        teacher_b = class_b.teacher_user
        seat = class_b.students[0].seat
        assert seat is not None
        tap_event = AttendanceSession(
            seat_id=seat.id,
            class_id=seat.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(tap_event)
        db.session.flush()
    return teacher_a, teacher_b, class_a, class_b, seat, tap_event


def test_DOM_IDEN_006__get_tap_entries_requires_student_in_current_class_scope(client):
    teacher_a, teacher_b, class_a, class_b, seat, _event = _setup_shared_student_with_split_membership()

    teacher_a_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_b_seat = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = teacher_a_seat.id
    denied = api_get_tap_entry(client, seat.id)
    assert denied.status_code == 404

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_b.id
        sess["current_class_id"] = class_b.class_id
        sess["current_seat_id"] = teacher_b_seat.id
    allowed = api_get_tap_entry(client, seat.id)
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["student_id"] == seat.id
    assert data["periods"]


def test_DOM_IDEN_006__delete_tap_entry_rejects_cross_class_scope_context(client):
    teacher_a, teacher_b, class_a, class_b, _seat, event = _setup_shared_student_with_split_membership()

    teacher_a_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_b_seat = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = teacher_a_seat.id
    denied = api_delete_tap_entry(client, event.id)
    assert denied.status_code == 404
    db.session.refresh(event)
    assert event.is_deleted is False

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_b.id
        sess["current_class_id"] = class_b.class_id
        sess["current_seat_id"] = teacher_b_seat.id
    allowed = api_delete_tap_entry(client, event.id)
    assert allowed.status_code == 200
    db.session.refresh(event)
    assert event.is_deleted is True
    assert event.deleted_by_seat_id is None
