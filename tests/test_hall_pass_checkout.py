"""
Tests for hall pass checkout and checkin API endpoints.

Ensures that students can check out and check in directly from the dashboard
without using the terminal, with proper limit enforcement.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone, timedelta
from app.models import Seat, IdentityProfile, Student, Admin, HallPassLog, StudentTeacher, HallPassSettings, ClassEconomy, AttendanceSession, SeatAttendanceState, User, UserRole
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from app.utils.auth_username import build_hashed_username_fields


def _make_canonical_user(*, username: str, role: UserRole) -> User:
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    user = User(
        user_role=role,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _login_student_context(client, *, student: Student, user: User, seat: Seat, login_time: str | None = None) -> None:
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['user_id'] = user.id
        sess['current_seat_id'] = seat.id
        sess['current_class_id'] = seat.class_id
        sess['current_join_code'] = seat.join_code
        sess['is_student'] = True
        sess['login_time'] = login_time or datetime.now(timezone.utc).isoformat()


def _login_admin_context(client, *, teacher: Admin, user: User, class_id: str, join_code: str) -> None:
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
        sess['user_id'] = user.id
        sess['current_class_id'] = class_id
        sess['current_join_code'] = join_code
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def setup_hall_pass_checkout_test(client):
    """Create teacher, student, and approved hall pass for testing checkout."""
    # Create teacher
    teacher = make_admin("teacher1", "secret1")
    db.session.add(teacher)
    db.session.flush()
    teacher_user = _make_canonical_user(username="teacher1", role=UserRole.TEACHER)
    teacher.user_id = teacher_user.id
    db.session.commit()

    # Create student
    user = _make_canonical_user(username="alice_a", role=UserRole.STUDENT)

    salt = get_random_salt()
    student = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt,
        username_hash=hash_username("alice_a", salt),
        pin_hash="$2b$12$test_hash"  # Mock hash
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    economy = ClassEconomy(
        join_code="TEST123",
        user_id=teacher.id,
        display_name="Period1",
        status='active',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    # Create hall pass settings
    settings = HallPassSettings(
        class_id=economy.class_id,
        queue_enabled=True,
        queue_limit=10,
        pass_types=[
            {"name": "Bathroom", "queue_limit": None, "simultaneous_limit": 2, "enabled": True},
            {"name": "Office", "queue_limit": None, "simultaneous_limit": None, "enabled": True}
        ]
    )
    db.session.add(settings)
    db.session.commit()

    now = datetime.now(timezone.utc)
    seat = Seat(
        user_id=user.id,
        student_id=student.id,
        class_id=economy.class_id,
        join_code=economy.join_code,
        block="Period1",
        block_identifier="Period1",
        role="student",
        claimed_at=now - timedelta(days=1),
    )
    db.session.add(seat)
    db.session.flush()

    # Create approved hall pass
    hall_pass = HallPassLog(
        student_id=student.id,
        seat_id=seat.id,
        class_id=economy.class_id,
        reason="Bathroom",
        status="approved",
        period="Period1",
        request_time=now - timedelta(minutes=10),
        decision_time=now - timedelta(minutes=5),
        join_code="TEST123"
    )
    db.session.add(hall_pass)

    # Create claimed seat so current class context can be resolved in student routes.
    _tb_seat = Seat(student_id=student.id, class_id=economy.class_id, join_code="TEST123", block="Period1", block_identifier="Period1", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=student.display_first_name, last_name=student.display_last_initial))
    db.session.commit()

    return {
        'teacher': teacher,
        'teacher_user': teacher_user,
        'student': student,
        'student_user': user,
        'seat': seat,
        'economy': economy,
        'hall_pass': hall_pass,
        'settings': settings
    }


def test_checkout_with_approved_pass(client, setup_hall_pass_checkout_test):
    """Test that student can check out with an approved hall pass."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']

    _login_student_context(client, student=student, user=user, seat=seat)

    # Checkout
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'Bathroom' in json_data['message']

    # Verify status changed to 'left'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'left'
    assert hall_pass.left_time is not None

    # Verify canonical attendance state/session update
    state = SeatAttendanceState.query.filter_by(
        student_id=student.id,
        class_id=hall_pass.class_id,
        period=hall_pass.period,
    ).first()
    assert state is not None
    assert state.is_active is False
    assert state.last_event_status == 'inactive'
    assert state.last_reason == 'Bathroom'

    latest_session = AttendanceSession.query.filter_by(
        student_id=student.id,
        class_id=hall_pass.class_id,
        period=hall_pass.period,
    ).order_by(AttendanceSession.id.desc()).first()
    assert latest_session is not None
    assert latest_session.end_reason == 'Bathroom'


def test_approve_does_not_generate_pass_number(client, setup_hall_pass_checkout_test):
    """Test that approval no longer creates or returns a pass number."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    teacher = data['teacher']
    teacher_user = data['teacher_user']
    hall_pass = data['hall_pass']

    hall_pass.status = 'pending'
    hall_pass.reason = 'Office'
    hall_pass.decision_time = None
    db.session.commit()

    _login_admin_context(
        client,
        teacher=teacher,
        user=teacher_user,
        class_id=hall_pass.class_id,
        join_code=hall_pass.join_code,
    )

    response = client.post(
        f'/api/hall-pass/{hall_pass.id}/approve',
        headers={'X-CSRFToken': 'test'}
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'success'
    assert 'pass_number' not in payload

    db.session.refresh(hall_pass)
    db.session.refresh(student)
    assert hall_pass.status == 'approved'
    assert student.hall_passes == 3


def test_checkout_blocked_by_simultaneous_limit(client, setup_hall_pass_checkout_test):
    """Test that checkout is blocked when simultaneous limit is reached."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']

    # Create 2 other students already out for bathroom (limit is 2)
    for i in range(2):
        salt = get_random_salt()
        other_student = Student(
            first_name=f"Student{i}",
            last_initial="S",
            block="Period1",
            salt=salt,
            username_hash=hash_username(f"student{i}_s", salt)
        )
        db.session.add(other_student)
        db.session.commit()

        # Create 'left' hall pass for this student
        now = datetime.now(timezone.utc)
        other_pass = HallPassLog(
            student_id=other_student.id,
            class_id=hall_pass.class_id,
            reason="Bathroom",
            status="left",
            period="Period1",
            request_time=now - timedelta(minutes=15),
            decision_time=now - timedelta(minutes=10),
            left_time=now - timedelta(minutes=5),
            join_code="TEST123"
        )
        db.session.add(other_pass)
    db.session.commit()

    # Login as student
    _login_student_context(client, student=student, user=user, seat=seat)

    # Try to checkout (should fail due to limit)
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'limit reached' in json_data['message'].lower()

    # Verify status is still 'approved'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'approved'


def test_checkin_with_left_pass(client, setup_hall_pass_checkout_test):
    """Test that student can check in when they're currently out."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']

    # Set pass to 'left' status
    now = datetime.now(timezone.utc)
    hall_pass.status = 'left'
    hall_pass.left_time = now - timedelta(minutes=5)
    db.session.commit()

    # Login as student
    _login_student_context(client, student=student, user=user, seat=seat)

    # Checkin
    response = client.post('/api/hall-pass/checkin',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'checked in' in json_data['message'].lower()

    # Verify status changed to 'returned'
    db.session.refresh(hall_pass)
    assert hall_pass.status == 'returned'
    assert hall_pass.return_time is not None

    # Verify canonical attendance state/session update
    state = SeatAttendanceState.query.filter_by(
        student_id=student.id,
        class_id=hall_pass.class_id,
        period=hall_pass.period,
    ).first()
    assert state is not None
    assert state.is_active is True
    assert state.last_event_status == 'active'
    assert state.last_reason == 'Returned from hall pass'
    assert state.open_session_id is not None

    open_session = db.session.get(AttendanceSession, state.open_session_id)
    assert open_session is not None
    assert open_session.ended_at is None


def test_checkout_requires_authentication(client, setup_hall_pass_checkout_test):
    """Test that checkout requires student to be logged in."""
    data = setup_hall_pass_checkout_test
    hall_pass = data['hall_pass']

    # Try to checkout without login
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    # Should redirect to login or return 401
    assert response.status_code in [302, 401]


def test_checkout_rejects_wrong_student(client, setup_hall_pass_checkout_test):
    """Test that student cannot check out another student's pass."""
    data = setup_hall_pass_checkout_test
    hall_pass = data['hall_pass']
    economy = data['economy']

    # Create another student
    other_user = _make_canonical_user(username="bob_b", role=UserRole.STUDENT)
    salt = get_random_salt()
    other_student = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt,
        username_hash=hash_username("bob_b", salt)
    )
    db.session.add(other_student)
    db.session.flush()
    other_seat = Seat(
        user_id=other_user.id,
        student_id=other_student.id,
        class_id=economy.class_id,
        join_code=economy.join_code,
        block="Period1",
        block_identifier="Period1",
        role="student",
        claimed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.session.add(other_seat)
    _tb_seat = Seat(student_id=other_student.id, class_id=economy.class_id, join_code=economy.join_code, block="Period1", block_identifier="Period1", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=other_student.display_first_name, last_name=other_student.display_last_initial))
    db.session.commit()

    _login_student_context(client, student=other_student, user=other_user, seat=other_seat)

    # Try to checkout Alice's pass
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'unauthorized' in json_data['message'].lower()


def test_checkout_rejects_non_approved_pass(client, setup_hall_pass_checkout_test):
    """Test that checkout fails if pass is not in approved status."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']

    # Set pass to 'pending' status
    hall_pass.status = 'pending'
    db.session.commit()

    # Login as student
    _login_student_context(client, student=student, user=user, seat=seat)

    # Try to checkout
    response = client.post('/api/hall-pass/checkout',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'not approved' in json_data['message'].lower()


def test_checkin_rejects_non_left_pass(client, setup_hall_pass_checkout_test):
    """Test that checkin fails if pass is not in left status."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']

    # Pass is still in 'approved' status
    assert hall_pass.status == 'approved'

    # Login as student
    _login_student_context(client, student=student, user=user, seat=seat)

    # Try to checkin
    response = client.post('/api/hall-pass/checkin',
                          json={'pass_id': hall_pass.id},
                          headers={'X-CSRFToken': 'test'})
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'not currently checked out' in json_data['message'].lower()


def test_checkout_rejects_mismatched_class_context(client, setup_hall_pass_checkout_test):
    """Checkout should fail when active class context does not match pass class_id."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    seat = data['seat']
    hall_pass = data['hall_pass']
    teacher = data['teacher']

    other_economy = ClassEconomy(
        join_code="OTHER123",
        user_id=teacher.id,
        display_name="Period2",
        status='active',
        created_by_admin_id=teacher.id,
    )
    db.session.add(other_economy)
    db.session.flush()
    other_seat = Seat(
        user_id=user.id,
        student_id=student.id,
        class_id=other_economy.class_id,
        join_code=other_economy.join_code,
        block="Period2",
        block_identifier="Period2",
        role="student",
        claimed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.session.add(other_seat)
    _tb_seat = Seat(student_id=student.id, class_id=other_economy.class_id, join_code="OTHER123", block="Period2", block_identifier="Period2", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=student.display_first_name, last_name=student.display_last_initial))
    db.session.commit()

    _login_student_context(client, student=student, user=user, seat=other_seat)

    response = client.post(
        '/api/hall-pass/checkout',
        json={'pass_id': hall_pass.id},
        headers={'X-CSRFToken': 'test'}
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'different class context' in json_data['message'].lower()


def test_cancel_rejects_mismatched_class_context(client, setup_hall_pass_checkout_test):
    """Cancel should fail when active class context does not match pass class_id."""
    data = setup_hall_pass_checkout_test
    student = data['student']
    user = data['student_user']
    hall_pass = data['hall_pass']
    teacher = data['teacher']

    hall_pass.status = 'pending'
    hall_pass.decision_time = None
    other_economy = ClassEconomy(
        join_code="OTHER123",
        user_id=teacher.id,
        display_name="Period2",
        status='active',
        created_by_admin_id=teacher.id,
    )
    db.session.add(other_economy)
    db.session.flush()
    other_seat = Seat(
        user_id=user.id,
        student_id=student.id,
        class_id=other_economy.class_id,
        join_code=other_economy.join_code,
        block="Period2",
        block_identifier="Period2",
        role="student",
        claimed_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.session.add(other_seat)
    _tb_seat = Seat(student_id=student.id, class_id=other_economy.class_id, join_code="OTHER123", block="Period2", block_identifier="Period2", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=student.display_first_name, last_name=student.display_last_initial))
    db.session.commit()

    _login_student_context(client, student=student, user=user, seat=other_seat)

    response = client.post(
        f'/api/hall-pass/cancel/{hall_pass.id}',
        headers={'X-CSRFToken': 'test'}
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'different class context' in json_data['message'].lower()
