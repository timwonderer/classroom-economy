"""
Tests for the attendance log page to ensure it renders with proper context.
"""
import pytest
from datetime import datetime, timezone
from app import app, db
from app.models import Admin, Student, TapEvent, StudentTeacher
from hash_utils import hash_username, get_random_salt


@pytest.fixture
def client():
    """Create a test client with a test database."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


@pytest.fixture
def admin_with_data(client):
    """Create an admin with students and tap events."""
    # Create admin
    admin = Admin(
        username='testadmin',
        totp_secret='TESTSECRET123456'
    )
    db.session.add(admin)
    db.session.flush()
    
    # Create students with blocks
    salt1 = get_random_salt()
    student1 = Student(
        username_hash=hash_username('student1', salt1),
        salt=salt1,
        first_name='Test',
        last_initial='T',
        pin_hash='hashed_pin',
        block='PERIOD1,PERIOD2',
        teacher_id=admin.id
    )
    salt2 = get_random_salt()
    student2 = Student(
        username_hash=hash_username('student2', salt2),
        salt=salt2,
        first_name='Student',
        last_initial='S',
        pin_hash='hashed_pin',
        block='PERIOD3',
        teacher_id=admin.id
    )
    db.session.add_all([student1, student2])
    db.session.flush()
    
    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(student_id=student1.id, admin_id=admin.id))
    db.session.add(StudentTeacher(student_id=student2.id, admin_id=admin.id))
    db.session.flush()
    
    # Create tap events with different periods
    tap1 = TapEvent(
        student_id=student1.id,
        period='PERIOD1',
        status='active',
        timestamp=datetime.now(timezone.utc)
    )
    tap2 = TapEvent(
        student_id=student1.id,
        period='PERIOD2',
        status='inactive',
        timestamp=datetime.now(timezone.utc)
    )
    tap3 = TapEvent(
        student_id=student2.id,
        period='PERIOD3',
        status='active',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add_all([tap1, tap2, tap3])
    db.session.commit()
    
    return {
        'admin': admin,
        'students': [student1, student2],
        'tap_events': [tap1, tap2, tap3]
    }


def test_attendance_log_page_renders_with_periods_and_blocks(client, admin_with_data):
    """Test that the attendance log page renders with periods and blocks context."""
    admin = admin_with_data['admin']
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Access the attendance log page
    response = client.get('/admin/attendance-log')
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Verify the page contains the periods from tap events
    assert 'PERIOD1' in html, "Expected PERIOD1 to be in the page"
    assert 'PERIOD2' in html, "Expected PERIOD2 to be in the page"
    assert 'PERIOD3' in html, "Expected PERIOD3 to be in the page"
    
    # Verify the page contains the filter dropdowns
    assert 'filterPeriod' in html, "Expected period filter dropdown"
    assert 'filterBlock' in html, "Expected block filter dropdown"
    
    # Verify page structure
    assert 'Attendance Log' in html or 'Attendance History' in html


def test_attendance_log_page_with_no_data(client):
    """Test that the attendance log page renders even with no data."""
    # Create admin with no students
    admin = Admin(
        username='testadmin2',
        totp_secret='TESTSECRET789'
    )
    db.session.add(admin)
    db.session.commit()
    
    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Access the attendance log page
    response = client.get('/admin/attendance-log')
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Page should render even with empty data
    assert 'filterPeriod' in html
    assert 'filterBlock' in html


def test_attendance_log_tenant_scoping(client):
    """Test that admins only see periods/blocks from their own students."""
    # Create two admins
    admin1 = Admin(username='admin1', totp_secret='SECRET1')
    admin2 = Admin(username='admin2', totp_secret='SECRET2')
    db.session.add_all([admin1, admin2])
    db.session.flush()
    
    # Create students for each admin
    salt1 = get_random_salt()
    student1 = Student(
        username_hash=hash_username('student1', salt1),
        salt=salt1,
        first_name='Student1',
        last_initial='S',
        pin_hash='hash1',
        block='ADMIN1PERIOD',
        teacher_id=admin1.id
    )
    salt2 = get_random_salt()
    student2 = Student(
        username_hash=hash_username('student2', salt2),
        salt=salt2,
        first_name='Student2',
        last_initial='S',
        pin_hash='hash2',
        block='ADMIN2PERIOD',
        teacher_id=admin2.id
    )
    db.session.add_all([student1, student2])
    db.session.flush()
    
    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(student_id=student1.id, admin_id=admin1.id))
    db.session.add(StudentTeacher(student_id=student2.id, admin_id=admin2.id))
    db.session.flush()
    
    # Create tap events
    tap1 = TapEvent(
        student_id=student1.id,
        period='ADMIN1PERIOD',
        status='active',
        timestamp=datetime.now(timezone.utc)
    )
    tap2 = TapEvent(
        student_id=student2.id,
        period='ADMIN2PERIOD',
        status='active',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add_all([tap1, tap2])
    db.session.commit()
    
    # Log in as admin1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin1.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Access the attendance log page
    response = client.get('/admin/attendance-log')
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Admin1 should see their period but not admin2's period
    assert 'ADMIN1PERIOD' in html, "Admin1 should see their own period"
    assert 'ADMIN2PERIOD' not in html, "Admin1 should not see admin2's period"
