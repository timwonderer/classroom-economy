from datetime import datetime, timezone

from flask import g
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_with_seat, seed_student_identity
from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, AttendanceSession, User
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, user: User, class_id: str):
    # Clear cached auth state from previous requests in the same test
    for attr in ('_auth_current_user_cache', '_auth_current_seat_cache', '_auth_current_system_admin_cache'):
        g.pop(attr, None)
    with client.session_transaction() as sess:
        teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
        if teacher_seat:
            set_canonical_context(
                sess,
                user_id=user.id,
                class_id=class_id,
                seat_id=teacher_seat.id,
                role="teacher",
            )


def _setup_shared_student_with_split_membership():
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-admin-tap-scope:seed"):
        teacher_a = seed_canonical_admin("tap_scope_admin_a").user
        teacher_b = seed_canonical_admin("tap_scope_admin_b").user
        class_a = seed_class_with_seat(
            teacher=teacher_a,
            join_code="TAPA01",
            student_first_name="AnchorA",
            student_last_name="Tap",
        ).class_row
        class_b = seed_class_with_seat(
            teacher=teacher_b,
            join_code="TAPB01",
            student_first_name="AnchorB",
            student_last_name="Tap",
        ).class_row
        student = seed_student_identity(
            class_id=class_b.class_id,
            first_name="Tap",
            last_name="S",
            username="tap_student",
        ).seat

        seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_b.class_id).first()
        assert seat is not None
        tap_event = AttendanceSession(
            seat_id=seat.id,
            class_id=seat.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(tap_event)
        db.session.flush()
    return teacher_a, teacher_b, class_a, class_b, seat, tap_event


def test_get_tap_entries_requires_student_in_current_class_scope(client):
    teacher_a, teacher_b, class_a, class_b, seat, _event = _setup_shared_student_with_split_membership()

    teacher_a_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_b_seat = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_a.id,
            class_id=class_a.class_id,
            seat_id=teacher_a_seat.id,
            role="teacher",
        )
    denied = client.get(f"/api/admin/tap-entries/{seat.id}")
    assert denied.status_code == 404

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_b.id,
            class_id=class_b.class_id,
            seat_id=teacher_b_seat.id,
            role="teacher",
        )
    allowed = client.get(f"/api/admin/tap-entries/{seat.id}")
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["student_id"] == seat.id
    assert data["periods"]


def test_delete_tap_entry_rejects_cross_class_scope_context(client):
    teacher_a, teacher_b, class_a, class_b, _seat, event = _setup_shared_student_with_split_membership()

    teacher_a_seat = Seat.query.filter_by(class_id=class_a.class_id, role="teacher").first()
    teacher_b_seat = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_a.id,
            class_id=class_a.class_id,
            seat_id=teacher_a_seat.id,
            role="teacher",
        )
    denied = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert denied.status_code == 404
    db.session.refresh(event)
    assert event.is_deleted is False

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_b.id,
            class_id=class_b.class_id,
            seat_id=teacher_b_seat.id,
            role="teacher",
        )
    allowed = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert allowed.status_code == 200
    db.session.refresh(event)
    assert event.is_deleted is True
    assert event.deleted_by_seat_id is None
