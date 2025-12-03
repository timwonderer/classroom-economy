"""
Tests for DeletionRequest cascade deletion when teacher is deleted.

This test ensures that when a teacher account is deleted, all associated
DeletionRequest records are properly cascade deleted from the database,
preventing NOT NULL constraint violations.
"""

import pyotp
from datetime import datetime, timezone, timedelta

from app import db
from app.models import Admin, Student, StudentTeacher, SystemAdmin, DeletionRequest, DeletionRequestType, DeletionRequestStatus
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
    sysadmin = SystemAdmin(username="sysadmin_cascade_test", totp_secret=secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def _create_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """Create a student associated with a teacher."""
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
    db.session.commit()
    
    return student


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str):
    """Log in as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": sysadmin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_delete_teacher_cascades_deletion_requests(client):
    """
    When a teacher is deleted, all their DeletionRequest records should be
    cascade deleted, not set to NULL which violates the NOT NULL constraint.
    """
    # Create teacher and make them inactive for >6 months (so sysadmin can delete)
    teacher, _ = _create_admin("teacher-with-requests")
    teacher.last_login = datetime.now(timezone.utc) - timedelta(days=200)
    db.session.commit()
    
    # Create some students for this teacher
    _create_student("Alice", teacher, block="A")
    _create_student("Bob", teacher, block="B")
    
    # Create multiple deletion requests for this teacher
    period_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.PERIOD,
        period="A",
        reason="Test period deletion",
        status=DeletionRequestStatus.PENDING,
    )
    account_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.ACCOUNT,
        reason="Test account deletion",
        status=DeletionRequestStatus.APPROVED,
    )
    another_period_request = DeletionRequest(
        admin_id=teacher.id,
        request_type=DeletionRequestType.PERIOD,
        period="B",
        status=DeletionRequestStatus.PENDING,
    )
    
    db.session.add_all([period_request, account_request, another_period_request])
    db.session.commit()
    
    period_request_id = period_request.id
    account_request_id = account_request.id
    another_period_request_id = another_period_request.id
    teacher_id = teacher.id
    
    # Create and login as sysadmin
    sysadmin, sys_secret = _create_sysadmin()
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Delete the teacher - this should cascade delete all DeletionRequest records
    response = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher_id}",
        follow_redirects=True
    )
    
    # Should succeed without NOT NULL constraint violations
    assert response.status_code == 200
    assert b"deleted" in response.data or b"Teacher" in response.data
    
    # Verify teacher is deleted
    assert Admin.query.get(teacher_id) is None
    
    # Verify all DeletionRequest records are cascade deleted (not set to NULL)
    assert DeletionRequest.query.get(period_request_id) is None
    assert DeletionRequest.query.get(account_request_id) is None
    assert DeletionRequest.query.get(another_period_request_id) is None
    
    # Verify no orphaned DeletionRequest records with NULL admin_id exist
    orphaned_requests = DeletionRequest.query.filter(
        DeletionRequest.admin_id.is_(None)
    ).all()
    assert len(orphaned_requests) == 0, "Found orphaned DeletionRequest records with NULL admin_id"


def test_delete_teacher_with_no_deletion_requests(client):
    """
    Verify that deleting a teacher without any DeletionRequest records works fine.
    This is a baseline test to ensure the fix doesn't break normal deletion.
    """
    # Create teacher and make them inactive for >6 months
    teacher, _ = _create_admin("teacher-no-requests")
    teacher.last_login = datetime.now(timezone.utc) - timedelta(days=200)
    db.session.commit()
    
    teacher_id = teacher.id
    
    # Create and login as sysadmin
    sysadmin, sys_secret = _create_sysadmin()
    _login_sysadmin(client, sysadmin, sys_secret)
    
    # Delete the teacher
    response = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher_id}",
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert Admin.query.get(teacher_id) is None
