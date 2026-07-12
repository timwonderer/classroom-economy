from datetime import datetime, timezone

from flask import g
from tests.helpers.v2_fixtures import make_teacher
from app.extensions import db
from app.models import ClassEconomy, Seat, AttendanceSession, IdentityProfile, User, UserRole
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, user: User, join_code: str):
    # Clear cached auth state from previous requests in the same test
    for attr in ('_auth_current_user_cache', '_auth_current_seat_cache', '_auth_current_system_admin_cache'):
        g.pop(attr, None)
    economy = ClassEconomy.query.filter_by(join_code=join_code, user_id=user.id).first()
    with client.session_transaction() as sess:
        if economy and economy.class_id:
            teacher_seat = Seat.query.filter_by(class_id=economy.class_id, role="teacher").first()
            if teacher_seat:
                set_canonical_context(
                    sess,
                    user_id=user.id,
                    class_id=economy.class_id,
                    seat_id=teacher_seat.id,
                    role="teacher",
                )
        elif join_code:
            sess["current_join_code"] = join_code


def _setup_shared_student_with_split_membership():
    teacher_a = make_teacher("tap_scope_admin_a")
    teacher_b = make_teacher("tap_scope_admin_b")
    db.session.flush()

    class_a = create_class_scope(teacher_user=teacher_a, join_code="TAPA01")
    class_b = create_class_scope(teacher_user=teacher_b, join_code="TAPB01")
    db.session.flush()

    student_user = User(user_role=UserRole.STUDENT, username_hash="tap_student_hash", username_lookup_hash="tap_student_lookup")
    db.session.add(student_user)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Tap", last_name="S")
    db.session.add(profile)
    db.session.flush()

    seat = Seat(
        user_id=student_user.id,
        class_id=class_b.class_id,
        role="student",
        block="A",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id

    tap_event = AttendanceSession(
        seat_id=seat.id,
        class_id=seat.class_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(tap_event)
    db.session.commit()
    return teacher_a, teacher_b, seat, tap_event


def test_get_tap_entries_requires_student_in_current_join_code(client):
    teacher_a, teacher_b, seat, _event = _setup_shared_student_with_split_membership()

    class_a = ClassEconomy.query.filter_by(join_code="TAPA01").first()
    class_b = ClassEconomy.query.filter_by(join_code="TAPB01").first()
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


def test_delete_tap_entry_rejects_cross_join_code_context(client):
    teacher_a, teacher_b, _seat, event = _setup_shared_student_with_split_membership()

    class_a = ClassEconomy.query.filter_by(join_code="TAPA01").first()
    class_b = ClassEconomy.query.filter_by(join_code="TAPB01").first()
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
