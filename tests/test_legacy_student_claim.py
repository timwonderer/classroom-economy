"""
Test that students can claim accounts in legacy classes using join code.

This test verifies that when a teacher has legacy students (created before join code system),
new students can still use the join code to claim their accounts by uploading a roster.
"""

import pyotp

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from hash_utils import get_random_salt, hash_username, hash_hmac


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


def test_new_student_can_claim_in_legacy_class(client):
    """
    Test that new students can claim accounts in legacy classes using join code.
    
    Scenario:
    1. Teacher has a legacy class (students exist, but no TeacherBlock entries initially)
    2. System generates join code for the legacy class (via placeholder)
    3. Teacher uploads a new roster with a new student
    4. New student should be able to claim their account using the join code
    """
    teacher, secret = _create_admin("teacher-with-legacy-and-new")
    
    # Create a legacy student (no TeacherBlock entry initially)
    _create_legacy_student("LegacyStudent", teacher, block="A")
    
    # Verify no TeacherBlock entry exists initially
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").count() == 0
    
    _login_admin(client, teacher, secret)
    
    # Visit students page to generate join code for legacy class
    response = client.get("/admin/students")
    assert response.status_code == 200
    
    # Verify join code was generated (via placeholder TeacherBlock)
    teacher_blocks = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").all()
    assert len(teacher_blocks) > 0, "Join code should have been generated"
    
    # Find the placeholder (it stores the join code)
    placeholder = next((tb for tb in teacher_blocks if tb.first_name == "__JOIN_CODE_PLACEHOLDER__"), None)
    assert placeholder is not None, "Placeholder should exist to store join code"
    join_code = placeholder.join_code
    
    # Now simulate teacher uploading a roster with a new student
    # This would create a real TeacherBlock entry (not a placeholder)
    new_salt = get_random_salt()
    # Corrected test data: Last name Smith -> Last Initial S
    # Admin logic uses Last Initial for hash generation
    new_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="NewStudent",
        last_initial="S",
        last_name_hash_by_part=[hash_hmac("smith".encode(), new_salt)],
        dob_sum=2025,
        salt=new_salt,
        first_half_hash=hash_hmac("S2025".encode(), new_salt),
        join_code=join_code,  # Same join code as the legacy class
        is_claimed=False,
    )
    db.session.add(new_seat)
    db.session.commit()
    
    # Logout admin and try to claim as student
    client.get("/admin/logout")
    
    # Student tries to claim their account using join code
    claim_response = client.post(
        "/student/claim-account",
        data={
            "join_code": join_code,
            "first_initial": "N",
            "last_name": "Smith",
            "dob_sum": "2025",
        },
        follow_redirects=False,
    )
    
    # Should redirect to create username (successful claim)
    assert claim_response.status_code == 302, \
        f"Expected redirect (302), got {claim_response.status_code}"
    assert "/student/create-username" in claim_response.location, \
        f"Should redirect to create-username, got {claim_response.location}"
    
    # Verify the seat was claimed
    new_seat_after = TeacherBlock.query.get(new_seat.id)
    assert new_seat_after.is_claimed, "Seat should be marked as claimed"
    assert new_seat_after.student_id is not None, "Seat should be linked to a student"


def test_join_code_persists_when_new_students_added(client):
    """
    Test that the join code persists when new students are added to a legacy class.
    
    This ensures that:
    1. Legacy class gets a join code (via placeholder)
    2. When teacher adds new students to roster, they use the SAME join code
    3. The join code doesn't change between page loads
    """
    teacher, secret = _create_admin("teacher-adding-students")
    
    # Create a legacy student
    _create_legacy_student("LegacyStudent1", teacher, block="B")
    
    _login_admin(client, teacher, secret)
    
    # First load - generates join code
    response1 = client.get("/admin/students")
    assert response1.status_code == 200
    
    # Get the generated join code from any TeacherBlock for this block
    # It could be stored in either a placeholder or a real seat
    teacher_block = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        block="B"
    ).first()
    assert teacher_block is not None, "Should have a TeacherBlock with join code"
    join_code_1 = teacher_block.join_code
    
    # Teacher adds a new student to roster (using the same join code)
    new_salt = get_random_salt()
    new_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name="NewStudent2",
        last_initial="N",
        last_name_hash_by_part=[hash_hmac("jones".encode(), new_salt)],
        dob_sum=2026,
        salt=new_salt,
        first_half_hash=hash_hmac("N2026".encode(), new_salt),
        join_code=join_code_1,  # Must use the same join code
        is_claimed=False,
    )
    db.session.add(new_seat)
    db.session.commit()
    
    # Second load - join code should be the same
    response2 = client.get("/admin/students")
    assert response2.status_code == 200
    
    # Verify join code is still the same (check any TeacherBlock for this block)
    all_blocks = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        block="B"
    ).all()
    
    # All blocks should have the same join code
    join_codes = set(tb.join_code for tb in all_blocks)
    assert len(join_codes) == 1, \
        f"All TeacherBlocks in the same block should have the same join code, got: {join_codes}"
    join_code_2 = join_codes.pop()
    
    assert join_code_1 == join_code_2, \
        f"Join code changed: {join_code_1} -> {join_code_2}. It should persist!"
