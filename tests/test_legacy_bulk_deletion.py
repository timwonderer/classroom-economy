"""
Tests for bulk deletion of legacy unclaimed students.

These tests ensure that:
1. Legacy unclaimed students can be bulk deleted by block
2. The "Delete All Unclaimed" button works for both TeacherBlock seats and legacy students
3. Block deletion with improved transaction handling works correctly
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction
from hash_utils import get_random_salt, hash_hmac


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_legacy_unclaimed_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """
    Create a legacy unclaimed student - a Student record without a username_hash.
    These are students that were added to the roster but never completed setup.
    """
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        dob_sum=2025,
        username_hash=None,  # Legacy - no username yet
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()
    
    # Create StudentTeacher association
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    
    return student


def _create_unclaimed_teacher_block(first_name: str, teacher: Admin, block: str = "A") -> TeacherBlock:
    """Create an unclaimed TeacherBlock entry (pending student)."""
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=first_name[0].upper(),
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=f"TEST{teacher.id}{block}",
        is_claimed=False,
        student_id=None,
    )
    db.session.add(teacher_block)
    db.session.commit()
    
    return teacher_block


def _create_claimed_student(first_name: str, username: str, teacher: Admin, block: str = "A") -> Student:
    """Create a fully claimed student with a username."""
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    username_hash = hash_hmac(username.encode(), salt)
    
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        dob_sum=2025,
        username_hash=username_hash,
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()
    
    # Create StudentTeacher association
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
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


def test_bulk_delete_legacy_unclaimed_students_by_block(client):
    """Teachers can bulk delete legacy unclaimed students in a block."""
    teacher, secret = _create_admin("teacher-legacy-bulk1")
    
    # Create multiple legacy unclaimed students in block A
    student1 = _create_legacy_unclaimed_student("Alice", teacher, "A")
    student2 = _create_legacy_unclaimed_student("Bob", teacher, "A")
    student3 = _create_legacy_unclaimed_student("Charlie", teacher, "A")
    
    # Create one in a different block to ensure it's not affected
    other_student = _create_legacy_unclaimed_student("Dave", teacher, "B")
    
    student_ids = [student1.id, student2.id, student3.id]
    other_student_id = other_student.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete legacy unclaimed students in block A
    response = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={"block": "A"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 3
    assert "Block A" in data["message"]
    
    # Verify block A students are deleted
    for student_id in student_ids:
        assert Student.query.get(student_id) is None
        assert StudentTeacher.query.filter_by(student_id=student_id).first() is None
    
    # Verify block B student is NOT deleted
    assert Student.query.get(other_student_id) is not None


def test_bulk_delete_legacy_unclaimed_students_skips_claimed(client):
    """Bulk delete legacy unclaimed should only delete students without usernames."""
    teacher, secret = _create_admin("teacher-legacy-bulk2")
    
    # Create legacy unclaimed students
    unclaimed1 = _create_legacy_unclaimed_student("Eve", teacher, "C")
    unclaimed2 = _create_legacy_unclaimed_student("Frank", teacher, "C")
    
    # Create a claimed student in the same block
    claimed = _create_claimed_student("Grace", "grace_username", teacher, "C")
    
    unclaimed_ids = [unclaimed1.id, unclaimed2.id]
    claimed_id = claimed.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete legacy unclaimed students in block C
    response = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={"block": "C"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 2  # Only the unclaimed ones
    
    # Verify unclaimed students are deleted
    for student_id in unclaimed_ids:
        assert Student.query.get(student_id) is None
    
    # Verify claimed student is NOT deleted
    assert Student.query.get(claimed_id) is not None


def test_bulk_delete_legacy_unclaimed_students_wrong_teacher(client):
    """Teachers cannot delete another teacher's legacy unclaimed students."""
    teacher1, secret1 = _create_admin("teacher-legacy-bulk3a")
    teacher2, secret2 = _create_admin("teacher-legacy-bulk3b")
    
    # Create legacy unclaimed student for teacher1
    student = _create_legacy_unclaimed_student("Henry", teacher1, "D")
    student_id = student.id
    
    # Login as teacher2
    _login_admin(client, teacher2, secret2)
    
    # Try to delete teacher1's legacy unclaimed students
    response = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={"block": "D"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 0  # Should not delete any
    
    # Verify student still exists
    assert Student.query.get(student_id) is not None


def test_bulk_delete_mixed_unclaimed_types(client):
    """Test deleting both TeacherBlock seats and legacy unclaimed students together."""
    teacher, secret = _create_admin("teacher-mixed-bulk1")
    
    # Create unclaimed TeacherBlock entries
    tb1 = _create_unclaimed_teacher_block("Ivy", teacher, "E")
    tb2 = _create_unclaimed_teacher_block("Jack", teacher, "E")
    
    # Create legacy unclaimed students
    student1 = _create_legacy_unclaimed_student("Kate", teacher, "E")
    student2 = _create_legacy_unclaimed_student("Liam", teacher, "E")
    
    tb_ids = [tb1.id, tb2.id]
    student_ids = [student1.id, student2.id]
    
    _login_admin(client, teacher, secret)
    
    # Delete all pending TeacherBlock entries
    response1 = client.post(
        "/admin/pending-students/bulk-delete",
        json={"block": "E"},
        content_type="application/json"
    )
    
    assert response1.status_code == 200
    data1 = response1.get_json()
    assert data1["status"] == "success"
    assert data1["deleted_count"] == 2
    
    # Delete all legacy unclaimed students
    response2 = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={"block": "E"},
        content_type="application/json"
    )
    
    assert response2.status_code == 200
    data2 = response2.get_json()
    assert data2["status"] == "success"
    assert data2["deleted_count"] == 2
    
    # Verify all are deleted
    for tb_id in tb_ids:
        assert TeacherBlock.query.get(tb_id) is None
    for student_id in student_ids:
        assert Student.query.get(student_id) is None


def test_block_deletion_with_improved_transactions(client):
    """Test that block deletion with improved transaction handling works correctly."""
    teacher, secret = _create_admin("teacher-block-improved1")
    
    # Create students in block F
    student1 = _create_claimed_student("Mia", "mia_username", teacher, "F")
    student2 = _create_claimed_student("Noah", "noah_username", teacher, "F")
    student3 = _create_legacy_unclaimed_student("Olivia", teacher, "F")
    
    # Add some transactions to ensure they're cleaned up
    db.session.add(Transaction(
        student_id=student1.id,
        teacher_id=teacher.id,
        amount=100,
        description="Test transaction",
        account_type="checking"
    ))
    db.session.commit()
    
    student_ids = [student1.id, student2.id, student3.id]
    
    _login_admin(client, teacher, secret)
    
    # Delete block F
    response = client.post(
        "/admin/students/delete-block",
        json={"block": "F"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "3" in data["message"]
    
    # Verify all students are deleted
    for student_id in student_ids:
        assert Student.query.get(student_id) is None
        assert StudentTeacher.query.filter_by(student_id=student_id).first() is None
    
    # Verify transactions are deleted
    assert Transaction.query.filter_by(student_id=student1.id).first() is None


def test_bulk_delete_legacy_unclaimed_no_block_provided(client):
    """Attempting to bulk delete without providing a block returns an error."""
    teacher, secret = _create_admin("teacher-legacy-bulk-error1")
    _login_admin(client, teacher, secret)
    
    response = client.post(
        "/admin/legacy-unclaimed-students/bulk-delete",
        json={},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "Block must be provided" in data["message"]
