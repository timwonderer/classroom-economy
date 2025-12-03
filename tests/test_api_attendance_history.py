"""
Tests for the /api/attendance/history endpoint to ensure it returns attendance records.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import app, db
from app.models import Admin, Student, TapEvent, StudentTeacher
from hash_utils import hash_username, get_random_salt
from werkzeug.security import generate_password_hash


@pytest.fixture
def admin_with_students(client):
    """Create an admin with students and tap events for testing."""
    # Create admin
    admin = Admin(
        username='testadmin',
        totp_secret='TESTSECRET123456'
    )
    db.session.add(admin)
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
        has_completed_setup=True,
        teacher_id=admin.id  # Primary ownership
    )
    db.session.add(student)
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher association for multi-tenancy
    db.session.add(StudentTeacher(student_id=student.id, admin_id=admin.id))
    db.session.flush()

    # Create some tap events for this student
    now_utc = datetime.now(timezone.utc)
    
    # Tap in event (1 hour ago)
    tap_in = TapEvent(
        student_id=student.id,
        period='A',
        status='active',
        timestamp=now_utc - timedelta(hours=1)
    )
    db.session.add(tap_in)
    
    # Tap out event (30 minutes ago)
    tap_out = TapEvent(
        student_id=student.id,
        period='A',
        status='inactive',
        timestamp=now_utc - timedelta(minutes=30),
        reason='done for the day'
    )
    db.session.add(tap_out)
    
    db.session.commit()
    
    return {
        'admin': admin,
        'student': student,
        'tap_events': [tap_in, tap_out]
    }


def test_attendance_history_returns_records(client, admin_with_students):
    """Test that /api/attendance/history returns attendance records for an admin's students."""
    admin = admin_with_students['admin']
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
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
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Get today's date in YYYY-MM-DD format
    today = datetime.now(timezone.utc).date()
    today_str = today.strftime('%Y-%m-%d')
    
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
    admin1 = Admin(
        username='admin1',
        totp_secret='TESTSECRET1'
    )
    admin2 = Admin(
        username='admin2',
        totp_secret='TESTSECRET2'
    )
    db.session.add_all([admin1, admin2])
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
        has_completed_setup=True,
        teacher_id=admin1.id
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
        has_completed_setup=True,
        teacher_id=admin2.id
    )
    db.session.add_all([student1, student2])
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(student_id=student1.id, admin_id=admin1.id))
    db.session.add(StudentTeacher(student_id=student2.id, admin_id=admin2.id))
    db.session.flush()

    # Create tap events for both students
    now_utc = datetime.now(timezone.utc)
    
    tap1 = TapEvent(
        student_id=student1.id,
        period='A',
        status='active',
        timestamp=now_utc
    )
    tap2 = TapEvent(
        student_id=student2.id,
        period='B',
        status='active',
        timestamp=now_utc
    )
    db.session.add_all([tap1, tap2])
    db.session.commit()

    # Log in as admin1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin1.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Call the API endpoint as admin1
    response = client.get('/api/attendance/history')
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data['status'] == 'success'
    # Admin1 should only see student1's record, not student2's
    assert data['total'] == 1, f"Admin1 should see exactly 1 record, got {data['total']}"
    assert len(data['records']) == 1
    assert data['records'][0]['student_id'] == student1.id
