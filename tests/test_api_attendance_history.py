"""
Tests for the /api/attendance/history endpoint to ensure it returns attendance records.
"""
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from datetime import datetime, timezone, timedelta
from app import app, db
from app.models import AttendanceSession, AttendanceReasonCode, ClassEconomy, Seat, User
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


@pytest.fixture
def admin_with_students(client):
    """Create an admin with students and tap events for testing."""
    teacher = make_admin('testadmin')
    db.session.flush()

    class_row = create_class_scope(teacher_user=teacher, join_code="ATTN01", display_name="Attendance History Class")
    db.session.flush()

    student = make_student_identity(class_id=class_row.class_id, first_name='Test', last_name='S')
    db.session.flush()

    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_row.class_id, role="student").first()
    teacher_seat = Seat.query.filter_by(user_id=teacher.id, class_id=class_row.class_id, role="teacher").first()
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

    db.session.commit()

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


def test_attendance_history_returns_records(client, admin_with_students):
    """Test that /api/attendance/history returns attendance records for an admin's students."""
    teacher = admin_with_students['teacher']

    login_teacher(client, teacher, class_id=admin_with_students['class_id'])

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


def test_attendance_history_with_date_filters(client, admin_with_students):
    """Test that date filters work correctly with UTC timestamps."""
    teacher = admin_with_students['teacher']

    login_teacher(client, teacher, class_id=admin_with_students['class_id'])

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


def test_attendance_history_tenant_scoping(client):
    """Test that admins can only see their own students' attendance records."""
    admin1 = make_admin('admin1')
    admin2 = make_admin('admin2')
    db.session.flush()

    class1 = create_class_scope(teacher_user=admin1, join_code="ATTN-A", display_name="Attendance A")
    class2 = create_class_scope(teacher_user=admin2, join_code="ATTN-B", display_name="Attendance B")
    db.session.flush()

    teacher1 = Seat.query.filter_by(user_id=admin1.id, class_id=class1.class_id, role="teacher").first()

    student1 = make_student_identity(class_id=class1.class_id, first_name='Student', last_name='1')
    student2 = make_student_identity(class_id=class2.class_id, first_name='Student', last_name='2')

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
    db.session.commit()

    login_teacher(client, admin1, class_id=class1.class_id)

    response = client.get('/api/attendance/history')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 1, f"Admin1 should see exactly 1 record, got {data['total']}"
    assert len(data['records']) == 1


def test_attendance_history_excludes_deleted_records(client, admin_with_students):
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
    db.session.add(deleted_tap)
    db.session.commit()

    login_teacher(client, teacher, class_id=admin_with_students['class_id'])

    response = client.get('/api/attendance/history')

    assert response.status_code == 200
    data = response.get_json()

    assert data['status'] == 'success'
    assert data['total'] == 2, f"Expected 2 records (excluding deleted), got {data['total']}"
    assert len(data['records']) == 2


def test_attendance_history_dedupes_duplicate_daily_limit_tapouts(client, admin_with_students):
    """Duplicate auto tap-outs with identical daily-limit payload should render once."""
    teacher = admin_with_students['teacher']
    now_utc = datetime.now(timezone.utc)
    duplicate_ts = now_utc - timedelta(minutes=10)
    reason = "Daily limit (1.2h) reached"

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
    db.session.commit()

    login_teacher(client, teacher, class_id=admin_with_students['class_id'])

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
