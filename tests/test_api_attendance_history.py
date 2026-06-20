"""
Tests for the /api/attendance/history endpoint to ensure it returns attendance records.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone, timedelta
from app import app, db
from app.models import Admin, Student, AttendanceSession, AttendanceReasonCode, StudentTeacher, ClassEconomy, ClassMembership, Seat
from app.hash_utils import hash_username, get_random_salt
from werkzeug.security import generate_password_hash


@pytest.fixture
def admin_with_students(client):
    """Create an admin with students and tap events for testing."""
    # Create admin
    admin = make_admin('testadmin', 'TESTSECRET123456')
    db.session.add(admin)
    db.session.flush()

    # Create admin User record for authentication
    from app.models import User, UserRole
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
        password_hash="pw",
    )
    db.session.add(user)
    db.session.flush()

    # Create student owned by this admin
    salt = get_random_salt()
    student = Student(
        first_name='Test',
        last_initial='S',
        block='A',
        salt=salt,
        username_hash=hash_username('teststudent', salt),
        pin_hash=generate_password_hash('1234'),
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher association for multi-tenancy
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    db.session.flush()
    class_row = ClassEconomy(
        join_code="ATTEND_A",
        teacher_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row)
    db.session.flush()
    db.session.add(ClassMembership(class_id=class_row.class_id, admin_id=admin.id, role="admin"))
    seat = Seat(
        student_id=student.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        block="A",
        role="student",
    )
    db.session.add(seat)
    db.session.flush()

    # Create some tap events for this student
    now_utc = datetime.now(timezone.utc)
    
    # Tap in event (1 hour ago)
    tap_in = AttendanceSession(
        student_id=student.id,
        seat_id=seat.id,
        class_id=class_row.class_id,
        period='A',
        started_at=now_utc - timedelta(hours=1),
    )
    db.session.add(tap_in)

    # Tap out event (30 minutes ago)
    tap_out = AttendanceSession(
        student_id=student.id,
        seat_id=seat.id,
        class_id=class_row.class_id,
        period='A',
        started_at=now_utc - timedelta(minutes=30),
        ended_at=now_utc - timedelta(minutes=30),
        duration_seconds=0,
        end_reason='done for the day',
    )
    db.session.add(tap_out)
    
    db.session.commit()
    
    return {
        'admin': admin,
        'user': user,
        'student': student,
        'seat': seat,
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
        'tap_events': [tap_in, tap_out]
    }


def test_attendance_history_returns_records(client, admin_with_students):
    """Test that /api/attendance/history returns attendance records for an admin's students."""
    admin = admin_with_students['admin']
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = admin_with_students['user'].id
        sess['current_class_id'] = admin_with_students['class_id']
        sess['current_join_code'] = admin_with_students['join_code']
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Call the API endpoint
    response = client.get('/api/attendance/history')
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data['status'] == 'success'
    assert data['total'] > 0, "Expected at least one attendance record"
    assert len(data['records']) > 0, "Expected records array to have at least one item"
    
    # Verify record structure
    record = data['records'][0]
    assert 'student_name' in record
    assert 'period' in record
    assert 'status' in record
    assert 'timestamp' in record
    assert record['timestamp'] is not None
    # Verify timestamp ends with 'Z' (UTC indicator)
    assert record['timestamp'].endswith('Z'), "Timestamp should end with 'Z' for UTC"


def test_attendance_history_with_date_filters(client, admin_with_students):
    """Test that date filters work correctly with UTC timestamps."""
    admin = admin_with_students['admin']
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = admin_with_students['user'].id
        sess['current_class_id'] = admin_with_students['class_id']
        sess['current_join_code'] = admin_with_students['join_code']
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Use the tap event date to avoid timezone-boundary flakiness.
    # Always convert to UTC first because psycopg2 may return timestamps
    # in the PostgreSQL session timezone (e.g. Pacific), and the API
    # endpoint interprets date filter parameters as UTC.
    event_ts = admin_with_students['tap_events'][0].timestamp
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)
    else:
        event_ts = event_ts.astimezone(timezone.utc)
    today_str = event_ts.date().strftime('%Y-%m-%d')
    
    # Call the API endpoint with today's date as filter
    response = client.get(f'/api/attendance/history?start_date={today_str}&end_date={today_str}')
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data['status'] == 'success'
    assert data['total'] > 0, "Expected records when filtering by today's date"
    assert len(data['records']) > 0


def test_attendance_history_tenant_scoping(client):
    """Test that admins can only see their own students' attendance records."""
    # Create two admins
    admin1 = make_admin('admin1', 'TESTSECRET1')
    admin2 = make_admin('admin2', 'TESTSECRET2')
    db.session.add_all([admin1, admin2])
    db.session.flush()

    # Create admin User records for authentication
    from app.models import User, UserRole
    user1 = User(
        user_role=UserRole.TEACHER,
        username_hash=admin1.username_hash,
        username_lookup_hash=admin1.username_lookup_hash,
        password_hash="pw",
    )
    user2 = User(
        user_role=UserRole.TEACHER,
        username_hash=admin2.username_hash,
        username_lookup_hash=admin2.username_lookup_hash,
        password_hash="pw",
    )
    db.session.add_all([user1, user2])
    db.session.flush()

    # Create student for admin1
    salt1 = get_random_salt()
    student1 = Student(
        first_name='Student',
        last_initial='1',
        block='A',
        salt=salt1,
        username_hash=hash_username('student1', salt1),
        pin_hash=generate_password_hash('1234'),
        has_completed_setup=True
    )
    
    # Create student for admin2
    salt2 = get_random_salt()
    student2 = Student(
        first_name='Student',
        last_initial='2',
        block='B',
        salt=salt2,
        username_hash=hash_username('student2', salt2),
        pin_hash=generate_password_hash('1234'),
        has_completed_setup=True
    )
    db.session.add_all([student1, student2])
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(student_id=student1.id, teacher_id=admin1.id))
    db.session.add(StudentTeacher(student_id=student2.id, teacher_id=admin2.id))
    db.session.flush()
    class1 = ClassEconomy(join_code="ATTEND_1", teacher_id=admin1.id, status="active", created_by_admin_id=admin1.id)
    class2 = ClassEconomy(join_code="ATTEND_2", teacher_id=admin2.id, status="active", created_by_admin_id=admin2.id)
    db.session.add_all([class1, class2])
    db.session.flush()
    db.session.add_all([
        ClassMembership(class_id=class1.class_id, admin_id=admin1.id, role="admin"),
        ClassMembership(class_id=class2.class_id, admin_id=admin2.id, role="admin"),
    ])
    seat1 = Seat(student_id=student1.id, class_id=class1.class_id, join_code=class1.join_code, block="A", role="student")
    seat2 = Seat(student_id=student2.id, class_id=class2.class_id, join_code=class2.join_code, block="B", role="student")
    db.session.add_all([seat1, seat2])
    db.session.flush()

    # Create tap events for both students
    now_utc = datetime.now(timezone.utc)
    
    tap1 = AttendanceSession(
        student_id=student1.id,
        seat_id=seat1.id,
        class_id=class1.class_id,
        period='A',
        started_at=now_utc,
    )
    tap2 = AttendanceSession(
        student_id=student2.id,
        seat_id=seat2.id,
        class_id=class2.class_id,
        period='B',
        started_at=now_utc,
    )
    db.session.add_all([tap1, tap2])
    db.session.commit()

    # Log in as admin1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin1.id
        sess['user_id'] = user1.id
        sess['current_class_id'] = class1.class_id
        sess['current_join_code'] = class1.join_code
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Call the API endpoint as admin1
    response = client.get('/api/attendance/history')
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data['status'] == 'success'
    # Admin1 should only see student1's record, not student2's
    assert data['total'] == 1, f"Admin1 should see exactly 1 record, got {data['total']}"
    assert len(data['records']) == 1
    assert data['records'][0]['student_block'] == 'A'
    assert data['records'][0]['student_name'].startswith('Student')


def test_attendance_history_excludes_deleted_records(client, admin_with_students):
    """Test that deleted tap events do not appear in attendance history."""
    admin = admin_with_students['admin']
    student = admin_with_students['student']
    
    # Create a new tap event that we'll mark as deleted
    now_utc = datetime.now(timezone.utc)
    deleted_tap = AttendanceSession(
        student_id=student.id,
        seat_id=admin_with_students['seat'].id,
        class_id=admin_with_students['class_id'],
        period='B',
        started_at=now_utc - timedelta(minutes=15),
        is_deleted=True,
        deleted_at=now_utc - timedelta(minutes=5),
    )
    db.session.add(deleted_tap)
    db.session.commit()
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = admin_with_students['user'].id
        sess['current_class_id'] = admin_with_students['class_id']
        sess['current_join_code'] = admin_with_students['join_code']
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Call the API endpoint
    response = client.get('/api/attendance/history')
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data['status'] == 'success'
    # Should only see the 2 original tap events (tap_in and tap_out), not the deleted one
    assert data['total'] == 2, f"Expected 2 records (excluding deleted), got {data['total']}"
    assert len(data['records']) == 2
    
    # Verify none of the returned records are from period B (the deleted one)
    for record in data['records']:
        assert record['period'] != 'B', "Deleted tap event should not appear in results"


def test_attendance_history_dedupes_duplicate_daily_limit_tapouts(client, admin_with_students):
    """Duplicate auto tap-outs with identical daily-limit payload should render once."""
    admin = admin_with_students['admin']
    student = admin_with_students['student']
    now_utc = datetime.now(timezone.utc)
    duplicate_ts = now_utc - timedelta(minutes=10)
    reason = "Daily limit (1.2h) reached"

    # Simulate duplicate inserts from concurrent workers.
    db.session.add(AttendanceSession(
        student_id=student.id,
        seat_id=admin_with_students['seat'].id,
        class_id=admin_with_students['class_id'],
        period='A',
        started_at=duplicate_ts,
        ended_at=duplicate_ts,
        duration_seconds=0,
        end_reason=reason,
        end_reason_code=AttendanceReasonCode.DAILY_LIMIT,
    ))
    db.session.add(AttendanceSession(
        student_id=student.id,
        seat_id=admin_with_students['seat'].id,
        class_id=admin_with_students['class_id'],
        period='A',
        started_at=duplicate_ts,
        ended_at=duplicate_ts,
        duration_seconds=0,
        end_reason=reason,
        end_reason_code=AttendanceReasonCode.DAILY_LIMIT,
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = admin_with_students['user'].id
        sess['current_class_id'] = admin_with_students['class_id']
        sess['current_join_code'] = admin_with_students['join_code']
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    response = client.get('/api/attendance/history')
    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 4  # tap-in + existing tap-out + two duplicate daily-limit tap-outs
    daily_limit_rows = [
        record for record in data['records']
        if record['status'] == 'inactive' and record.get('reason') == reason
    ]
    assert len(daily_limit_rows) == 2
