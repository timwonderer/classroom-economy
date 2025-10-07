import pytest
from app import db, Student
from werkzeug.security import generate_password_hash
from hash_utils import get_legacy_peppers, get_random_salt, hash_username

def test_student_login_next_redirect(client):
    salt = get_random_salt()
    username = "stu1"
    stu = Student(
        first_name="Stu",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("1234"),
        has_completed_setup=True,
    )
    db.session.add(stu)
    db.session.commit()

    # Access protected route
    resp = client.get('/student/dashboard')
    assert resp.status_code == 302
    assert '/student/login?next=%2Fstudent%2Fdashboard' in resp.headers['Location']

    # Login and expect redirect back
    login_resp = client.post('/student/login?next=/student/dashboard', data={'username': 'stu1', 'pin': '1234'})
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')


def test_student_login_with_legacy_pepper_rotation(client):
    salt = get_random_salt()
    legacy_peppers = list(get_legacy_peppers())
    assert legacy_peppers, "Expected at least one legacy pepper for rotation test"
    legacy_pepper = legacy_peppers[0]

    username = "legacy_user"
    stu = Student(
        first_name="Legacy",
        last_initial="L",
        block="B",
        salt=salt,
        username_hash=hash_username(username, salt, pepper=legacy_pepper),
        pin_hash=generate_password_hash("1234"),
        has_completed_setup=True,
    )
    db.session.add(stu)
    db.session.commit()

    resp = client.post('/student/login', data={'username': username, 'pin': '1234'})
    assert resp.status_code == 302

    updated = db.session.get(Student, stu.id)
    assert updated.username_hash == hash_username(username, salt)
