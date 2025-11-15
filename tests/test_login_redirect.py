import pytest
from app import db, Student
from werkzeug.security import generate_password_hash
from hash_utils import hash_username, get_random_salt

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
