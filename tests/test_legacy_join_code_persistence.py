"""
Tests for join code persistence in legacy classes.

This test verifies that when a teacher has students from before the join code
system was implemented (i.e., students exist but no TeacherBlock entries),
the join codes generated for those blocks persist across page loads.

Regression test for: "Join code for legacy classes does not persist"
"""

# Constants
JOIN_CODE_LENGTH = 6  # Length of join codes (should match app.utils.join_code.generate_join_code)
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


def _create_legacy_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """
    Helper to create a legacy student (no TeacherBlock entry).
    
    This simulates a student that was created before the join code system
    was implemented.
    """
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="L",
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


def _extract_join_code_from_page(html: str, block: str) -> str:
    """
    Extract the join code for a specific block from the HTML page.
    
    The join code is displayed in an input element with id="join-code-{block}"
    """
    import re
    # Look for the input element with id="join-code-{block}" and extract its value
    pattern = rf'<input[^>]*id="join-code-{block}"[^>]*value="([A-Z0-9]{{{JOIN_CODE_LENGTH}}})"'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Alternative pattern if value attribute comes before id
    pattern = rf'<input[^>]*value="([A-Z0-9]{{{JOIN_CODE_LENGTH}}})"[^>]*id="join-code-{block}"'
    match = re.search(pattern, html, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def test_legacy_class_join_code_persists_across_page_loads(client):
    """
    Test that join codes for legacy classes persist across page loads.
    
    This is a regression test for the bug where join codes were generated
    on-the-fly but not persisted to the database, causing them to change
    on every page load.
    """
    teacher, secret = _create_admin("teacher-with-legacy-class")
    
    # Create a legacy student (no TeacherBlock entry)
    _create_legacy_student("LegacyStudent", teacher, block="A")
    
    # Verify no TeacherBlock entry exists initially
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").count() == 0
    
    _login_admin(client, teacher, secret)
    
    # First page load - should generate and persist join code
    response1 = client.get("/admin/students")
    assert response1.status_code == 200
    html1 = response1.get_data(as_text=True)
    
    # Extract join code from first page load
    join_code_1 = _extract_join_code_from_page(html1, "A")
    assert join_code_1 is not None, "Join code should be displayed on the page"
    assert len(join_code_1) == JOIN_CODE_LENGTH, f"Join code should be {JOIN_CODE_LENGTH} characters, got {len(join_code_1)}"
    
    # Verify TeacherBlock was created and persisted
    teacher_block = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").first()
    assert teacher_block is not None, "TeacherBlock should be created and persisted"
    assert teacher_block.join_code == join_code_1, "Persisted join code should match displayed code"
    
    # Second page load - should use the same join code from database
    response2 = client.get("/admin/students")
    assert response2.status_code == 200
    html2 = response2.get_data(as_text=True)
    
    # Extract join code from second page load
    join_code_2 = _extract_join_code_from_page(html2, "A")
    assert join_code_2 is not None, "Join code should be displayed on second load"
    
    # THE KEY ASSERTION: Join codes must be the same across page loads
    assert join_code_1 == join_code_2, \
        f"Join code changed between page loads: {join_code_1} -> {join_code_2}. " \
        "This means the join code is not persisting properly."


def test_legacy_class_multiple_blocks_have_different_join_codes(client):
    """
    Test that different blocks in a legacy class get different join codes.
    
    Each period/block should have its own unique join code.
    """
    teacher, secret = _create_admin("teacher-with-multiple-blocks")
    
    # Create legacy students in different blocks
    _create_legacy_student("StudentA", teacher, block="A")
    _create_legacy_student("StudentB", teacher, block="B")
    _create_legacy_student("StudentC", teacher, block="C")
    
    _login_admin(client, teacher, secret)
    
    # Load the page once to generate join codes
    response = client.get("/admin/students")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Extract join codes for all blocks
    join_code_a = _extract_join_code_from_page(html, "A")
    join_code_b = _extract_join_code_from_page(html, "B")
    join_code_c = _extract_join_code_from_page(html, "C")
    
    # All join codes should exist
    assert join_code_a is not None, "Join code for block A should exist"
    assert join_code_b is not None, "Join code for block B should exist"
    assert join_code_c is not None, "Join code for block C should exist"
    
    # All join codes should be different
    assert join_code_a != join_code_b, "Block A and B should have different join codes"
    assert join_code_b != join_code_c, "Block B and C should have different join codes"
    assert join_code_a != join_code_c, "Block A and C should have different join codes"
    
    # Verify all are persisted in database
    block_a = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").first()
    block_b = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="B").first()
    block_c = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="C").first()
    
    assert block_a is not None and block_a.join_code == join_code_a
    assert block_b is not None and block_b.join_code == join_code_b
    assert block_c is not None and block_c.join_code == join_code_c
