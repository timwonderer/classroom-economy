"""
Tests for the attendance log page to ensure it renders with proper context.
"""
from datetime import datetime, timezone

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, Seat, User
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.dom.identity.helpers import admin_get_attendance_log, api_get_attendance_history


@pytest.fixture
def admin_with_data(client):
    """Create an admin with students and tap events."""
    classroom = initialize("chemistry_p1", client.application)
    teacher = classroom.teacher_user
    teacher_seat = classroom.teacher_seat
    seat1 = classroom.students[0].seat
    seat2 = classroom.students[1].seat

    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_log_page:admin_data"):
        tap1 = AttendanceSession(target_seat_id=seat1.id, class_id=classroom.class_id, target_user_id=seat1.user_id, actor_seat_id=teacher_seat.id, reason_code="tap_in", timestamp=datetime.now(timezone.utc))
        tap2 = AttendanceSession(target_seat_id=seat1.id, class_id=classroom.class_id, target_user_id=seat1.user_id, actor_seat_id=teacher_seat.id, reason_code="tap_out", status="completed", timestamp=datetime.now(timezone.utc))
        tap3 = AttendanceSession(target_seat_id=seat2.id, class_id=classroom.class_id, target_user_id=seat2.user_id, actor_seat_id=teacher_seat.id, reason_code="tap_in", timestamp=datetime.now(timezone.utc))
        db.session.add_all([tap1, tap2, tap3])
        db.session.flush()

    return {
        'teacher': teacher,
        'user': db.session.get(User, teacher.id),
        'teacher_seat': teacher_seat,
        'students': [seat1, seat2],
        'tap_events': [tap1, tap2, tap3],
        'class_id': classroom.class_id,
        'join_code': classroom.join_code,
    }


def test_DOM_IDEN_006__attendance_log_page_renders_with_periods_and_blocks(client, admin_with_data):
    """Test that the attendance log page renders with periods and blocks context."""
    teacher = admin_with_data['teacher']

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = admin_get_attendance_log(client)

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html
    assert 'filterStatus' in html, "Expected status filter"
    assert 'filterStartDate' in html, "Expected start date filter"


def test_DOM_IDEN_006__attendance_log_page_with_no_data(client):
    """Test that the attendance log page renders even with no data."""
    classroom = initialize("ap_csp_p3", client.application)
    initialize_as_teacher("ap_csp_p3", client, client.application)

    response = admin_get_attendance_log(client)

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html
    assert 'filterStatus' in html


def test_DOM_IDEN_006__attendance_log_tenant_scoping(client):
    """Test that admins only see periods/blocks from their own students."""
    class1 = initialize_as_teacher("chemistry_p1", client, client.application)
    class2 = initialize("biology_block_a", client.application)
    admin1 = class1.teacher_user
    admin2 = class2.teacher_user
    seat1 = class1.students[0].seat
    seat2 = class2.students[0].seat

    teacher_seat1 = Seat.query.filter_by(class_id=class1.class_id, role="teacher").first()
    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_log_page:tenant_scoping"):
        tap1 = AttendanceSession(target_seat_id=seat1.id, class_id=class1.class_id, target_user_id=seat1.user_id, actor_seat_id=teacher_seat1.id, reason_code="tap_in", timestamp=datetime.now(timezone.utc))
        tap2 = AttendanceSession(target_seat_id=seat2.id, class_id=class2.class_id, target_user_id=seat2.user_id, actor_seat_id=seat2.id, reason_code="tap_in", timestamp=datetime.now(timezone.utc))
        db.session.add_all([tap1, tap2])
        db.session.flush()

    response = admin_get_attendance_log(client)

    assert response.status_code == 200
    html = response.data.decode('utf-8')

    assert 'Attendance Log' in html or 'Attendance History' in html

    api_response = api_get_attendance_history(client)
    assert api_response.status_code == 200
    data = api_response.get_json()
    returned_periods = {r['period'] for r in data['records']}
    assert 'Period 1' in returned_periods, "Admin1 should see their own period"
    assert 'Block A' not in returned_periods, "Admin1 should not see admin2's period"
