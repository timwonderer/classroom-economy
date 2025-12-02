"""
Tests for legacy unclaimed student deletion.

These tests ensure that teachers can delete legacy student records that don't have
a username_hash set, similar to how they can delete TeacherBlock unclaimed seats.
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, Student, StudentTeacher, Transaction, TapEvent
from hash_utils import get_random_salt, hash_hmac


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_legacy_unclaimed_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """Create a legacy unclaimed student (Student record without username_hash)."""
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        username_hash=None,  # Legacy unclaimed student has no username
        last_name_hash_by_part=[],
        dob_sum=2025,
    )
    db.session.add(student)
    db.session.flush()
    
    # Link student to teacher
    link = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    db.session.add(link)
    db.session.commit()
    
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Log in as admin."""
    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def test_delete_single_legacy_unclaimed_student(client):
    """Teachers can delete a single legacy unclaimed student (no username_hash)."""
    teacher, secret = _create_admin("teacher-legacy1")
    legacy_student = _create_legacy_unclaimed_student("Alice", teacher, "A")
    
    student_id = legacy_student.id
    
    _login_admin(client, teacher, secret)
    
    # Delete the legacy unclaimed student
    response = client.post(
        "/admin/legacy-students/delete",
        json={"student_id": student_id},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "Alice A." in data["message"]
    
    # Verify Student is deleted
    assert Student.query.get(student_id) is None


def test_delete_legacy_unclaimed_student_wrong_teacher(client):
    """Teachers cannot delete another teacher's legacy unclaimed students."""
    teacher1, secret1 = _create_admin("teacher-legacy2a")
    teacher2, secret2 = _create_admin("teacher-legacy2b")
    
    # Create legacy unclaimed student for teacher1
    legacy_student = _create_legacy_unclaimed_student("Bob", teacher1, "B")
    student_id = legacy_student.id
    
    # Login as teacher2
    _login_admin(client, teacher2, secret2)
    
    # Try to delete teacher1's legacy student
    response = client.post(
        "/admin/legacy-students/delete",
        json={"student_id": student_id},
        content_type="application/json"
    )
    
    assert response.status_code == 404
    
    # Verify Student still exists
    assert Student.query.get(student_id) is not None


def test_cannot_delete_legacy_student_with_username(client):
    """Cannot delete a Student that has already set up a username."""
    teacher, secret = _create_admin("teacher-legacy3")
    
    # Create a student WITH username_hash (already claimed)
    salt = get_random_salt()
    credential = "C2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    username_hash = hash_hmac(b"claimed_username", salt)
    
    claimed_student = Student(
        first_name="Charlie",
        last_initial="C",
        block="C",
        salt=salt,
        first_half_hash=first_half_hash,
        username_hash=username_hash,  # Has username - claimed
        last_name_hash_by_part=[],
        dob_sum=2025,
    )
    db.session.add(claimed_student)
    db.session.flush()
    
    link = StudentTeacher(student_id=claimed_student.id, admin_id=teacher.id)
    db.session.add(link)
    db.session.commit()
    
    student_id = claimed_student.id
    
    _login_admin(client, teacher, secret)
    
    # Try to delete the claimed student via legacy route
    response = client.post(
        "/admin/legacy-students/delete",
        json={"student_id": student_id},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "already set up a username" in data["message"]
    
    # Verify Student still exists
    assert Student.query.get(student_id) is not None


def test_delete_legacy_student_with_associated_data(client):
    """Deleting a legacy student also deletes all associated records."""
    teacher, secret = _create_admin("teacher-legacy4")
    legacy_student = _create_legacy_unclaimed_student("David", teacher, "D")
    
    student_id = legacy_student.id
    
    # Add some associated data
    transaction = Transaction(
        student_id=student_id,
        amount=100,
        type='deposit',
        description='Test transaction'
    )
    db.session.add(transaction)
    
    tap_event = TapEvent(
        student_id=student_id,
        period='D',
        status='active',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(tap_event)
    db.session.commit()
    
    _login_admin(client, teacher, secret)
    
    # Delete the legacy unclaimed student
    response = client.post(
        "/admin/legacy-students/delete",
        json={"student_id": student_id},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    
    # Verify Student is deleted
    assert Student.query.get(student_id) is None
    
    # Verify associated data is deleted
    assert Transaction.query.filter_by(student_id=student_id).count() == 0
    assert TapEvent.query.filter_by(student_id=student_id).count() == 0


def test_delete_legacy_student_no_id_provided(client):
    """Attempting to delete without providing an ID returns an error."""
    teacher, secret = _create_admin("teacher-legacy5")
    _login_admin(client, teacher, secret)
    
    response = client.post(
        "/admin/legacy-students/delete",
        json={},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "No student ID" in data["message"]


def test_bulk_delete_includes_legacy_students(client):
    """Bulk delete by block should delete both TeacherBlock seats and legacy students."""
    from app.models import TeacherBlock
    
    teacher, secret = _create_admin("teacher-legacy6")
    
    # Create legacy unclaimed students in block E
    legacy1 = _create_legacy_unclaimed_student("Eve", teacher, "E")
    legacy2 = _create_legacy_unclaimed_student("Frank", teacher, "E")
    
    # Create a TeacherBlock unclaimed seat in same block
    salt = get_random_salt()
    credential = "G2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block="E",
        first_name="Grace",
        last_initial="G",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=f"TEST{teacher.id}E",
        is_claimed=False,
        student_id=None,
    )
    db.session.add(teacher_block)
    db.session.commit()
    
    legacy1_id = legacy1.id
    legacy2_id = legacy2.id
    tb_id = teacher_block.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete all unclaimed in block E
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"block": "E"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 3  # 2 legacy + 1 TeacherBlock
    
    # Verify all are deleted
    assert Student.query.get(legacy1_id) is None
    assert Student.query.get(legacy2_id) is None
    assert TeacherBlock.query.get(tb_id) is None


def test_bulk_delete_does_not_delete_claimed_legacy_students(client):
    """Bulk delete should only delete legacy students without username_hash."""
    teacher, secret = _create_admin("teacher-legacy7")
    
    # Create unclaimed legacy student in block F
    unclaimed = _create_legacy_unclaimed_student("Henry", teacher, "F")
    
    # Create claimed legacy student in same block (has username_hash)
    salt = get_random_salt()
    credential = "I2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    username_hash = hash_hmac(b"ivy_username", salt)
    
    claimed = Student(
        first_name="Ivy",
        last_initial="I",
        block="F",
        salt=salt,
        first_half_hash=first_half_hash,
        username_hash=username_hash,
        last_name_hash_by_part=[],
        dob_sum=2025,
    )
    db.session.add(claimed)
    db.session.flush()
    
    link = StudentTeacher(student_id=claimed.id, admin_id=teacher.id)
    db.session.add(link)
    db.session.commit()
    
    unclaimed_id = unclaimed.id
    claimed_id = claimed.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete all unclaimed in block F
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"block": "F"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 1  # Only unclaimed one
    
    # Verify unclaimed is deleted
    assert Student.query.get(unclaimed_id) is None
    
    # Verify claimed still exists
    assert Student.query.get(claimed_id) is not None
