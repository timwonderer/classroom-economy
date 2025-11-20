import pyotp

from app import db
from app.models import Admin, Student
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, teacher: Admin) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="A",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=teacher.id,
    )
    db.session.add(student)
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    return client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_student_listing_scoped_to_teacher(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    student_a = _create_student("Alice", teacher_a)
    _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get("/admin/students")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert student_a.first_name in body
    assert "Bob" not in body


def test_student_detail_forbids_cross_tenant_access(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    _create_student("Alice", teacher_a)
    student_b = _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get(f"/admin/students/{student_b.id}")

    assert response.status_code == 404
