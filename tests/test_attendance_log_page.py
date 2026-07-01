"""
Tests for the attendance log page to ensure it renders with proper context.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone
from app import db
from app.models import Admin, Student, AttendanceSession, StudentTeacher, ClassEconomy, ClassMembership, Seat, User
from app.hash_utils import hash_username, get_random_salt


def _create_user_for_admin(admin):
    """Create a User record linked to an admin."""
    user = User(
        user_role="teacher",
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id
    return user

@pytest.fixture
def admin_with_data(client):
    """Create an admin with students and tap events."""
    # Create admin
    admin = make_admin('testadmin', 'TESTSECRET123456')
    db.session.add(admin)
    db.session.flush()
    user = _create_user_for_admin(admin)

    # Create class economy
    class_row = ClassEconomy(
        join_code="ATTLOG1",
        user_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row)
    db.session.flush()
    db.session.add(ClassMembership(class_id=class_row.class_id, join_code="ATTLOG1", admin_id=admin.id, role="admin"))

    # Create students with blocks
    salt1 = get_random_salt()
    student1 = Student(
        username_hash=hash_username('student1', salt1),
        salt=salt1,
        first_name='Test',
        last_initial='T',
        pin_hash='hashed_pin',
        block='PERIOD1'
    )
    salt2 = get_random_salt()
    student2 = Student(
        username_hash=hash_username('student2', salt2),
        salt=salt2,
        first_name='Student',
        last_initial='S',
        pin_hash='hashed_pin',
        block='PERIOD3'
    )
    db.session.add_all([student1, student2])
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(user_id=student1_user.id, teacher_id=admin.id))
    db.session.add(StudentTeacher(user_id=student2_user.id, teacher_id=admin.id))
    db.session.flush()

    # Create seats
    # Auto-injected Canonical User
    student1_user = User(username_hash=f"auto_{student1.id}", username_lookup_hash=f"auto_l_{student1.id}", user_role=UserRole.STUDENT)
    db.session.add(student1_user)
    db.session.flush()
    seat1 = Seat(user_id=student1_user.id, class_id=class_row.class_id, join_code="ATTLOG1", block="PERIOD1", role="student")
    # Auto-injected Canonical User
    student2_user = User(username_hash=f"auto_{student2.id}", username_lookup_hash=f"auto_l_{student2.id}", user_role=UserRole.STUDENT)
    db.session.add(student2_user)
    db.session.flush()
    seat2 = Seat(user_id=student2_user.id, class_id=class_row.class_id, join_code="ATTLOG1", block="PERIOD3", role="student")
    db.session.add_all([seat1, seat2])
    db.session.flush()

    # Create attendance sessions with different periods
    tap1 = AttendanceSession(
        user_id=student1_user.id,
        seat_id=seat1.id,
        class_id=class_row.class_id,
        period='PERIOD1',
        started_at=datetime.now(timezone.utc),
    )
    tap2 = AttendanceSession(
        user_id=student1_user.id,
        seat_id=seat1.id,
        class_id=class_row.class_id,
        period='PERIOD2',
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=0,
    )
    tap3 = AttendanceSession(
        user_id=student2_user.id,
        seat_id=seat2.id,
        class_id=class_row.class_id,
        period='PERIOD3',
        started_at=datetime.now(timezone.utc),
    )
    db.session.add_all([tap1, tap2, tap3])
    db.session.commit()

    return {
        'admin': admin,
        'user': user,
        'students': [student1, student2],
        'tap_events': [tap1, tap2, tap3],
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
    }


def test_attendance_log_page_renders_with_periods_and_blocks(client, admin_with_data):
    """Test that the attendance log page renders with periods and blocks context."""
    admin = admin_with_data['admin']

    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = admin_with_data['user'].id
        sess['current_class_id'] = admin_with_data['class_id']
        sess['current_join_code'] = admin_with_data['join_code']
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Access the attendance log page
    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Verify page structure
    assert 'Attendance Log' in html or 'Attendance History' in html

    # Verify the page contains the filter elements
    assert 'filterStatus' in html, "Expected status filter"
    assert 'filterStartDate' in html, "Expected start date filter"


def test_attendance_log_page_with_no_data(client):
    """Test that the attendance log page renders even with no data."""
    # Create admin with no students
    admin = make_admin('testadmin2', 'TESTSECRET789')
    db.session.add(admin)
    db.session.flush()
    user = _create_user_for_admin(admin)
    db.session.commit()

    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = user.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Access the attendance log page
    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Page should render even with empty data
    assert 'Attendance Log' in html or 'Attendance History' in html
    assert 'filterStatus' in html


def test_attendance_log_tenant_scoping(client):
    """Test that admins only see periods/blocks from their own students."""
    # Create two admins
    admin1 = make_admin('admin1', 'SECRET1')
    admin2 = make_admin('admin2', 'SECRET2')
    db.session.add_all([admin1, admin2])
    db.session.flush()
    user1 = _create_user_for_admin(admin1)
    _create_user_for_admin(admin2)

    # Create class economies
    class1 = ClassEconomy(join_code="ADM1CLS", user_id=admin1.id, status="active", created_by_admin_id=admin1.id)
    class2 = ClassEconomy(join_code="ADM2CLS", user_id=admin2.id, status="active", created_by_admin_id=admin2.id)
    db.session.add_all([class1, class2])
    db.session.flush()
    db.session.add(ClassMembership(class_id=class1.class_id, join_code="ADM1CLS", admin_id=admin1.id, role="admin"))
    db.session.add(ClassMembership(class_id=class2.class_id, join_code="ADM2CLS", admin_id=admin2.id, role="admin"))

    # Create students for each admin
    salt1 = get_random_salt()
    student1 = Student(
        username_hash=hash_username('student1', salt1),
        salt=salt1,
        first_name='Student1',
        last_initial='S',
        pin_hash='hash1',
        block='ADM1PER'
    )
    salt2 = get_random_salt()
    student2 = Student(
        username_hash=hash_username('student2', salt2),
        salt=salt2,
        first_name='Student2',
        last_initial='S',
        pin_hash='hash2',
        block='ADM2PER'
    )
    db.session.add_all([student1, student2])
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(user_id=student1_user.id, teacher_id=admin1.id))
    db.session.add(StudentTeacher(user_id=student2_user.id, teacher_id=admin2.id))
    db.session.flush()

    # Create seats
    # Auto-injected Canonical User
    student1_user = User(username_hash=f"auto_{student1.id}", username_lookup_hash=f"auto_l_{student1.id}", user_role=UserRole.STUDENT)
    db.session.add(student1_user)
    db.session.flush()
    seat1 = Seat(user_id=student1_user.id, class_id=class1.class_id, join_code="ADM1CLS", block="ADM1PER", role="student")
    # Auto-injected Canonical User
    student2_user = User(username_hash=f"auto_{student2.id}", username_lookup_hash=f"auto_l_{student2.id}", user_role=UserRole.STUDENT)
    db.session.add(student2_user)
    db.session.flush()
    seat2 = Seat(user_id=student2_user.id, class_id=class2.class_id, join_code="ADM2CLS", block="ADM2PER", role="student")
    db.session.add_all([seat1, seat2])
    db.session.flush()

    # Create attendance sessions
    tap1 = AttendanceSession(
        user_id=student1_user.id,
        seat_id=seat1.id,
        class_id=class1.class_id,
        period='ADM1PER',
        started_at=datetime.now(timezone.utc),
    )
    tap2 = AttendanceSession(
        user_id=student2_user.id,
        seat_id=seat2.id,
        class_id=class2.class_id,
        period='ADM2PER',
        started_at=datetime.now(timezone.utc),
    )
    db.session.add_all([tap1, tap2])
    db.session.commit()

    # Log in as admin1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin1.id
        sess['user_id'] = user1.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Access the attendance log page
    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Verify the page renders successfully
    assert 'Attendance Log' in html or 'Attendance History' in html

    # Verify tenant isolation via the attendance history API
    with client.session_transaction() as sess:
        sess['current_class_id'] = class1.class_id
        sess['current_join_code'] = "ADM1CLS"
    api_response = client.get('/api/attendance/history')
    assert api_response.status_code == 200
    data = api_response.get_json()
    returned_periods = {r['period'] for r in data['records']}
    assert 'ADM1PER' in returned_periods, "Admin1 should see their own period"
    assert 'ADM2PER' not in returned_periods, "Admin1 should not see admin2's period"
