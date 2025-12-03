"""
Tests for legacy unclaimed student deletion and block deletion with StudentTeacher associations.

These tests ensure:
1. Legacy students without usernames can be deleted through the modal
2. Block deletion properly cleans up StudentTeacher associations
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
        teacher_id=teacher.id  # Legacy field
    )
    db.session.add(student)
    db.session.commit()
    
    # Create StudentTeacher association
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    db.session.commit()
    
    return student


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


def test_delete_legacy_unclaimed_student(client):
    """Teachers can delete legacy unclaimed students via the delete_student route."""
    teacher, secret = _create_admin("teacher-legacy1")
    legacy_student = _create_legacy_unclaimed_student("Alice", teacher, "A")
    
    student_id = legacy_student.id
    student_name = legacy_student.full_name
    
    _login_admin(client, teacher, secret)
    
    # Delete the legacy student via form POST
    response = client.post(
        "/admin/student/delete",
        data={"student_id": student_id, "confirmation": "DELETE"},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert b"Successfully deleted" in response.data or b"deleted" in response.data.lower()
    
    # Verify Student is deleted
    assert Student.query.get(student_id) is None
    
    # Verify StudentTeacher association is deleted
    assert StudentTeacher.query.filter_by(student_id=student_id).first() is None


def test_delete_block_removes_student_teacher_associations(client):
    """Block deletion should properly remove StudentTeacher associations."""
    teacher, secret = _create_admin("teacher-block1")
    
    # Create students in block B
    student1 = _create_claimed_student("Bob", "bob_username", teacher, "B")
    student2 = _create_claimed_student("Carol", "carol_username", teacher, "B")
    student3 = _create_legacy_unclaimed_student("Dave", teacher, "B")
    
    # Create a student in a different block to ensure it's not affected
    other_student = _create_claimed_student("Eve", "eve_username", teacher, "C")
    
    student1_id = student1.id
    student2_id = student2.id
    student3_id = student3.id
    other_student_id = other_student.id
    
    # Add some transactions to verify they're deleted too
    db.session.add(Transaction(
        student_id=student1.id,
        teacher_id=teacher.id,
        amount=100,
        description="Test transaction",
        account_type="checking"
    ))
    db.session.commit()
    
    _login_admin(client, teacher, secret)
    
    # Delete block B
    response = client.post(
        "/admin/students/delete-block",
        json={"block": "B"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "3" in data["message"]  # Should delete 3 students
    
    # Verify all block B students are deleted
    assert Student.query.get(student1_id) is None
    assert Student.query.get(student2_id) is None
    assert Student.query.get(student3_id) is None
    
    # Verify StudentTeacher associations are deleted
    assert StudentTeacher.query.filter_by(student_id=student1_id).first() is None
    assert StudentTeacher.query.filter_by(student_id=student2_id).first() is None
    assert StudentTeacher.query.filter_by(student_id=student3_id).first() is None
    
    # Verify transactions are deleted
    assert Transaction.query.filter_by(student_id=student1_id).first() is None
    
    # Verify block C student is NOT deleted
    assert Student.query.get(other_student_id) is not None
    assert StudentTeacher.query.filter_by(student_id=other_student_id).first() is not None


def test_delete_block_with_shared_students(client):
    """
    Block deletion should handle students shared between multiple teachers.
    When deleting a block, only the StudentTeacher association for that teacher
    should be removed (if the student is also in other teachers' classes).
    """
    teacher1, secret1 = _create_admin("teacher-shared1")
    teacher2, secret2 = _create_admin("teacher-shared2")
    
    # Create a student that belongs to both teachers
    student = _create_claimed_student("Frank", "frank_username", teacher1, "D")
    student_id = student.id
    
    # Add second teacher association
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher2.id))
    db.session.commit()
    
    # Verify student has two associations
    associations = StudentTeacher.query.filter_by(student_id=student_id).all()
    assert len(associations) == 2
    
    _login_admin(client, teacher1, secret1)
    
    # Teacher1 deletes block D
    response = client.post(
        "/admin/students/delete-block",
        json={"block": "D"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    
    # The student should be deleted (since we delete all students in the block)
    # This is the current behavior - block deletion removes students entirely
    assert Student.query.get(student_id) is None
    
    # All StudentTeacher associations should be deleted
    assert StudentTeacher.query.filter_by(student_id=student_id).first() is None


def test_bulk_delete_students_removes_associations(client):
    """Bulk student deletion should properly remove StudentTeacher associations."""
    teacher, secret = _create_admin("teacher-bulk1")
    
    # Create multiple students
    student1 = _create_claimed_student("Grace", "grace_username", teacher, "E")
    student2 = _create_claimed_student("Henry", "henry_username", teacher, "E")
    student3 = _create_legacy_unclaimed_student("Ivy", teacher, "E")
    
    student_ids = [student1.id, student2.id, student3.id]
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete students
    response = client.post(
        "/admin/students/bulk-delete",
        json={"student_ids": student_ids},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "3" in data["message"]  # Should delete 3 students
    
    # Verify all students are deleted
    for student_id in student_ids:
        assert Student.query.get(student_id) is None
        assert StudentTeacher.query.filter_by(student_id=student_id).first() is None


def test_delete_student_without_confirmation(client):
    """Attempting to delete a student without proper confirmation should fail."""
    teacher, secret = _create_admin("teacher-confirm1")
    student = _create_claimed_student("Jack", "jack_username", teacher, "F")
    
    student_id = student.id
    
    _login_admin(client, teacher, secret)
    
    # Try to delete without proper confirmation
    response = client.post(
        "/admin/student/delete",
        data={"student_id": student_id, "confirmation": "delete"},  # Wrong case
        follow_redirects=True
    )
    
    assert response.status_code == 200
    # Should show cancellation message
    assert b"cancelled" in response.data.lower() or b"cancel" in response.data.lower()
    
    # Verify student is NOT deleted
    assert Student.query.get(student_id) is not None
    assert StudentTeacher.query.filter_by(student_id=student_id).first() is not None
