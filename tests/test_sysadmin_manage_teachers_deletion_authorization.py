"""
Regression tests for sysadmin manage-teachers deletion policy.

System admins should not have executable teacher/class deletion actions.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp

from app import db
from app.models import SystemAdmin
from tests.helpers.class_scope import create_class_scope, make_student_identity


def _create_sysadmin(username: str):
    secret = pyotp.random_base32()
    sysadmin = make_sysadmin(username, secret)
    db.session.commit()
    return sysadmin, secret


def _create_teacher(username: str):
    teacher = make_admin(username, pyotp.random_base32())
    db.session.flush()
    return teacher


def _create_student_for_teacher(teacher, first_name: str = "Alex"):
    join_code = f"MGMT{first_name[:4].upper()}"
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code)
    db.session.flush()
    student_seat = make_student_identity(
        class_id=class_row.class_id,
        first_name=first_name,
        last_name="Test",
        claimed=True,
    )
    db.session.commit()
    return student_seat


def _login_sysadmin(client, sysadmin, secret: str, username: str = "sysadmin"):
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_manage_teachers_hides_delete_actions(client):
    teacher = _create_teacher("teacher-account-request")
    _create_student_for_teacher(teacher, first_name="Avery")

    sysadmin, secret = _create_sysadmin("sysadmin-account-request")
    _login_sysadmin(client, sysadmin, secret, username="sysadmin-account-request")

    response = client.get("/sysadmin/manage-teachers")
    assert response.status_code == 200
    html = response.data.decode()

    assert f"/sysadmin/manage-teachers/delete/{teacher.id}" not in html
    assert f"/sysadmin/delete-period/{teacher.id}/A" not in html
