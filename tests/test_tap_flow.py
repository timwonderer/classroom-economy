from app import db, Student
from werkzeug.security import generate_password_hash
from hash_utils import hash_username, get_random_salt
from bs4 import BeautifulSoup
import json

def login(client, username, pin):
    return client.post('/student/login', data={'username': username, 'pin': pin})

def parse_server_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find(id='serverState')
    return json.loads(script.string)

def test_dynamic_blocks_and_tap_flow(client):
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create a teacher and link the student
    teacher = Admin(username="tapflow-teacher", totp_secret=pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # 1. Create a two-block student
    salt = get_random_salt()
    username = "t1"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A,C",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
        teacher_id=teacher.id
    )
    db.session.add(stu)
    db.session.flush()

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(student_id=stu.id, admin_id=teacher.id)
    db.session.add(st)
    db.session.commit()

    # 2. Log in
    resp = login(client, username, "0000")
    assert resp.status_code == 302

    # 3. Dashboard must include both “Block A” and “Block C”
    dash_html = client.get('/student/dashboard').data.decode()
    assert "Block A" in dash_html
    assert "Block C" in dash_html

    # 4. Tap in to A
    j = client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    assert j.status_code == 200 and j.json['status'] == 'ok'

    # 5. On next dashboard load, A should be “active”
    dash_state = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":true' in dash_state

    # 6. Tap out with “done”
    j2 = client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    assert j2.status_code == 200 and j2.json['status'] == 'ok'

    # 7. After refresh, “done” state must stick
    dash_html2 = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":false,"done":true' in dash_html2

def test_invalid_period_and_action(client):
    # Set up student and log in
    salt = get_random_salt()
    username = "t2"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000")
    )
    db.session.add(stu); db.session.commit()
    login(client, username, "0000")
    # Invalid period
    resp = client.post('/api/tap', json={'period': 'Z', 'action': 'tap_in', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json

    # Invalid action
    resp = client.post('/api/tap', json={'period': 'A', 'action': 'jump', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json

def test_server_state_json(client):
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create a teacher and link the student
    teacher = Admin(username="serverstate-teacher", totp_secret=pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # Ensure serverState JSON matches interactions
    # Create and log in student
    salt = get_random_salt()
    username = "t3"
    stu = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username(username, salt),
        pin_hash=generate_password_hash("0000"),
        teacher_id=teacher.id
    )
    db.session.add(stu)
    db.session.flush()

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(student_id=stu.id, admin_id=teacher.id)
    db.session.add(st)
    db.session.commit()

    login(client, username, "0000")

    # Tap in to block A
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    dash_html = client.get('/student/dashboard').data.decode()
    state = parse_server_state(dash_html)
    assert 'A' in state
    assert state['A']['active'] is True

    # Tap out with done
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    dash_html2 = client.get('/student/dashboard').data.decode()
    state2 = parse_server_state(dash_html2)
    assert state2['A']['active'] is False
    assert state2['A']['done'] is True
