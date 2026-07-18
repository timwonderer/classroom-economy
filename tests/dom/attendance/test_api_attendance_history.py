"""
Tests for the /api/attendance/history endpoint to ensure it returns attendance records.
"""
from datetime import datetime, timezone, timedelta

import pytest

from app import app, db
from app.feats.base import FEATContext
from app.models import AttendanceReasonCode, AttendanceSession, Seat, User
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


@pytest.fixture
def admin_with_students(client):
    """Create an admin with students and tap events for testing."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_history:admin_setup"):
        classroom = initialize("chemistry_p1", app)
        teacher = classroom.teacher_user
        class_row = classroom.economy
        student = classroom.students[0].user
        seat = classroom.students[0].seat
        teacher_seat = classroom.teacher_seat
        now_utc = datetime.now(timezone.utc)

        tap_in = AttendanceSession(
            seat_id=seat.id,
            class_id=class_row.class_id,
            started_at=now_utc - timedelta(hours=1),
        )
        db.session.add(tap_in)

        tap_out = AttendanceSession(
            seat_id=seat.id,
            class_id=class_row.class_id,
            started_at=now_utc - timedelta(minutes=30),
            ended_at=now_utc - timedelta(minutes=30),
            duration_seconds=0,
            end_reason='done for the day',
        )
        db.session.add(tap_out)
        db.session.flush()

    return {
        'teacher': teacher,
        'user': db.session.get(User, teacher.id),
        'student': student,
        'seat': seat,
        'teacher_seat': teacher_seat,
        'class_id': class_row.class_id,
        'join_code': class_row.join_code,
        'tap_events': [tap_in, tap_out]
    }


def test_DOM_ATT_001__attendance_history_returns_records(client, admin_with_students):
    """Test that /api/attendance/history returns attendance records for an admin's students."""
    teacher = admin_with_students['teacher']

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/attendance/history')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] > 0, "Expected at least one attendance record"
    assert len(data['records']) > 0, "Expected records array to have at least one item"

    record = data['records'][0]
    assert 'student_name' in record
    assert 'period' in record
    assert 'status' in record
    assert 'timestamp' in record
    assert record['timestamp'] is not None
    assert record['timestamp'].endswith('Z'), "Timestamp should end with 'Z' for UTC"


def test_DOM_ATT_001__attendance_history_with_date_filters(client, admin_with_students):
    """Test that date filters work correctly with UTC timestamps."""
    teacher = admin_with_students['teacher']

    initialize_as_teacher("chemistry_p1", client, client.application)

    event_ts = admin_with_students['tap_events'][0].started_at
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)
    else:
        event_ts = event_ts.astimezone(timezone.utc)
    today_str = event_ts.date().strftime('%Y-%m-%d')

    response = client.get(f'/api/attendance/history?start_date={today_str}&end_date={today_str}')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] > 0, "Expected records when filtering by today's date"
    assert len(data['records']) > 0


def test_DOM_ATT_001__attendance_history_tenant_scoping(client):
    """Test that admins can only see their own students' attendance records."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_history:tenant_scoping"):
        class1 = initialize("chemistry_p1", app)
        class2 = initialize("biology_block_a")
        teacher1 = class1.teacher_seat
        student1 = class1.students[0].seat
        student2 = class2.students[0].seat

        now_utc = datetime.now(timezone.utc)

        tap1 = AttendanceSession(
            seat_id=student1.id,
            class_id=class1.class_id,
            started_at=now_utc,
        )
        tap2 = AttendanceSession(
            seat_id=student2.id,
            class_id=class2.class_id,
            started_at=now_utc,
        )
        db.session.add_all([tap1, tap2])
        db.session.flush()

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/attendance/history')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 1, f"Admin1 should see exactly 1 record, got {data['total']}"
    assert len(data['records']) == 1


def test_DOM_ATT_001__attendance_history_excludes_deleted_records(client, admin_with_students):
    """Test that deleted tap events do not appear in attendance history."""
    teacher = admin_with_students['teacher']
    now_utc = datetime.now(timezone.utc)
    deleted_tap = AttendanceSession(
        seat_id=admin_with_students['seat'].id,
        class_id=admin_with_students['class_id'],
        started_at=now_utc - timedelta(minutes=15),
        is_deleted=True,
        deleted_at=now_utc - timedelta(minutes=5),
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_history:deleted_record"):
        db.session.add(deleted_tap)
        db.session.flush()

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/attendance/history')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 2, f"Expected 2 records (excluding deleted), got {data['total']}"
    assert len(data['records']) == 2


def test_DOM_ATT_001__attendance_history_dedupes_duplicate_daily_limit_tapouts(client, admin_with_students):
    """Duplicate auto tap-outs with identical daily-limit payload should render once."""
    teacher = admin_with_students['teacher']
    now_utc = datetime.now(timezone.utc)
    duplicate_ts = now_utc - timedelta(minutes=10)
    reason = "Daily limit (1.2h) reached"

    with FEATContext("FEAT-IDEN-001", idempotency_key="attendance_history:duplicate_daily_limit"):
        db.session.add(AttendanceSession(
            seat_id=admin_with_students['seat'].id,
            class_id=admin_with_students['class_id'],
            started_at=duplicate_ts,
            ended_at=duplicate_ts,
            duration_seconds=0,
            end_reason=reason,
            end_reason_code=AttendanceReasonCode.DAILY_LIMIT,
        ))
        db.session.add(AttendanceSession(
            seat_id=admin_with_students['seat'].id,
            class_id=admin_with_students['class_id'],
            started_at=duplicate_ts,
            ended_at=duplicate_ts,
            duration_seconds=0,
            end_reason=reason,
            end_reason_code=AttendanceReasonCode.DAILY_LIMIT,
        ))
        db.session.flush()

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/attendance/history')
    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 3  # tap-in + existing tap-out + deduped daily-limit tap-out
    daily_limit_rows = [
        record for record in data['records']
        if record['status'] == 'inactive' and record.get('reason') == reason
    ]
    assert len(daily_limit_rows) == 1
