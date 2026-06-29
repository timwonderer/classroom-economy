from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_with_seat
from tests.helpers.admin_context import login_admin as canonical_login_admin
from app.extensions import db
from app.models import Admin, ClassEconomy, StudentTeacher, TapEvent, User


def _login_admin(client, admin_id, join_code):
    admin = db.session.get(Admin, admin_id)
    economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    canonical_login_admin(
        client,
        admin_id,
        join_code,
        user_id=economy.user_id if economy else None,
        class_id=economy.class_id if economy else None,
    )


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

    class_a = create_class_scope(teacher=admin_a, join_code="TAPA01")
    class_b = create_class_scope(teacher=admin_b, join_code="TAPB01")

    student, seat = make_student_with_seat(
        class_id=class_b.class_id,
        join_code="TAPB01",
        block="A",
        first_name="Tap",
        last_name="S",
    )

    # Shared student-teacher association but the student is only seated in TAPB01.
    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=admin_a.id),
        StudentTeacher(student_id=student.id, teacher_id=admin_b.id),
    ])
    db.session.flush()

    tap_event = TapEvent(
        seat_id=seat.id,
        class_id=seat.class_id,
        join_code="TAPB01",
        period="A",
        status="active",
        reason="work",
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


def test_delete_tap_entry_rejects_cross_join_code_context(client):
    admin_a, admin_b, _student, event = _setup_shared_student_with_split_membership()

    _login_admin(client, admin_a.id, "TAPA01")
    denied = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert denied.status_code == 403
    db.session.refresh(event)
    assert event.is_deleted is False

    _login_admin(client, admin_b.id, "TAPB01")
    allowed = client.delete(f"/api/admin/tap-entries/{event.id}")
    assert allowed.status_code == 200
    db.session.refresh(event)
    assert event.is_deleted is True
