import pytest
from app import db, Student, Admin
from werkzeug.security import generate_password_hash

def test_student_login_next_redirect(client):
    # Create student with hashed pin
    stu = Student(name="Stu", email="s@example.com", qr_id="S1", pin_hash=generate_password_hash("1234"), block="A", has_completed_setup=True)
    db.session.add(stu)
    db.session.commit()

    # Access protected route
    resp = client.get('/student/dashboard')
    assert resp.status_code == 302
    assert '/student/login?next=%2Fstudent%2Fdashboard' in resp.headers['Location']

    # Login and expect redirect back
    login_resp = client.post('/student/login?next=/student/dashboard', data={'qr_id': 'S1', 'pin': '1234'})
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')


def test_admin_login_next_redirect(client):
    # Create admin
    admin = Admin(username='admin', password_hash=Admin.hash_password('pw'))
    db.session.add(admin)
    db.session.commit()

    # Access protected admin route
    resp = client.get('/admin/students')
    assert resp.status_code == 302
    assert '/admin/login?next=%2Fadmin%2Fstudents' in resp.headers['Location']

    # Perform login
    login_resp = client.post('/admin/login?next=/admin/students', data={'username': 'admin', 'password': 'pw'})
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/admin/students')
