"""
Test that legacy placeholder TeacherBlock entries don't show up in unclaimed seats badge.

This test verifies the fix for the issue where legacy classes showed incorrect
"unclaimed seats" counts in the badge because placeholder TeacherBlock entries
(used only to store join codes) were being counted as unclaimed seats.
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


def test_legacy_placeholder_not_counted_as_unclaimed_seat(client):
    """
    Test that legacy placeholder TeacherBlock entries don't appear in unclaimed seats badge.
    
    When a legacy class (students exist but no TeacherBlock) is viewed, the system
    creates a placeholder TeacherBlock with first_name="__JOIN_CODE_PLACEHOLDER__"
    to store the join code. This placeholder should NOT be counted as an unclaimed seat
    because it's not a real student account waiting to be claimed.
    """
    teacher, secret = _create_admin("teacher-legacy-class")
    
    # Create a legacy student (no TeacherBlock entry)
    _create_legacy_student("LegacyStudent", teacher, block="A")
    
    # Verify no TeacherBlock entry exists initially
    assert TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").count() == 0
    
    _login_admin(client, teacher, secret)
    
    # Load the page - this will create the placeholder TeacherBlock
    response = client.get("/admin/students")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # Verify that:
    # 1. A TeacherBlock was created (for the join code)
    teacher_blocks = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="A").all()
    assert len(teacher_blocks) == 1, "Should have exactly one TeacherBlock (the placeholder)"
    
    placeholder = teacher_blocks[0]
    assert placeholder.first_name == "__JOIN_CODE_PLACEHOLDER__", "Should be a placeholder"
    assert not placeholder.is_claimed, "Placeholder should be unclaimed"
    
    # 2. The badge should NOT show "unclaimed" (placeholder should be excluded)
    # The badge appears like: <span class="badge bg-warning text-dark ms-1">1 unclaimed</span>
    assert '1 unclaimed</span>' not in html, \
        "Legacy placeholder should not appear in unclaimed seats badge"
    
    # 3. The "All seats claimed" badge should be shown instead
    assert 'All seats claimed' in html, \
        "Should show 'All seats claimed' when only placeholder exists"
    
    # 4. The unclaimed seats section should NOT appear
    assert 'Unclaimed Seats (' not in html, \
        "Should not show unclaimed seats section when only placeholder exists"


def test_real_unclaimed_seats_still_counted(client):
    """
    Test that real unclaimed seats (from roster upload) are still counted correctly.
    
    This ensures our fix doesn't break the normal case where teachers upload rosters
    and those TeacherBlock entries should appear as unclaimed seats.
    """
    from hash_utils import hash_hmac
    
    teacher, secret = _create_admin("teacher-with-roster")
    
    # Create a real unclaimed seat (from roster upload)
    salt = get_random_salt()
    real_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="RealStudent",  # NOT the placeholder name
        last_initial="R",
        last_name_hash_by_part=["hash1"],
        dob_sum=2025,
        salt=salt,
        first_half_hash=hash_hmac("R2025".encode(), salt),
        join_code="ABC123",
        is_claimed=False,
    )
    db.session.add(real_seat)
    db.session.commit()
    
    _login_admin(client, teacher, secret)
    
    # Load the page
    response = client.get("/admin/students")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # The badge SHOULD show "1 unclaimed" for the real seat
    assert '1 unclaimed</span>' in html, \
        "Real unclaimed seat should appear in badge"
    
    # The unclaimed seats section SHOULD appear
    assert 'Unclaimed Seats (1)' in html, \
        "Should show unclaimed seats section for real seat"
    
    # Should show the real student's name
    assert 'RealStudent R.' in html, \
        "Should display the real unclaimed student's name"


def test_mixed_legacy_and_unclaimed_seats(client):
    """
    Test correct counting when both legacy placeholder and real unclaimed seats exist.
    
    This tests the edge case where a teacher has:
    - Legacy students (creates placeholder)
    - Real unclaimed seats from roster upload
    
    Only the real unclaimed seats should be counted.
    """
    from hash_utils import hash_hmac
    
    teacher, secret = _create_admin("teacher-mixed-class")
    
    # Create a legacy student in block A
    _create_legacy_student("LegacyStudent", teacher, block="A")
    
    # Create a real unclaimed seat in block A (from roster upload)
    salt = get_random_salt()
    real_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="NewStudent",
        last_initial="N",
        last_name_hash_by_part=["hash1"],
        dob_sum=2026,
        salt=salt,
        first_half_hash=hash_hmac("N2026".encode(), salt),
        join_code="DEF456",
        is_claimed=False,
    )
    db.session.add(real_seat)
    db.session.commit()
    
    _login_admin(client, teacher, secret)
    
    # Load the page
    response = client.get("/admin/students")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    
    # After loading, we should have:
    # - 1 legacy student (claimed, via StudentTeacher link)
    # - 1 placeholder TeacherBlock (unclaimed, for join code storage)
    # - 1 real unclaimed seat
    
    # The badge should show "1 unclaimed" (only the real seat, not the placeholder)
    assert '1 unclaimed</span>' in html, \
        "Badge should show only the real unclaimed seat, not the placeholder"
    
    # Should NOT show "2 unclaimed"
    assert '2 unclaimed</span>' not in html, \
        "Should not count placeholder as unclaimed seat"
    
    # The unclaimed seats section should show only the real student
    assert 'Unclaimed Seats (1)' in html, \
        "Should show 1 unclaimed seat (the real one)"
    
    assert 'NewStudent N.' in html, \
        "Should show the real unclaimed student"
    
    assert '__JOIN_CODE_PLACEHOLDER__' not in html, \
        "Should not display placeholder in unclaimed seats section"
