"""
Tests for join code generation and retry logic in the students management page.

This specifically tests that the MAX_JOIN_CODE_RETRIES constant is properly defined
and used when generating unique join codes for classroom blocks.
"""
import pyotp

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """Helper to create a student."""
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="A",
        block=block,
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=teacher.id,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Helper to log in an admin."""
    return client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


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
