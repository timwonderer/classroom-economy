"""
Regression tests for sysadmin manage-teachers deletion policy.

System admins should not have executable teacher/class deletion actions.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp

from app import db
from app.models import User, UserRole, Admin, Student, StudentTeacher, SystemAdmin
from app.hash_utils import get_random_salt, hash_hmac


def _create_sysadmin(username: str) -> tuple[SystemAdmin, str]:
    secret = pyotp.random_base32()
    sysadmin = make_sysadmin(username, secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def _create_teacher(username: str) -> Admin:
    teacher = make_admin(username, pyotp.random_base32())
    db.session.add(teacher)
    db.session.commit()
    return teacher


def _create_student_for_teacher(teacher: Admin, block: str = "A", first_name: str = "Alex") -> Student:
    salt = get_random_salt()
    first_half_hash = hash_hmac(b"A2025", salt)
    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.commit()
    return student


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str, username: str = "sysadmin"):
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_manage_teachers_hides_delete_actions(client):
    teacher = _create_teacher("teacher-account-request")
    _create_student_for_teacher(teacher, block="A", first_name="Avery")

    sysadmin, secret = _create_sysadmin("sysadmin-account-request")
    _login_sysadmin(client, sysadmin, secret, username="sysadmin-account-request")

    response = client.get("/sysadmin/manage-teachers")
    assert response.status_code == 200
    html = response.data.decode()

    assert f"/sysadmin/manage-teachers/delete/{teacher.id}" not in html
    assert f"/sysadmin/delete-period/{teacher.id}/A" not in html
