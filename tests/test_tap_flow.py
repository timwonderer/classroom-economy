from app import db, Student, TapSession
from werkzeug.security import generate_password_hash
from bs4 import BeautifulSoup
import json

def login(client, qr_id, pin):
    return client.post('/student/login', data={'qr_id': qr_id, 'pin': pin})

def parse_server_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find(id='serverState')
    return json.loads(script.string)

def test_dynamic_blocks_and_tap_flow(client):
    # 1. Create a two-block student
    stu = Student(
        name="Test Student",
        email="t@t.com",
        qr_id="T1",
        pin_hash=generate_password_hash("0000"),
        block="A,C"
    )
    db.session.add(stu); db.session.commit()

    # 2. Log in
    resp = login(client, "T1", "0000")
    assert resp.status_code == 302

    # 3. Dashboard must include both “Block A” and “Block C”
    dash_html = client.get('/student/dashboard').data.decode()
    assert "Block A" in dash_html
    assert "Block C" in dash_html

    # 4. Tap in to A
    j = client.post('/api/tap', json={'period': 'A', 'action': 'tap_in'})
    assert j.status_code == 200 and j.json['status'] == 'ok'

    # 5. On next dashboard load, A should be “active”
    dash_state = client.get('/student/dashboard').data.decode()
    assert '"A":[true' in dash_state

    # 6. Tap out with “done”
    j2 = client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done'})
    assert j2.status_code == 200 and j2.json['status'] == 'ok'

    # 7. After refresh, “done” state must stick
    dash_state2 = client.get('/student/dashboard').data.decode()
    assert '"A":[false,true' in dash_state2

def test_invalid_period_and_action(client):
    # Set up student and log in
    stu = Student(
        name="Test Student",
        email="t@t.com",
        qr_id="T1",
        pin_hash=generate_password_hash("0000"),
        block="A"
    )
    db.session.add(stu); db.session.commit()
    login(client, "T1", "0000")
    # Invalid period
    resp = client.post('/api/tap', json={'period': 'Z', 'action': 'tap_in'})
    assert resp.status_code == 400
    assert 'error' in resp.json

    # Invalid action
    resp = client.post('/api/tap', json={'period': 'A', 'action': 'jump'})
    assert resp.status_code == 400
    assert 'error' in resp.json

def test_server_state_json(client):
    # Ensure serverState JSON matches interactions
    # Create and log in student
    stu = Student(
        name="Test Student",
        email="t@t.com",
        qr_id="T1",
        pin_hash=generate_password_hash("0000"),
        block="A"
    )
    db.session.add(stu); db.session.commit()
    login(client, "T1", "0000")

    # Tap in to block A
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_in'})
    dash_html = client.get('/student/dashboard').data.decode()
    state = parse_server_state(dash_html)
    assert 'A' in state
    assert state['A'][0] is True  # active

    # Tap out with done
    client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done'})
    dash_html2 = client.get('/student/dashboard').data.decode()
    state2 = parse_server_state(dash_html2)
    assert state2['A'][0] is False
    assert state2['A'][1] is True  # done flag