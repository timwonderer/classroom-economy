"""
Tests for the attendance log page to ensure it renders with proper context.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
from datetime import datetime, timezone
import uuid
from app import db
from app.models import Admin, AttendanceSession, ClassEconomy, Seat, User, UserRole, IdentityProfile
from app.hash_utils import hash_username, get_random_salt
from tests.helpers.canonical_session import set_canonical_context


def _create_user_for_admin(admin):
    """Return the canonical User record already linked to an admin."""
    return db.session.get(User, admin.user_id)

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
        user_id=admin.id,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Class",
        class_timezone="UTC",
    )
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
    db.session.add(teacher_seat)
    db.session.flush()
    # Create students with blocks
    seat1 = make_student_identity(block='PERIOD1', first_name='Test', last_name='T', class_id=class_row.class_id)
    seat2 = make_student_identity(block='PERIOD3', first_name='Student', last_name='S', class_id=class_row.class_id)
    student1 = seat1
    student2 = seat2

    # Create attendance sessions with different periods
    tap1 = AttendanceSession(
        seat_id=seat1.id,
        class_id=class_row.class_id,
        started_at=datetime.now(timezone.utc),
    )
    tap2 = AttendanceSession(
        seat_id=seat1.id,
        class_id=class_row.class_id,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=0,
    )
    tap3 = AttendanceSession(
        seat_id=seat2.id,
        class_id=class_row.class_id,
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
        set_canonical_context(
            sess,
            user_id=admin_with_data['user'].id,
            class_id=admin_with_data['class_id'],
            seat_id=admin_with_data['seat'].id if admin_with_data.get('seat') else admin_with_data['user'].id,
            role="teacher",
        )

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
    class_row = ClassEconomy(
        user_id=admin.id,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Empty Class",
        class_timezone="UTC",
    )
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
    db.session.add(teacher_seat)
    db.session.flush()
    db.session.commit()

    # Log in as the admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = user.id
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_row.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

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

    # Create class economies
    class1 = ClassEconomy(
        user_id=admin1.id,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Tenant 1",
        class_timezone="UTC",
    )
    class2 = ClassEconomy(
        user_id=admin2.id,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Tenant 2",
        class_timezone="UTC",
    )
    db.session.add_all([class1, class2])
    db.session.flush()
    teacher1 = Seat(user_id=user1.id, class_id=class1.class_id, role="teacher")
    teacher2 = Seat(user_id=admin2.user_id, class_id=class2.class_id, role="teacher")
    db.session.add_all([teacher1, teacher2])
    db.session.flush()
    # Create students for each admin
    student1 = make_student_identity(block='ADM1PER', first_name='Student1', last_name='S')
    student2 = make_student_identity(block='ADM2PER', first_name='Student2', last_name='S')

    # Create seats
    student1_user = User(username_hash=f"auto_{student1.id}", username_lookup_hash=f"auto_l_{student1.id}", user_role=UserRole.STUDENT)
    db.session.add(student1_user)
    db.session.flush()
    seat1 = Seat(user_id=student1_user.id, class_id=class1.class_id, block="ADM1PER", role="student")
    # Auto-injected Canonical User
    student2_user = User(username_hash=f"auto_{student2.id}", username_lookup_hash=f"auto_l_{student2.id}", user_role=UserRole.STUDENT)
    db.session.add(student2_user)
    db.session.flush()
    seat2 = Seat(user_id=student2_user.id, class_id=class2.class_id, block="ADM2PER", role="student")
    db.session.add_all([seat1, seat2])
    db.session.flush()

    # Create attendance sessions
    tap1 = AttendanceSession(
        seat_id=seat1.id,
        class_id=class1.class_id,
        started_at=datetime.now(timezone.utc),
    )
    tap2 = AttendanceSession(
        seat_id=seat2.id,
        class_id=class2.class_id,
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
        set_canonical_context(
            sess,
            user_id=user1.id,
            class_id=class1.class_id,
            seat_id=teacher1.id,
            role="teacher",
        )

    # Access the attendance log page
    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Verify the page renders successfully
    assert 'Attendance Log' in html or 'Attendance History' in html

    # Verify tenant isolation via the attendance history API
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user1.id,
            class_id=class1.class_id,
            seat_id=teacher1.id,
            role="teacher",
        )
    api_response = client.get('/api/attendance/history')
    assert api_response.status_code == 200
    data = api_response.get_json()
    returned_periods = {r['student_block'] for r in data['records']}
    assert 'ADM1PER' in returned_periods, "Admin1 should see their own period"
    assert 'ADM2PER' not in returned_periods, "Admin1 should not see admin2's period"
