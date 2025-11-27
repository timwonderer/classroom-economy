"""
Tests for TeacherBlock cleanup during student/period/teacher deletion.

These tests ensure that TeacherBlock entries are properly cleaned up
when students, periods, or teachers are deleted.
"""

import pyotp

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, SystemAdmin
from hash_utils import get_random_salt, hash_hmac


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create an admin/teacher with TOTP authentication."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_sysadmin() -> tuple[SystemAdmin, str]:
    """Create a system admin with TOTP authentication."""
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username="sysadmin", totp_secret=secret)
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
        dob_sum=2025,
        teacher_id=teacher.id,
    )
    db.session.add(student)
    db.session.flush()
    
    # Create StudentTeacher link
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    
    # Create TeacherBlock entry
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
        student_id=student.id,
    )
    db.session.add(teacher_block)
    db.session.commit()
    
    return student, teacher_block


def _login_admin(client, admin: Admin, secret: str):
    """Log in as admin."""
    return client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str):
    """Log in as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": sysadmin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_delete_student_removes_teacher_block(client):
    """When a student is deleted, their TeacherBlock entry should be removed."""
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
    assert Student.query.get(student_id) is None
    
    # Verify TeacherBlock is also deleted
    assert TeacherBlock.query.get(teacher_block_id) is None


def test_bulk_delete_students_removes_teacher_blocks(client):
    """When students are bulk deleted, their TeacherBlock entries should be removed."""
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
        json={"student_ids": [student1_id, student2_id]},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify students are deleted
    assert Student.query.get(student1_id) is None
    assert Student.query.get(student2_id) is None
    
    # Verify TeacherBlocks are also deleted
    assert TeacherBlock.query.get(tb1_id) is None
    assert TeacherBlock.query.get(tb2_id) is None


def test_delete_block_removes_teacher_blocks(client):
    """When a block is deleted, all TeacherBlock entries for that block should be removed."""
    teacher, secret = _create_admin("teacher-block-del")
    _create_student_with_teacher_block("Alice", teacher, block="X")
    _create_student_with_teacher_block("Bob", teacher, block="X")
    
    # Create an unclaimed TeacherBlock in the same block
    unclaimed_tb = TeacherBlock(
        teacher_id=teacher.id,
        block="X",
        first_name="Unclaimed",
        last_initial="U",
        last_name_hash_by_part=[],
        dob_sum=2025,
        salt=get_random_salt(),
        first_half_hash="test_hash",
        join_code=f"TESTX{teacher.id}",
        is_claimed=False,
    )
    db.session.add(unclaimed_tb)
    db.session.commit()
    _login_admin(client, teacher, secret)
    
    # Delete the block
    response = client.post(
        "/admin/students/delete-block",
        json={"block": "X"},
        content_type="application/json"
    )
    
    assert response.status_code == 200
    
    # Verify all TeacherBlocks for block X are deleted (including unclaimed)
    remaining_tbs = TeacherBlock.query.filter_by(teacher_id=teacher.id, block="X").all()
    assert len(remaining_tbs) == 0


def test_sysadmin_delete_period_removes_teacher_blocks(client):
    """When sysadmin deletes a period, TeacherBlock entries should be removed."""
    teacher, _ = _create_admin("teacher-period")
    sysadmin, sys_secret = _create_sysadmin()
    
    # Make teacher inactive so sysadmin can delete without request
    teacher.last_login = None
    db.session.commit()
    
    student, tb = _create_student_with_teacher_block("Alice", teacher, block="Y")
    tb_id = tb.id
    
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Delete the period
    response = client.post(
        f"/sysadmin/delete-period/{teacher.id}/Y",
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    # Verify TeacherBlock for block Y is deleted
    assert TeacherBlock.query.get(tb_id) is None


def test_sysadmin_delete_teacher_removes_teacher_blocks(client):
    """When sysadmin deletes a teacher, all their TeacherBlock entries should be removed."""
    teacher, _ = _create_admin("teacher-to-delete")
    sysadmin, sys_secret = _create_sysadmin()
    
    # Make teacher inactive so sysadmin can delete without request
    teacher.last_login = None
    db.session.commit()
    
    teacher_id = teacher.id
    
    student1, tb1 = _create_student_with_teacher_block("Alice", teacher, block="A")
    student2, tb2 = _create_student_with_teacher_block("Bob", teacher, block="B")
    tb1_id = tb1.id
    tb2_id = tb2.id
    
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Delete the teacher
    response = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher_id}",
        follow_redirects=True
    )
    
    assert response.status_code == 200
    
    # Verify TeacherBlocks are deleted
    assert TeacherBlock.query.get(tb1_id) is None
    assert TeacherBlock.query.get(tb2_id) is None
