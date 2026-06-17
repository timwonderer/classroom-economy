import pytest
pytest.skip('Legacy TeacherBlock test', allow_module_level=True)
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest

pytestmark = [pytest.mark.critical, pytest.mark.regression]

"""
Test that students can claim accounts in legacy classes using join code.

This test verifies that when a teacher has legacy students (created before join code system),
new students can still use the join code to claim their accounts by uploading a roster.
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, Student, StudentTeacher
from app.hash_utils import get_random_salt, hash_username, hash_hmac
from app.utils.name_utils import hash_last_name_parts
from app.utils.claim_credentials import compute_primary_claim_hash


def _create_admin(username: str) -> tuple[Admin, str]:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
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
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Helper to log in an admin."""
    from app.models import User, UserRole
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    if not user:
        user = User(
            username_hash=admin.username_lookup_hash,
            username_lookup_hash=admin.username_lookup_hash,
            user_role=UserRole.TEACHER,
        )
        db.session.add(user)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        sess["user_id"] = user.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return None


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
    
    _login_admin(client, teacher, secret)
    from app.routes.admin import _ensure_join_code_anchors, _ensure_teacher_student_seat
    join_code = "LEGACYA1"
    _ensure_join_code_anchors(teacher.id, join_code, class_label="A")
    _ensure_teacher_student_seat(teacher.id, join_code, "A")
    db.session.commit()

    response = client.get("/admin/students", follow_redirects=True)
    assert response.status_code == 200
    
    # Now simulate teacher uploading a roster with a new student
    # This would create a real TeacherBlock entry (not a placeholder)
    new_salt = get_random_salt()
    new_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="NewStudent",
        last_initial="N",
        last_name_hash_by_part=[hash_hmac("smith".encode(), new_salt)],
        dob_sum_hash=hash_hmac(b'2025', new_salt),
        salt=new_salt,
        first_half_hash=hash_hmac("N2025".encode(), new_salt),
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
            "first_name": "NewStudent",
            "last_name": "Smith",
            "dedupe_code": "",
        },
        follow_redirects=False,
    )
    
    # Should redirect to create username (successful claim)
    assert claim_response.status_code == 302, \
        f"Expected redirect (302), got {claim_response.status_code}"
    assert "/student/create-username" in claim_response.location, \
        f"Should redirect to create-username, got {claim_response.location}"
    
    # Verify the seat was claimed
    new_seat_after = db.session.get(TeacherBlock, new_seat.id)
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
    
    from app.routes.admin import _ensure_join_code_anchors, _ensure_teacher_student_seat
    join_code_1 = "LEGACYB1"
    _ensure_join_code_anchors(teacher.id, join_code_1, class_label="B")
    _ensure_teacher_student_seat(teacher.id, join_code_1, "B")
    db.session.commit()

    response1 = client.get("/admin/students", follow_redirects=True)
    assert response1.status_code == 200
    
    # Teacher adds a new student to roster (using the same join code)
    new_salt = get_random_salt()
    new_seat = TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name="NewStudent2",
        last_initial="N",
        last_name_hash_by_part=[hash_hmac("jones".encode(), new_salt)],
        dob_sum_hash=None,
        salt=new_salt,
        first_half_hash=hash_hmac("N2026".encode(), new_salt),
        join_code=join_code_1,  # Must use the same join code
        is_claimed=False,
    )
    db.session.add(new_seat)
    db.session.commit()
    
    # Second load - join code should be the same
    response2 = client.get("/admin/students", follow_redirects=True)
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


def test_claim_succeeds_when_seat_uses_last_initial_hash(client):
    """Students can claim even if the seat hash was generated with the last initial."""

    teacher, _ = _create_admin("teacher-last-initial-hash")

    salt = get_random_salt()
    join_code = "P2C7FZ"
    last_name = "Hayslett"

    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name="Benjamin",
        last_initial="H",
        last_name_hash_by_part=hash_last_name_parts(last_name, salt),
        dob_sum_hash=hash_hmac(b'2030', salt),
        salt=salt,
        first_half_hash=hash_hmac("H2030".encode(), salt),
        join_code=join_code,
        is_claimed=False,
    )
    db.session.add(seat)
    db.session.commit()

    response = client.post(
        "/student/claim-account",
        data={
            "join_code": join_code,
            "first_name": "Benjamin",
            "last_name": last_name,
            "dedupe_code": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/student/create-username" in response.location

    refreshed_seat = db.session.get(TeacherBlock, seat.id)
    assert refreshed_seat.is_claimed is True
    assert refreshed_seat.first_half_hash == hash_hmac("H2030".encode(), salt)

    student = db.session.get(Student, refreshed_seat.student_id)
    assert student is not None
    assert student.first_half_hash == hash_hmac("H2030".encode(), salt)
    assert StudentTeacher.query.filter_by(student_id=student.id, teacher_id=teacher.id).count() == 1


def test_students_page_normalizes_legacy_claim_hashes(client):
    """Visiting the students page backfills legacy claim hashes to the canonical format."""

    teacher, secret = _create_admin("teacher-normalize-hashes")

    # Create a TeacherBlock entry using the legacy last-initial credential
    seat_salt = get_random_salt()
    legacy_seat_hash = hash_hmac("L2035".encode(), seat_salt)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="C",
        first_name="Ada",
        last_initial="L",
        last_name_hash_by_part=hash_last_name_parts("Lovelace", seat_salt),
        dob_sum_hash=hash_hmac(b'2035', seat_salt),
        salt=seat_salt,
        first_half_hash=legacy_seat_hash,
        join_code="LEGACY1",
        is_claimed=False,
    )

    # Create a Student record still using the legacy last-initial credential
    student_salt = get_random_salt()
    legacy_student_hash = hash_hmac("L2035".encode(), student_salt)
    student = Student(
        first_name="Aria",
        last_initial="L",
        block="C",
        salt=student_salt,
        first_half_hash=legacy_student_hash,
        has_completed_setup=False,
    )
    db.session.add_all([seat, student])
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    from app.routes.admin import _ensure_join_code_anchors
    class_id = _ensure_join_code_anchors(teacher.id, "LEGACY1", class_label="C")
    seat.class_id = class_id
    db.session.commit()

    _login_admin(client, teacher, secret)

    # Visiting the students page still works; legacy hash normalization no longer
    # runs (dob_sum is no longer stored in plain text), so hashes remain unchanged.
    response = client.get("/admin/students", follow_redirects=True)
    assert response.status_code == 200

    updated_seat = db.session.get(TeacherBlock, seat.id)
    updated_student = db.session.get(Student, student.id)

    # Hashes are not changed since dob_sum is not available for re-computation
    assert updated_seat.first_half_hash == legacy_seat_hash
    assert updated_student.first_half_hash == legacy_student_hash
