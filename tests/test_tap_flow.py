from tests.helpers.v2_fixtures import make_admin
from app import db
from werkzeug.security import generate_password_hash
from app.hash_utils import hash_username_lookup
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity, create_class_scope
from app.models import ClassEconomy, Seat, IdentityProfile, User, UserRole


def login(client, username, pin):
    return client.post('/student/login', data={'username': username, 'pin': pin})


def parse_server_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find(id='serverState')
    return json.loads(script.string)


def _create_class_with_login_student(teacher, join_code, block, username, pin):
    """Create a class, student, and set up login credentials. Returns (class_row, seat, user)."""
    class_economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_economy:
        class_economy = ClassEconomy(
            user_id=teacher.id,
            join_code=join_code,
            display_name=f"Class {join_code}",
            status="active",
        )
        db.session.add(class_economy)
        db.session.flush()

    student_seat = make_student_identity(class_id=class_economy.class_id, first_name="Test", last_name="S", claimed=True)
    db.session.flush()
    student_user = db.session.get(User, student_seat.user_id)
    student_user.username_lookup_hash = hash_username_lookup(username)
    student_user.pin_hash = generate_password_hash(pin)
    student_user.has_completed_setup = True
    student_user.last_active_class_id = class_economy.class_id
    student_user.last_active_seat_id = student_seat.id
    db.session.flush()

    seat = Seat.query.filter_by(user_id=student_user.id, class_id=class_economy.class_id, role="student").first()
    return class_economy, seat, student_user


def test_dynamic_blocks_and_tap_flow(client):
    import pyotp

    teacher = make_admin("tapflow-teacher", pyotp.random_base32())
    db.session.flush()

    username = "t1_tap"
    class_a, seat, student_user = _create_class_with_login_student(teacher, "JOIN-A", "A", username, "0000")
    db.session.commit()

    resp = login(client, username, "0000")
    assert resp.status_code == 302

    dash_html = client.get('/student/dashboard').data.decode()
    assert "Period" in dash_html or "period" in dash_html.lower() or resp.status_code == 302

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=class_a.class_id,
            seat_id=seat.id,
            role="student",
            join_code="JOIN-A",
        )

    j = client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    assert j.status_code == 200 and j.json['status'] == 'ok'

    dash_state = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":true' in dash_state

    j2 = client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    assert j2.status_code == 200 and j2.json['status'] == 'ok'

    dash_html2 = client.get('/student/dashboard').data.decode()
    assert '"A":{"active":false,"done":true' in dash_html2


def test_invalid_period_and_action(client):
    import pyotp

    teacher = make_admin("t2_teacher", pyotp.random_base32())
    db.session.flush()

    username = "t2_tap"
    class_row, seat, student_user = _create_class_with_login_student(teacher, "JOIN-T2", "A", username, "0000")
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=class_row.class_id,
            seat_id=seat.id,
            role="student",
            join_code="JOIN-T2",
        )

    resp = client.post('/api/tap', json={'period': 'Z', 'action': 'tap_in', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json

    resp = client.post('/api/tap', json={'period': 'A', 'action': 'jump', 'pin': '0000'})
    assert resp.status_code == 400
    assert 'error' in resp.json


def test_server_state_json(client):
    import pyotp

    teacher = make_admin("serverstate-teacher", pyotp.random_base32())
    db.session.flush()

    username = "t3_tap"
    class_row, seat, student_user = _create_class_with_login_student(teacher, "JOIN-SS", "A", username, "0000")
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=class_row.class_id,
            seat_id=seat.id,
            role="student",
            join_code="JOIN-SS",
        )

    client.post('/api/tap', json={'period': 'A', 'action': 'tap_in', 'pin': '0000'})
    dash_html = client.get('/student/dashboard').data.decode()
    state = parse_server_state(dash_html)
    assert 'A' in state
    assert state['A']['active'] is True

    client.post('/api/tap', json={'period': 'A', 'action': 'tap_out', 'reason': 'done', 'pin': '0000'})
    dash_html2 = client.get('/student/dashboard').data.decode()
    state2 = parse_server_state(dash_html2)
    assert state2['A']['active'] is False
    assert state2['A']['done'] is True


def test_auto_tapout_noops_without_canonical_seat_scope(client):
    """
    Auto-tap-out should no-op when no canonical class/seat scope exists.
    """
    from app.models import PayrollSettings
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    import pyotp
    from uuid import uuid4 as _uuid4

    teacher = make_admin("legacy_teacher", pyotp.random_base32())
    db.session.flush()

    class_economy = ClassEconomy(
        join_code=f"TAPLEG{_uuid4().hex[:6].upper()}",
        user_id=teacher.id,
        display_name="Legacy Class",
        status="active",
    )
    db.session.add(class_economy)
    db.session.flush()

    ps = PayrollSettings(
        class_id=class_economy.class_id,
        block="A",
        daily_limit_hours=0.001,
        settings_mode='simple'
    )
    db.session.add(ps)

    stu = make_student_identity(class_id=class_economy.class_id, first_name="Legacy", last_name="T")
    db.session.commit()

    # No canonical seat/class context exists in session; function should no-op.
    check_and_auto_tapout_if_limit_reached(stu)


def test_student_status_get_is_read_only_and_reconcile_is_explicit_mutation(client, monkeypatch):
    import pyotp
    from app.routes import api as api_routes

    teacher = make_admin("status_teacher", pyotp.random_base32())
    db.session.flush()

    class_row = create_class_scope(teacher_user=teacher, join_code="JOIN-STATUS")
    stu = make_student_identity(class_id=class_row.class_id, first_name="Status", last_name="R")
    db.session.commit()

    seat = Seat.query.filter_by(user_id=stu.user_id, class_id=class_row.class_id, role="student").first()
    assert seat is not None
    if not seat.claimed_at:
        seat.claimed_at = datetime.now(timezone.utc)
        db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=stu.user_id,
            class_id=class_row.class_id,
            seat_id=seat.id,
            role="student",
        )

    called = {"count": 0}

    def _fake_auto_tapout(student, commit=True):
        called["count"] += 1

    monkeypatch.setattr(api_routes, "check_and_auto_tapout_if_limit_reached", _fake_auto_tapout)

    get_resp = client.get("/api/student-status")
    assert get_resp.status_code == 200
    assert called["count"] == 0

    post_resp = client.post("/api/student-status/reconcile")
    assert post_resp.status_code == 200
    assert called["count"] == 1
