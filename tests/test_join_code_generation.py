"""
Tests for display-alias generation and retry logic in the students management page.

This specifically tests that the MAX_JOIN_CODE_RETRIES constant is properly defined
and used when generating unique display aliases for classroom blocks.
"""
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher
import pyotp
from datetime import datetime, timezone

from app import db
from app.models import User, Seat, IdentityProfile


def _create_admin(username: str) -> tuple[str]:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = seed_canonical_admin(username, secret).user
    db.session.commit()
    return admin, secret


def _login_admin(client, admin: User, class_id: str):
    """Helper to log in an admin via canonical class context."""
    teacher_seat = Seat.query.filter_by(user_id=admin.id, class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    login_teacher(client, admin, class_id=class_id, seat_id=teacher_seat.id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )


def test_students_page_generates_display_aliases_for_blocks(client):
    """
    Test that accessing /admin/students doesn't crash when generating display aliases.

    This verifies that MAX_JOIN_CODE_RETRIES and related constants are defined.
    Regression test for: NameError: name 'MAX_JOIN_CODE_RETRIES' is not defined
    """
    teacher, secret = _create_admin("teacher-with-blocks")

    class_row = create_class_scope(
        teacher_user=teacher, join_code="JCG-ABC")

    seat_a = make_student_identity(class_id=class_row.class_id, first_name="Alice", last_name="A", claimed=True)
    seat_b = make_student_identity(class_id=class_row.class_id, first_name="Bob", last_name="B", claimed=True)
    seat_c = make_student_identity(class_id=class_row.class_id, first_name="Charlie", last_name="C", claimed=True)
    db.session.commit()

    _login_admin(client, teacher, class_row.class_id)

    # This should not raise NameError about MAX_JOIN_CODE_RETRIES
    response = client.get("/admin/students")

    # The page should load successfully
    assert response.status_code == 200


def test_students_page_works_with_no_students(client):
    """
    Test that the students page works even with no students.

    Verifies the constants are defined even when the display-alias generation
    code path may not be exercised.
    """
    teacher, secret = _create_admin("teacher-without-students")

    class_row = create_class_scope(
        teacher_user=teacher, join_code="JCG-EMPTY")
    db.session.commit()

    _login_admin(client, teacher, class_id=class_row.class_id)

    response = client.get("/admin/students")

    assert response.status_code == 200
