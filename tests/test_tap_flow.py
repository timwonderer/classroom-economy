from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from werkzeug.security import generate_password_hash
from app.hash_utils import hash_username, hash_username_lookup, get_random_salt
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity

def login(client, username, pin):
    return client.post('/student/login', data={'username': username, 'pin': pin})

def parse_server_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find(id='serverState')
    return json.loads(script.string)

def create_claimed_seat(teacher_id, student_id, block, join_code, salt=None, username=None, pin=None):
    from app.models import ClassEconomy, Seat, User, UserRole, IdentityProfile
    if salt is None:
        salt = get_random_salt()

    # Ensure ClassEconomy exists for FK constraint
    class_economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_economy:
        class_economy = ClassEconomy(
            join_code=join_code,
            user_id=teacher_id,
            display_name=f"Class {join_code}",
            status="active",
            created_by_admin_id=teacher_id,
        )
        db.session.add(class_economy)
        db.session.flush()

    identity_user = (
        User.query
        .join(Seat, Seat.user_id == User.id)
        .filter(Seat.user_id == student_id)
        .order_by(Seat.id.asc())
        .first()
    )
    if not identity_user:
        identity_user = User(
            user_role=UserRole.STUDENT,
            username_hash=hash_username(f"tapflow_{student_id}_{join_code.lower()}", salt),
            username_lookup_hash=hash_username_lookup(username) if username else None,
            password_hash=generate_password_hash("test-passphrase"),
            pin_hash=generate_password_hash(pin) if pin else None,
            last_active_class_id=class_economy.class_id,
        )
        db.session.add(identity_user)
        db.session.flush()
    elif not identity_user.last_active_class_id:
        identity_user.last_active_class_id = class_economy.class_id

    tb = Seat(user_id=identity_user.id, class_id=class_economy.class_id, join_code=join_code, block=block, block_identifier=block, role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(tb)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name="Test", last_initial="S"))
    db.session.add(tb)
    db.session.flush()

    db.session.add(Seat(
        user_id=identity_user.id,
        class_id=class_economy.class_id,
        join_code=join_code,
        block=block,
        block_identifier=block,
        role="student",
        claimed_at=datetime.now(timezone.utc),
    ))
    return tb

def test_dynamic_blocks_and_tap_flow(client):
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create a teacher and link the student
    teacher = make_admin("tapflow-teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # 1. Create a two-block student
    username = "t1"
    stu = make_student_identity(block="A,C", first_name="Test", last_name="S")

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(user_id=stu.user_id, teacher_id=teacher.id)
    db.session.add(st)

    # Create TeacherBlocks for the student (required for join_code context)
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", username=username, pin="0000")
    create_claimed_seat(teacher.id, stu.id, "C", "JOIN-C")

    db.session.commit()

    # 2. Log in
    resp = login(client, username, "0000")
    assert resp.status_code == 302

    # 3. Dashboard must include the current block (Block A by default)
    # Note: New multi-tenancy model only shows ONE class at a time.
    dash_html = client.get('/student/dashboard').data.decode()
    assert "Period A" in dash_html
    # assert "Block C" in dash_html  <-- Removed: Dashboard only shows current class

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
    from app.models import Admin, StudentTeacher
    import pyotp

    # Create dummy teacher
    teacher = make_admin("t2_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # Set up student and log in
    username = "t2"
    stu = make_student_identity(block="A", first_name="Test", last_name="S")

    db.session.add(StudentTeacher(user_id=stu.user_id, teacher_id=teacher.id))

    # Create TeacherBlock
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-T2", username=username, pin="0000")

    db.session.commit()
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
    teacher = make_admin("serverstate-teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    # Ensure serverState JSON matches interactions
    # Create and log in student
    username = "t3"
    stu = make_student_identity(block="A", first_name="Test", last_name="S")

    # Link student to teacher via StudentTeacher
    st = StudentTeacher(user_id=stu.user_id, teacher_id=teacher.id)
    db.session.add(st)

    # Create TeacherBlock
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", username=username, pin="0000")

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

def test_auto_tapout_noops_without_canonical_seat_scope(client):
    """
    Auto-tap-out should no-op when no canonical class/seat scope exists.
    """
    from app.models import Admin, PayrollSettings, ClassEconomy
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    import pyotp

    # Create teacher and payroll settings (student will intentionally have no seat).
    teacher = make_admin("legacy_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    class_economy = ClassEconomy(
        join_code="LEGACY_JOIN",
        user_id=teacher.id,
        display_name="Legacy Class",
        status="active",
        created_by_admin_id=teacher.id,
    )
    db.session.add(class_economy)
    db.session.flush()

    ps = PayrollSettings(
        class_id=class_economy.class_id,
        block="A",
        daily_limit_hours=0.001, # very small limit to trigger immediate tapout
        settings_mode='simple'
    )
    db.session.add(ps)

    # 1. Create a student with a period
    username = "legacy_test"
    stu = make_student_identity(block="A", first_name="Legacy", last_name="T")
    
    # Link to teacher
    from app.models import StudentTeacher
    st = StudentTeacher(user_id=stu.user_id, teacher_id=teacher.id)
    db.session.add(st)
    db.session.commit()

    # No canonical seat/class context exists for this student; function should no-op.
    check_and_auto_tapout_if_limit_reached(stu)


def test_student_status_get_is_read_only_and_reconcile_is_explicit_mutation(client, monkeypatch):
    from datetime import datetime, timezone
    from app.models import Admin, StudentTeacher, ClassEconomy, Seat
    import pyotp
    from app.routes import api as api_routes

    teacher = make_admin("status_teacher", pyotp.random_base32())
    db.session.add(teacher)
    db.session.flush()

    username = "status_student"
    stu = make_student_identity(block="A", first_name="Status", last_name="R")

    db.session.add(StudentTeacher(user_id=stu.user_id, teacher_id=teacher.id))
    create_claimed_seat(teacher.id, stu.id, "A", "JOIN-A", username=username, pin="0000")
    db.session.commit()
    class_row = ClassEconomy.query.filter_by(join_code="JOIN-A").first()
    seat = Seat.query.filter_by(user_id=stu.user_id, class_id=class_row.class_id).first()
    assert class_row is not None
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
            join_code="JOIN-A",
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
