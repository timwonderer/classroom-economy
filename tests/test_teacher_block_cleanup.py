import pytest
pytest.skip('Legacy TeacherBlock test', allow_module_level=True)
"""
Tests for TeacherBlock cleanup during student/period/teacher deletion.

These tests ensure that TeacherBlock entries are properly cleaned up
when students, periods, or teachers are deleted.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin, Student, StudentTeacher, SystemAdmin
from app.hash_utils import get_random_salt, hash_hmac
from tests.helpers.class_scope import create_class_scope

pytestmark = pytest.mark.skip(reason="TeacherBlock removed in Wave 11 decommissioning")


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_sysadmin() -> tuple[SystemAdmin, str]:
    """Create a system admin with TOTP authentication."""
    secret = pyotp.random_base32()
    sysadmin = make_sysadmin("sysadmin", secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def _create_student_with_teacher_block(first_name: str, teacher: Admin, block: str = "A") -> tuple[Student, TeacherBlock]:
    """Create a student with an associated TeacherBlock entry."""
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)
    
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
    )
    db.session.add(student)
    db.session.flush()
    
    # Create StudentTeacher link
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    
    join_code = f"TEST{teacher.id}{block}"
    if not TeacherBlock.query.filter_by(join_code=join_code).first():
        create_class_scope(
            teacher=teacher,
            join_code=join_code,
            student=student,
            block=block,
            display_name=f'Test Class {teacher.id}{block}',
            create_teacher_membership=False,
            create_student_membership=False,
        )
        db.session.flush()
    
    # Create TeacherBlock entry
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=first_name[0].upper(),
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=join_code,
        is_claimed=False,
        student_id=student.id,
    )
    db.session.add(teacher_block)
    db.session.commit()
    
    return student, teacher_block


def _login_admin(client, admin: Admin, secret: str, username: str = "teacher"):
    """Log in as admin."""
    response = client.post(
        "/admin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str, username: str = "sysadmin"):
    """Log in as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_delete_student_removes_student_and_unclaims_teacher_block(client):
    """Deleting a student should remove the student and keep roster seat as unclaimed."""
    teacher, secret = _create_admin("teacher-cleanup")
    student, teacher_block = _create_student_with_teacher_block("Alice", teacher)
    
    student_id = student.id
    teacher_block_id = teacher_block.id
    
    _login_admin(client, teacher, secret)
    
    # Delete the student
    response = client.post(
        "/admin/student/delete",
        data={"student_id": student_id, "confirmation": "DELETE"},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    # Verify student is deleted
    assert db.session.get(Student, student_id) is None

    # Verify TeacherBlock seat is preserved but unclaimed
    refreshed_tb = db.session.get(TeacherBlock, teacher_block_id)
    assert refreshed_tb is not None
    assert refreshed_tb.student_id is None
    assert refreshed_tb.is_claimed is False


def test_bulk_delete_students_removes_students_and_unclaims_teacher_blocks(client):
    """Bulk delete should remove students and keep TeacherBlock seats unclaimed."""
    teacher, secret = _create_admin("teacher-bulk")
    student1, tb1 = _create_student_with_teacher_block("Alice", teacher)
    student2, tb2 = _create_student_with_teacher_block("Bob", teacher)
    
    student1_id = student1.id
    student2_id = student2.id
    tb1_id = tb1.id
    tb2_id = tb2.id
    
    _login_admin(client, teacher, secret)
    
    # Bulk delete students
    response = client.post(
        "/admin/students/bulk-delete",
        json={
            "student_ids": [student1_id, student2_id],
            "gate_phrase": "DELETE STUDENTS",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify students are deleted
    assert db.session.get(Student, student1_id) is None
    assert db.session.get(Student, student2_id) is None

    # Verify TeacherBlocks are preserved but unclaimed
    refreshed_tb1 = db.session.get(TeacherBlock, tb1_id)
    refreshed_tb2 = db.session.get(TeacherBlock, tb2_id)
    assert refreshed_tb1 is not None
    assert refreshed_tb2 is not None
    assert refreshed_tb1.student_id is None and refreshed_tb1.is_claimed is False
    assert refreshed_tb2.student_id is None and refreshed_tb2.is_claimed is False


def test_delete_block_removes_teacher_blocks(client):
    """When a block is deleted, all TeacherBlock entries for that block should be removed."""
    teacher, secret = _create_admin("teacher-block-del")
    _create_student_with_teacher_block("Alice", teacher, block="X")
    _create_student_with_teacher_block("Bob", teacher, block="X")
    
    # Use existing join code that was created by _create_student_with_teacher_block
    join_code = f"TEST{teacher.id}X"
    
    # Create an unclaimed TeacherBlock in the same block using same join_code
    unclaimed_tb = TeacherBlock(
        teacher_id=teacher.id,
        block="X",
        first_name="Unclaimed",
        last_initial="U",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=get_random_salt(),
        first_half_hash="test_hash",
        join_code=join_code,
        is_claimed=False,
    )
    db.session.add(unclaimed_tb)
    db.session.commit()
    # 1. Login as teacher
    _login_admin(client, teacher, secret, username="teacher-block-del")
    
    # Delete the block
    response = client.post(
        "/admin/students/delete-block",
        json={
            "block": "X",
            "gate_phrase": "DELETE BLOCK X",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify all TeacherBlocks for block X are deleted (including unclaimed)
    remaining_tbs = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="X").all()
    assert len(remaining_tbs) == 0


def test_sysadmin_delete_period_is_disabled(client):
    """System admins cannot delete class periods."""
    teacher, _ = _create_admin("teacher-period")
    sysadmin, sys_secret = _create_sysadmin()
    
    # Make teacher inactive so sysadmin can delete without request
    teacher.last_login = None
    db.session.commit()
    
    student, tb = _create_student_with_teacher_block("Alice", teacher, block="Y")
    tb_id = tb.id
    
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Attempt period deletion (should be blocked)
    response = client.post(
        f"/sysadmin/delete-period/{teacher.id}/Y",
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert b"System admins cannot delete classes" in response.data
    assert db.session.get(TeacherBlock, tb_id) is not None


def test_teacher_account_deletion_removes_teacher_blocks(client):
    """Teacher self-deletion removes all owned TeacherBlock entries."""
    teacher, _ = _create_admin("teacher-to-delete")

    teacher_id = teacher.id
    
    student1, tb1 = _create_student_with_teacher_block("Alice", teacher, block="A")
    student2, tb2 = _create_student_with_teacher_block("Bob", teacher, block="B")
    tb1_id = tb1.id
    tb2_id = tb2.id
    
    from app.routes.admin import _hard_delete_teacher_account_scope
    _hard_delete_teacher_account_scope(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    
    # Verify TeacherBlocks are deleted
    assert db.session.get(TeacherBlock, tb1_id) is None
    assert db.session.get(TeacherBlock, tb2_id) is None
    assert db.session.get(Admin, teacher_id) is None
