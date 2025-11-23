import pyotp

from app import app, db
from app.models import Admin, Student, StudentTeacher, SystemAdmin
from hash_utils import get_random_salt, hash_username


def _create_sysadmin(username: str = "sysadmin"):
    secret = pyotp.random_base32()
    sys_admin = SystemAdmin(username=username, totp_secret=secret)
    db.session.add(sys_admin)
    db.session.commit()
    return sys_admin, secret


def _create_admin(username: str) -> tuple[Admin, str]:
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, owner: Admin) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="X",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=owner.id,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, admin_id=owner.id))
    db.session.commit()
    return student


def _login_sysadmin(client, sys_admin: SystemAdmin, secret: str):
    return client.post(
        "/sysadmin/login",
        data={"username": sys_admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_sysadmin_can_add_teacher_and_set_primary(client):
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    student = _create_student("Shared", teacher_a)

    _login_sysadmin(client, sys_admin, sys_secret)

    response = client.post(
        "/sysadmin/student-ownership",
        data={
            "action": "add",
            "student_id": student.id,
            "admin_id": teacher_b.id,
            "make_primary": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert StudentTeacher.query.filter_by(student_id=student.id, admin_id=teacher_b.id).first()
    assert Student.query.get(student.id).teacher_id == teacher_b.id


def test_student_ownership_forms_include_csrf_token(client):
    sys_admin, sys_secret = _create_sysadmin()
    _login_sysadmin(client, sys_admin, sys_secret)

    previous_csrf_setting = app.config.get("WTF_CSRF_ENABLED")
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        response = client.get("/sysadmin/student-ownership")
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous_csrf_setting

    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data


def test_removing_primary_teacher_reassigns_when_available(client):
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    student = _create_student("Shared", teacher_a)

    # Add a secondary teacher and keep teacher A as primary
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher_b.id))
    db.session.commit()

    _login_sysadmin(client, sys_admin, sys_secret)

    response = client.post(
        "/sysadmin/student-ownership",
        data={
            "action": "remove",
            "student_id": student.id,
            "admin_id": teacher_a.id,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert StudentTeacher.query.filter_by(student_id=student.id, admin_id=teacher_a.id).first() is None
    # Should pick teacher B as the new primary owner
    assert Student.query.get(student.id).teacher_id == teacher_b.id
