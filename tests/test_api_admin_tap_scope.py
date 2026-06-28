from datetime import datetime, timezone

from flask import g
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, ClassEconomy, ClassMembership, Seat, Student, StudentTeacher, AttendanceSession, IdentityProfile, User


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
        if user:
            sess["user_id"] = user.id
        sess["current_join_code"] = join_code
        if economy and economy.class_id:
            sess["current_class_id"] = economy.class_id
        else:
            sess.pop("current_class_id", None)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


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

    student = Student(first_name="Tap", last_initial="S", block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    class_a = ClassEconomy(join_code="TAPA01", user_id=admin_a.id, status="active", created_by_admin_id=admin_a.id)
    class_b = ClassEconomy(join_code="TAPB01", user_id=admin_b.id, status="active", created_by_admin_id=admin_b.id)
    db.session.add_all([class_a, class_b])
    db.session.flush()

    # Shared student-teacher association but student class membership only in TAPB01.
    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=admin_a.id),
        StudentTeacher(student_id=student.id, teacher_id=admin_b.id),
        ClassMembership(join_code="TAPA01", class_id=class_a.class_id, admin_id=admin_a.id, role="admin"),
        ClassMembership(join_code="TAPB01", class_id=class_b.class_id, admin_id=admin_b.id, role="admin"),
        ClassMembership(join_code="TAPB01", class_id=class_b.class_id, student_id=student.id, role="student"),
    ])
    db.session.flush()
    seat = Seat.query.filter_by(
        student_id=student.id,
        join_code="TAPB01",
    ).first()
    if not seat:
        seat = Seat(student_id=student.id, class_id=class_b.class_id, join_code="TAPB01", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add(seat)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name=student.first_name, last_initial=student.last_initial))
        db.session.add(seat)
        db.session.flush()

    seat_row = Seat.query.filter_by(student_id=student.id, class_id=seat.class_id).first()
    if not seat_row:
        seat_row = Seat(
            student_id=student.id,
            class_id=seat.class_id,
            join_code="TAPB01",
            role="student",
            block_identifier="A",
            block="A",
        )
        db.session.add(seat_row)
        db.session.flush()

    tap_event = AttendanceSession(
        student_id=student.id,
        seat_id=seat_row.id,
        class_id=seat.class_id,
        period="A",
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(tap_event)
    db.session.commit()
    return admin_a, admin_b, student, tap_event


def test_get_tap_entries_requires_student_in_current_join_code(client):
    admin_a, admin_b, student, _event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.get(f"/api/admin/tap-entries/{student.id}")
    assert denied.status_code == 404

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.get(f"/api/admin/tap-entries/{student.id}")
    assert allowed.status_code == 200
    data = allowed.get_json()
    assert data["student_id"] == student.id
    assert "A" in data["periods"]


def test_delete_tap_entry_rejects_cross_join_code_context(client):
    admin_a, admin_b, _student, event = _setup_shared_student_with_split_membership()

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
