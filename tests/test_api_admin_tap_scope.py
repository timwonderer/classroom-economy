from datetime import datetime, timezone

from flask import g
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Seat, StudentTeacher, AttendanceSession, IdentityProfile, User, UserRole
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, admin_id, join_code):
    # Clear cached auth state from previous requests in the same test
    for attr in ('_auth_current_user_cache', '_auth_current_seat_cache', '_auth_current_system_admin_cache'):
        g.pop(attr, None)
    admin = db.session.get(Admin, admin_id)
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first() if admin else None
    economy = ClassEconomy.query.filter_by(join_code=join_code, user_id=admin_id).first()
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        if user and economy and economy.class_id:
            teacher_seat = Seat.query.filter_by(class_id=economy.class_id, role="teacher").first()
            if teacher_seat:
                set_canonical_context(
                    sess,
                    user_id=user.id,
                    class_id=economy.class_id,
                    seat_id=teacher_seat.id,
                    role="teacher",
                    join_code=join_code,
                )
        elif join_code:
            sess["current_join_code"] = join_code


def _setup_shared_student_with_split_membership():
    admin_a = make_admin("tap_scope_admin_a", "secret-a")
    admin_b = make_admin("tap_scope_admin_b", "secret-b")
    db.session.add_all([admin_a, admin_b])
    db.session.flush()

    # Create User records for both admins (required for auth)
    user_a = User(user_role="teacher", username_hash=admin_a.username_hash, username_lookup_hash=admin_a.username_lookup_hash)
    user_b = User(user_role="teacher", username_hash=admin_b.username_hash, username_lookup_hash=admin_b.username_lookup_hash)
    db.session.add_all([user_a, user_b])
    db.session.flush()

    student_user = User(user_role=UserRole.STUDENT, username_hash="tap_student_hash", username_lookup_hash="tap_student_lookup")
    db.session.add(student_user)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Tap", last_initial="S")
    db.session.add(profile)
    db.session.flush()

    class_a = ClassEconomy(join_code="TAPA01", user_id=admin_a.id, status="active", created_by_admin_id=admin_a.id)
    class_b = ClassEconomy(join_code="TAPB01", user_id=admin_b.id, status="active", created_by_admin_id=admin_b.id)
    db.session.add_all([class_a, class_b])
    db.session.flush()

    seat = Seat(
        user_id=student_user.id,
        class_id=class_b.class_id,
        join_code="TAPB01",
        role="student",
        block_identifier="A",
        block="A",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id

    db.session.add_all([
        StudentTeacher(user_id=student_user.id, teacher_id=admin_a.id),
        StudentTeacher(user_id=student_user.id, teacher_id=admin_b.id),
        ClassMembership(join_code="TAPA01", class_id=class_a.class_id, admin_id=admin_a.id, role="admin"),
        ClassMembership(join_code="TAPB01", class_id=class_b.class_id, admin_id=admin_b.id, role="admin"),
        ClassMembership(join_code="TAPB01", class_id=class_b.class_id, user_id=student_user.id, role="student"),
    ])
    db.session.flush()

    tap_event = AttendanceSession(
        seat_id=seat.id,
        class_id=seat.class_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(tap_event)
    db.session.commit()
    return admin_a, admin_b, seat, tap_event


def test_get_tap_entries_requires_student_in_current_join_code(client):
    admin_a, admin_b, seat, _event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.get(f"/api/admin/tap-entries/{seat.id}")
    assert denied.status_code == 404

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.get(f"/api/admin/tap-entries/{seat.id}")
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["student_id"] == seat.id
    assert "A" in data["periods"]


def test_delete_tap_entry_rejects_cross_join_code_context(client):
    admin_a, admin_b, _seat, event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert denied.status_code == 404
    db.session.refresh(event)
    assert event.is_deleted is False

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert allowed.status_code == 200
    db.session.refresh(event)
    assert event.is_deleted is True
    assert event.deleted_by_seat_id is None
