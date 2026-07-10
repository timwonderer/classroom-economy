"""
Tests for the attendance log page to ensure it renders with proper context.
"""
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from datetime import datetime, timezone
import uuid
from app import db
from app.models import AttendanceSession, ClassEconomy, Seat, User
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


@pytest.fixture
def admin_with_data(client):
    """Create an admin with students and tap events."""
    teacher = make_admin('testadmin')
    db.session.flush()

    class_row = create_class_scope(
        teacher_user=teacher,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Class",
    )
    db.session.flush()

    teacher_seat = Seat.query.filter_by(user_id=teacher.id, class_id=class_row.class_id, role="teacher").first()

    seat1 = make_student_identity(class_id=class_row.class_id, first_name='Test', last_name='T')
    seat2 = make_student_identity(class_id=class_row.class_id, first_name='Student', last_name='S')

    tap1 = AttendanceSession(seat_id=seat1.id, class_id=class_row.class_id, started_at=datetime.now(timezone.utc))
    tap2 = AttendanceSession(
        seat_id=seat1.id,
        class_id=class_row.class_id,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=0,
    )
    tap3 = AttendanceSession(seat_id=seat2.id, class_id=class_row.class_id, started_at=datetime.now(timezone.utc))
    db.session.add_all([tap1, tap2, tap3])
    db.session.commit()

    return {
        'teacher': teacher,
        'user': db.session.get(User, teacher.id),
        'teacher_seat': teacher_seat,
        'students': [seat1, seat2],
        'tap_events': [tap1, tap2, tap3],
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
    }


def test_attendance_log_page_renders_with_periods_and_blocks(client, admin_with_data):
    """Test that the attendance log page renders with periods and blocks context."""
    teacher = admin_with_data['teacher']

    login_teacher(client, teacher, class_id=admin_with_data['class_id'])

    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html
    assert 'filterStatus' in html, "Expected status filter"
    assert 'filterStartDate' in html, "Expected start date filter"


def test_attendance_log_page_with_no_data(client):
    """Test that the attendance log page renders even with no data."""
    teacher = make_admin('testadmin2')
    db.session.flush()

    class_row = create_class_scope(
        teacher_user=teacher,
        join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}",
        display_name="Attendance Empty Class",
    )
    db.session.flush()
    db.session.commit()

    login_teacher(client, teacher, class_id=class_row.class_id)

    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html
    assert 'filterStatus' in html


def test_attendance_log_tenant_scoping(client):
    """Test that admins only see periods/blocks from their own students."""
    admin1 = make_admin('admin1')
    admin2 = make_admin('admin2')
    db.session.flush()

    class1 = create_class_scope(teacher_user=admin1, join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}", display_name="Attendance Tenant 1")
    class2 = create_class_scope(teacher_user=admin2, join_code=f"ATTEND-{uuid.uuid4().hex[:8].upper()}", display_name="Attendance Tenant 2")
    db.session.flush()

    teacher1 = Seat.query.filter_by(user_id=admin1.id, class_id=class1.class_id, role="teacher").first()

    student1 = make_student_identity(class_id=class1.class_id, first_name='Student1', last_name='S')
    student2 = make_student_identity(class_id=class2.class_id, first_name='Student2', last_name='S')
    db.session.flush()
    seat1 = Seat.query.filter_by(user_id=student1.user_id, class_id=class1.class_id, role="student").first()
    seat2 = Seat.query.filter_by(user_id=student2.user_id, class_id=class2.class_id, role="student").first()

    tap1 = AttendanceSession(seat_id=seat1.id, class_id=class1.class_id, started_at=datetime.now(timezone.utc))
    tap2 = AttendanceSession(seat_id=seat2.id, class_id=class2.class_id, started_at=datetime.now(timezone.utc))
    db.session.add_all([tap1, tap2])
    db.session.commit()

    login_teacher(client, admin1, class_id=class1.class_id)

    response = client.get('/admin/attendance-log')

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html

    api_response = client.get('/api/attendance/history')
    assert api_response.status_code == 200
    data = api_response.get_json()
    returned_periods = {r['student_block'] for r in data['records']}
    assert 'ADM2PER' not in returned_periods, "Admin1 should not see admin2's period"
