"""
Tests for join code generation and retry logic in the students management page.

This specifically tests that the MAX_JOIN_CODE_RETRIES constant is properly defined
and used when generating unique join codes for classroom blocks.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.models import User, UserRole, Admin, Seat, IdentityProfile, StudentTeacher


def _create_admin(username: str) -> tuple[Admin, str]:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, teacher: Admin, block: str = "A") -> Seat:
    """Helper to create a canonical student seat."""
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash=f"{first_name.lower()}_{block.lower()}_hash",
        username_lookup_hash=f"{first_name.lower()}_{block.lower()}_lookup",
    )
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(
        user_id=student_user.id,
        block=block,
        block_identifier=block,
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student", first_name=first_name, last_initial="A"))
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.commit()
    return seat


def _login_admin(client, admin: Admin, secret: str):
    """Helper to log in an admin."""
    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def test_students_page_generates_join_codes_for_blocks(client):
    """
    Test that accessing /admin/students doesn't crash when generating join codes.
    
    This verifies that MAX_JOIN_CODE_RETRIES and related constants are defined.
    Regression test for: NameError: name 'MAX_JOIN_CODE_RETRIES' is not defined
    """
    teacher, secret = _create_admin("teacher-with-blocks")
    
    # Create students in different blocks (without pre-existing join codes)
    _create_student("Alice", teacher, block="A")
    _create_student("Bob", teacher, block="B")
    _create_student("Charlie", teacher, block="C")
    
    _login_admin(client, teacher, secret)
    
    # This should not raise NameError about MAX_JOIN_CODE_RETRIES
    # The page will attempt to generate join codes for each block
    response = client.get("/admin/students")
    
    # The page should load successfully
    assert response.status_code == 200
    
    # Verify the page contains the student names
    body = response.get_data(as_text=True)
    assert "Alice" in body
    assert "Bob" in body
    assert "Charlie" in body
    
    # Verify join codes are displayed on the page for each block
    # The system generates join codes on-demand but may not persist them
    # unless there are TeacherBlock seat records (which require student info)
    # For this test, we're primarily verifying no NameError is raised
    assert "Join Code:" in body or "join-code" in body.lower()


def test_students_page_works_with_no_students(client):
    """
    Test that the students page works even with no students.
    
    Verifies the constants are defined even when the join code generation
    code path may not be exercised.
    """
    teacher, secret = _create_admin("teacher-without-students")
    
    _login_admin(client, teacher, secret)
    
    # Access the students page with no students
    response = client.get("/admin/students")
    
    # Should still work without errors
    assert response.status_code == 200
