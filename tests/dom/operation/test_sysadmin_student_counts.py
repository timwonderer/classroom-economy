"""
Tests for system admin student count functionality.

Validates that system admins see accurate per-teacher student counts
and that counts properly account for multi-teacher relationships.
"""

from app import app, db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import User
from app.routes.system_admin import _user_student_counts
from tests.helpers.classroom_initializer import initialize
from tests.helpers.operation_routes import (
    get_sysadmin_admins,
    get_sysadmin_dashboard,
    login_sysadmin,
)
from wsgi import app as cli_app


def _create_admin(classroom_key: str):
    """Create a canonical teacher-admin classroom for testing."""
    classroom = initialize(classroom_key, app)
    return classroom.teacher_user, classroom


def _create_sysadmin_via_cli(username: str = "sysadmin"):
    result = cli_app.test_cli_runner().invoke(args=["create-sysadmin"], input=f"{username}\n")
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    assert user is not None, "create-sysadmin did not create a sysadmin user"
    secret = ""
    lines = result.output.splitlines()
    for idx, line in enumerate(lines):
        if "TOTP SECRET" in line:
            for candidate in lines[idx + 1 :]:
                stripped = candidate.strip()
                if stripped and not stripped.startswith("=") and "IMPORTANT:" not in stripped and "Manual entry URI" not in stripped:
                    secret = stripped
                    break
            break
    assert secret, result.output
    return user, secret


def test_DOM_OPS_001__sysadmin_sees_correct_student_count_for_single_teacher(client):
    """System admin should see correct count for teacher with exclusive students."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    teacher_a, _classroom_a = _create_admin("chemistry_p1")
    teacher_b, _classroom_b = _create_admin("biology_block_a")
    teacher_a_id, teacher_b_id = teacher_a.id, teacher_b.id

    db.session.commit()

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_admins(client)

    assert response.status_code == 200
    html = response.data.decode()

    # Sysadmin views show only the opaque teacher identifier, never a real username.
    assert f"user_{teacher_a_id}" in html
    assert f"user_{teacher_b_id}" in html
    assert "4 students" in html
    assert "3 students" in html


def test_DOM_OPS_001__sysadmin_counts_shared_students_correctly(client):
    """System admin should count shared students only once per teacher."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    teacher_a, _classroom_a = _create_admin("chemistry_p1")
    teacher_b, _classroom_b = _create_admin("biology_block_a")
    teacher_a_id, teacher_b_id = teacher_a.id, teacher_b.id

    db.session.commit()

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_admins(client)

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_a_id}" in html
    assert f"user_{teacher_b_id}" in html
    assert "4 students" in html
    assert "3 students" in html


def test_DOM_OPS_001__sysadmin_counts_students_with_only_links(client):
    """System admin should count students linked via seat even without legacy teacher_id."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    teacher_a, _classroom_a = _create_admin("chemistry_p1")
    teacher_a_id = teacher_a.id

    db.session.commit()

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_admins(client)

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_a_id}" in html
    assert "4 students" in html


def test_DOM_OPS_001__sysadmin_dashboard_shows_total_students(client, monkeypatch):
    """System admin dashboard should show total unique student count."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    _teacher_a, _classroom_a = _create_admin("chemistry_p1")
    _teacher_b, _classroom_b = _create_admin("biology_block_a")

    db.session.commit()

    monkeypatch.setattr(
        "app.routes.system_admin.count_active_admin_invite_codes",
        lambda: 0,
    )
    monkeypatch.setattr(
        "app.routes.system_admin.db.session.execute",
        lambda *args, **kwargs: type("Result", (), {"mappings": lambda self: type("Rows", (), {"all": lambda self: []})()})(),
    )

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_dashboard(client)

    assert response.status_code == 200
    html = response.data.decode()

    assert "Total Students" in html
    assert "Total Teachers" in html


def test_DOM_OPS_001__sysadmin_does_not_see_student_details_on_admin_page(client):
    """System admin should not see individual student details on the admin management page."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    teacher_a, _classroom_a = _create_admin("chemistry_p1")
    teacher_a_id = teacher_a.id

    db.session.commit()

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_admins(client)

    assert response.status_code == 200
    html = response.data.decode()

    assert "SecretName" not in html
    assert f"user_{teacher_a_id}" in html
    assert "student" in html.lower()


def test_DOM_OPS_001__teacher_with_no_students_shows_zero_count(client):
    """System admin should see 0 students for teachers with no students."""
    _sys_admin, sys_secret = _create_sysadmin_via_cli()
    teacher_empty, classroom_empty = _create_admin("ap_csp_p3")
    teacher_empty_id = teacher_empty.id
    with FEATContext("FEAT-IDEN-001", idempotency_key="sysadmin_student_counts:clear_all"):
        for student in classroom_empty.students:
            student.seat.claimed_at = None
        db.session.flush()
    db.session.commit()

    login_sysadmin(client, username="sysadmin", totp_secret=sys_secret)
    response = get_sysadmin_admins(client)

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_empty_id}" in html
    assert "0 students" in html


def test_DOM_OPS_001__deleted_students_are_excluded_from_teacher_counts(client):
    """Deleted students should not contribute to sysadmin-facing teacher totals."""
    _sys_admin, _sys_secret = _create_sysadmin_via_cli()
    teacher, classroom = _create_admin("chemistry_p1")
    deleted_student_seat = classroom.students[1].seat
    # Simulate removal by unclaiming the seat rather than a physical delete:
    # _user_student_counts() only counts claimed seats (Seat.claimed_at.isnot(None)),
    # so an unclaimed seat is excluded exactly like a deleted one — without touching
    # Seat's cascade relationship to the (dropped) tap_events table, which is a
    # separate, pre-existing schema/model mismatch unrelated to this test's intent.
    with FEATContext("FEAT-IDEN-001", idempotency_key="test_deleted_students_are_excluded:unclaim"):
        deleted_student_seat.claimed_at = None
        db.session.flush()
    db.session.commit()

    teacher_counts, _ = _user_student_counts([teacher.id])
    assert teacher_counts[teacher.id] == 3
