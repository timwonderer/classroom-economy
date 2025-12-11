"""
Tests for pending student (unclaimed TeacherBlock) deletion.

These tests ensure that teachers can delete pending roster entries
that have not yet been claimed by students.
"""

import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, TeacherBlock
from hash_utils import get_random_salt, hash_hmac


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


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
        student_id=None,  # Explicitly None for unclaimed
    )
    db.session.add(teacher_block)
    db.session.commit()
    
    return teacher_block


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


def test_delete_single_pending_student(client):
    """Teachers can delete a single unclaimed roster entry."""
    teacher, secret = _create_admin("teacher-pending1")
    pending_student = _create_unclaimed_teacher_block("Charlie", teacher, "B")
    
    tb_id = pending_student.id
    
    _login_admin(client, teacher, secret)
    
    # Delete the pending student
    response = client.post(
        "/admin/pending-students/delete",
        json={"teacher_block_id": tb_id},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "Charlie C." in data["message"]
    
    # Verify TeacherBlock is deleted
    assert TeacherBlock.query.get(tb_id) is None


def test_delete_pending_student_wrong_teacher(client):
    """Teachers cannot delete another teacher's pending students."""
    teacher1, secret1 = _create_admin("teacher-pending2a")
    teacher2, secret2 = _create_admin("teacher-pending2b")
    
    # Create pending student for teacher1
    pending_student = _create_unclaimed_teacher_block("David", teacher1, "C")
    tb_id = pending_student.id
    
    # Login as teacher2
    _login_admin(client, teacher2, secret2)
    
    # Try to delete teacher1's pending student
    response = client.post(
        "/admin/pending-students/delete",
        json={"teacher_block_id": tb_id},
        content_type="application/json"
    )
    
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert "not found or access denied" in data["message"]
    
    # Verify TeacherBlock still exists
    assert TeacherBlock.query.get(tb_id) is not None


def test_delete_pending_student_already_claimed(client):
    """Cannot delete a TeacherBlock that has already been claimed."""
    from app.models import Student
    from hash_utils import hash_username

    teacher, secret = _create_admin("teacher-pending3")

    # Create a student first to satisfy foreign key constraint
    student_salt = get_random_salt()
    student = Student(
        first_name="Eve",
        last_initial="E",
        block="D",
        salt=student_salt,
        username_hash=hash_username("eve", student_salt),
        pin_hash="fake-hash",
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.flush()  # Get the student ID

    # Create a claimed TeacherBlock (simulate a student having claimed it)
    salt = get_random_salt()
    credential = "E2025"
    first_half_hash = hash_hmac(credential.encode(), salt)

    claimed_tb = TeacherBlock(
        teacher_id=teacher.id,
        block="D",
        first_name="Eve",
        last_initial="E",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=f"TEST{teacher.id}D",
        is_claimed=True,  # Claimed
        student_id=student.id,  # Use actual student ID
    )
    db.session.add(claimed_tb)
    db.session.commit()
    
    tb_id = claimed_tb.id
    
    _login_admin(client, teacher, secret)
    
    # Try to delete the claimed seat
    response = client.post(
        "/admin/pending-students/delete",
        json={"teacher_block_id": tb_id},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "already been claimed" in data["message"]
    
    # Verify TeacherBlock still exists
    assert TeacherBlock.query.get(tb_id) is not None


def test_bulk_delete_pending_students_by_ids(client):
    """Teachers can bulk delete multiple unclaimed roster entries by IDs."""
    teacher, secret = _create_admin("teacher-pending4")
    
    # Create multiple pending students
    pending1 = _create_unclaimed_teacher_block("Frank", teacher, "E")
    pending2 = _create_unclaimed_teacher_block("Grace", teacher, "E")
    pending3 = _create_unclaimed_teacher_block("Hank", teacher, "E")
    
    tb_ids = [pending1.id, pending2.id, pending3.id]
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete pending students
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"teacher_block_ids": tb_ids},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 3
    
    # Verify all TeacherBlocks are deleted
    for tb_id in tb_ids:
        assert TeacherBlock.query.get(tb_id) is None


def test_bulk_delete_pending_students_by_block(client):
    """Teachers can delete all unclaimed roster entries in a block."""
    teacher, secret = _create_admin("teacher-pending5")
    
    # Create multiple pending students in block F
    pending1 = _create_unclaimed_teacher_block("Ivy", teacher, "F")
    pending2 = _create_unclaimed_teacher_block("Jack", teacher, "F")
    pending3 = _create_unclaimed_teacher_block("Kate", teacher, "F")
    
    # Create one in a different block
    pending_other = _create_unclaimed_teacher_block("Liam", teacher, "G")
    
    # Store IDs before deletion
    pending1_id = pending1.id
    pending2_id = pending2.id
    pending3_id = pending3.id
    pending_other_id = pending_other.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete all pending students in block F
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"block": "F"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 3
    assert "Block F" in data["message"]
    
    # Verify block F TeacherBlocks are deleted
    assert TeacherBlock.query.get(pending1_id) is None
    assert TeacherBlock.query.get(pending2_id) is None
    assert TeacherBlock.query.get(pending3_id) is None
    
    # Verify block G TeacherBlock still exists
    assert TeacherBlock.query.get(pending_other_id) is not None


def test_bulk_delete_skips_claimed_students(client):
    """Bulk delete by IDs should skip any claimed TeacherBlocks."""
    from app.models import Student
    from hash_utils import hash_username

    teacher, secret = _create_admin("teacher-pending6")

    # Create unclaimed pending student
    pending1 = _create_unclaimed_teacher_block("Mia", teacher, "H")

    # Create a student first to satisfy foreign key constraint
    student_salt = get_random_salt()
    student = Student(
        first_name="Nate",
        last_initial="N",
        block="H",
        salt=student_salt,
        username_hash=hash_username("nate", student_salt),
        pin_hash="fake-hash",
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.flush()

    # Create a claimed TeacherBlock
    salt = get_random_salt()
    credential = "N2025"
    first_half_hash = hash_hmac(credential.encode(), salt)

    claimed_tb = TeacherBlock(
        teacher_id=teacher.id,
        block="H",
        first_name="Nate",
        last_initial="N",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=f"TEST{teacher.id}H",
        is_claimed=True,
        student_id=student.id,
    )
    db.session.add(claimed_tb)
    db.session.commit()
    
    tb_ids = [pending1.id, claimed_tb.id]
    
    _login_admin(client, teacher, secret)
    
    # Try to bulk delete both
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"teacher_block_ids": tb_ids},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 1  # Only the unclaimed one
    
    # Verify unclaimed is deleted, claimed still exists
    assert TeacherBlock.query.get(pending1.id) is None
    assert TeacherBlock.query.get(claimed_tb.id) is not None


def test_bulk_delete_by_block_only_deletes_unclaimed(client):
    """Bulk delete by block should only delete unclaimed TeacherBlocks."""
    from app.models import Student
    from hash_utils import hash_username

    teacher, secret = _create_admin("teacher-pending7")

    # Create unclaimed pending students in block I
    pending1 = _create_unclaimed_teacher_block("Olivia", teacher, "I")
    pending2 = _create_unclaimed_teacher_block("Paul", teacher, "I")

    # Create a student first to satisfy foreign key constraint
    student_salt = get_random_salt()
    student = Student(
        first_name="Quinn",
        last_initial="Q",
        block="I",
        salt=student_salt,
        username_hash=hash_username("quinn", student_salt),
        pin_hash="fake-hash",
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.flush()

    # Create a claimed TeacherBlock in same block
    salt = get_random_salt()
    credential = "Q2025"
    first_half_hash = hash_hmac(credential.encode(), salt)

    claimed_tb = TeacherBlock(
        teacher_id=teacher.id,
        block="I",
        first_name="Quinn",
        last_initial="Q",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=f"TEST{teacher.id}I",
        is_claimed=True,
        student_id=student.id,
    )
    db.session.add(claimed_tb)
    db.session.commit()
    
    # Store IDs before deletion
    pending1_id = pending1.id
    pending2_id = pending2.id
    claimed_tb_id = claimed_tb.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete all pending students in block I
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={"block": "I"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["deleted_count"] == 2  # Only unclaimed ones
    
    # Verify unclaimed are deleted
    assert TeacherBlock.query.get(pending1_id) is None
    assert TeacherBlock.query.get(pending2_id) is None
    
    # Verify claimed still exists
    assert TeacherBlock.query.get(claimed_tb_id) is not None


def test_delete_pending_student_no_id_provided(client):
    """Attempting to delete without providing an ID returns an error."""
    teacher, secret = _create_admin("teacher-pending8")
    _login_admin(client, teacher, secret)
    
    response = client.post(
        "/admin/pending-students/delete",
        json={},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "No teacher block ID" in data["message"]


def test_bulk_delete_pending_students_no_params(client):
    """Bulk delete without IDs or block returns an error."""
    teacher, secret = _create_admin("teacher-pending9")
    _login_admin(client, teacher, secret)
    
    response = client.post(
        "/admin/pending-students/bulk-delete",
        json={},
        content_type="application/json"
    )
    
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "teacher_block_ids or block must be provided" in data["message"]
