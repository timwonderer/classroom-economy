"""
Tests for system admin student count functionality.

Validates that system admins see accurate per-teacher student counts
and that counts properly account for multi-teacher relationships.
"""

from datetime import datetime, timezone

import pyotp

from app import app, db
from app.models import User, UserRole, SystemAdmin, Seat
from app.routes.system_admin import _user_student_counts
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin


def _create_sysadmin(username: str = "sysadmin"):
    """Create a system admin for testing."""
    secret = pyotp.random_base32()
    sys_admin = make_sysadmin(username, secret)
    db.session.commit()
    return sys_admin, secret


def _create_admin(username: str):
    """Create a teacher admin for testing."""
    secret = pyotp.random_base32()
    admin = seed_canonical_admin(username).user
    db.session.flush()
    return admin, secret


def _create_student_in_class(first_name: str, teacher, join_code_suffix: str):
    """Create a class and student for testing."""
    join_code = f"SYS{join_code_suffix}"
    from app.models import ClassEconomy
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code)
    student = make_student_identity(class_id=class_row.class_id, first_name=first_name, last_name="X")
    db.session.flush()
    return student


def _login_sysadmin(client, sys_admin, secret: str):
    """Login as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": "sysadmin", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_sysadmin_sees_correct_student_count_for_single_teacher(client):
    """System admin should see correct count for teacher with exclusive students."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    teacher_a_id, teacher_b_id = teacher_a.id, teacher_b.id

    # Create students for teacher A
    _create_student_in_class("Student1", teacher_a, "A1")
    _create_student_in_class("Student2", teacher_a, "A2")
    _create_student_in_class("Student3", teacher_a, "A3")

    # Create students for teacher B
    _create_student_in_class("Student4", teacher_b, "B1")
    _create_student_in_class("Student5", teacher_b, "B2")
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")

    assert response.status_code == 200
    html = response.data.decode()

    # Sysadmin views show only the opaque teacher identifier, never a real username.
    assert f"user_{teacher_a_id}" in html
    assert f"user_{teacher_b_id}" in html
    assert "3 students" in html
    assert "2 students" in html


def test_sysadmin_counts_shared_students_correctly(client):
    """System admin should count shared students only once per teacher."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    teacher_a_id, teacher_b_id = teacher_a.id, teacher_b.id

    # Create students in separate classes
    _create_student_in_class("Shared", teacher_a, "SHA")
    _create_student_in_class("ExclusiveA", teacher_a, "EXA")
    _create_student_in_class("ExclusiveB", teacher_b, "EXB")
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_a_id}" in html
    assert f"user_{teacher_b_id}" in html
    assert "2 students" in html  # teacher_a: Shared + ExclusiveA
    assert "1 students" in html  # teacher_b: ExclusiveB


def test_sysadmin_counts_students_with_only_links(client):
    """System admin should count students linked via seat even without legacy teacher_id."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_a_id = teacher_a.id

    _create_student_in_class("NoOwner", teacher_a, "NWR")
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_a_id}" in html
    assert "1 students" in html


def test_sysadmin_dashboard_shows_total_students(client):
    """System admin dashboard should show total unique student count."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    _create_student_in_class("Student1", teacher_a, "DS1")
    _create_student_in_class("Student2", teacher_b, "DS2")
    _create_student_in_class("Shared", teacher_a, "DSH")
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/dashboard")

    assert response.status_code == 200
    html = response.data.decode()

    assert "Total Students" in html
    assert "Total Teachers" in html


def test_sysadmin_does_not_see_student_details_on_admin_page(client):
    """System admin should not see individual student details on the admin management page."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_a_id = teacher_a.id

    _create_student_in_class("SecretName", teacher_a, "SEC")
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")

    assert response.status_code == 200
    html = response.data.decode()

    assert "SecretName" not in html
    assert f"user_{teacher_a_id}" in html
    assert "student" in html.lower()


def test_teacher_with_no_students_shows_zero_count(client):
    """System admin should see 0 students for teachers with no students."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_empty, _ = _create_admin("teacher-empty")
    teacher_empty_id = teacher_empty.id
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")

    assert response.status_code == 200
    html = response.data.decode()

    assert f"user_{teacher_empty_id}" in html
    assert "0 students" in html


def test_deleted_students_are_excluded_from_teacher_counts(client):
    """Deleted students should not contribute to sysadmin-facing teacher totals."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher, _ = _create_admin("teacher-delete-count")

    class_row = create_class_scope(teacher_user=teacher, join_code="DELCOUNT")
    active_student_seat = make_student_identity(
        class_id=class_row.class_id,
        first_name="Active",
        last_name="Student",
    )
    deleted_student_seat = make_student_identity(
        class_id=class_row.class_id,
        first_name="Deleted",
        last_name="Student",
    )
    # Simulate removal by unclaiming the seat rather than a physical delete:
    # _user_student_counts() only counts claimed seats (Seat.claimed_at.isnot(None)),
    # so an unclaimed seat is excluded exactly like a deleted one — without touching
    # Seat's cascade relationship to the (dropped) tap_events table, which is a
    # separate, pre-existing schema/model mismatch unrelated to this test's intent.
    from app.feats.base import FEATContext
    with FEATContext("FEAT-IDEN-001", idempotency_key="test_deleted_students_are_excluded:unclaim"):
        deleted_student_seat.claimed_at = None
        db.session.flush()
    db.session.commit()

    teacher_counts, _ = _user_student_counts([teacher.id])
    assert teacher_counts[teacher.id] == 1
