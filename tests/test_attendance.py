from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
from types import SimpleNamespace
import pytest
from app import db, Transaction
from app.feats.base import FEATContext
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    calculate_period_attendance,
    get_session_status,
    get_all_block_statuses
)
from app.models import AttendanceSession, ClassEconomy, SeatAttendanceState, Seat
from datetime import datetime, timedelta, timezone


def _create_class_and_student(test_suffix, first_name="Test", last_name="S", section="A"):
    """Create a teacher + class + student. Returns (class_id, student_seat)."""
    join_code = f"ATT-{test_suffix}"
    teacher = seed_canonical_admin(f"teacher_{join_code.lower()}", "s").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code, display_name=section, section=section)
    student = make_student_identity(class_id=class_row.class_id, first_name=first_name, last_name=last_name)
    db.session.commit()
    return class_row.class_id, student


def _resolve_scope(student_user_id, class_id):
    seat = Seat.query.filter_by(user_id=student_user_id, class_id=class_id).first()
    assert seat is not None
    return seat.id, class_id

def test_get_last_payroll_time(client):
    with pytest.raises(ValueError):
        get_last_payroll_time(seat_id=None, class_id=None)

    class_id, student = _create_class_and_student("payroll-A")
    seat_id, class_id = _resolve_scope(student.user_id, class_id)

    # Test with a payroll transaction
    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:get_last_payroll_time:payroll"):
        tx = Transaction(
            user_id=student.user_id,
            seat_id=seat_id,
            class_id=class_id,
            amount=10,
            type="payroll",
            timestamp=now,
        )
        db.session.add(tx)
        db.session.flush()
    
    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == now

    # Manual payments should only change the per-student anchor
    manual_time = now + timedelta(hours=1)
    manual_tx = Transaction(
        user_id=student.user_id, 
        seat_id=seat_id,
        class_id=class_id,
        amount=5, 
        type="manual_payment", 
        timestamp=manual_time)
    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:get_last_payroll_time:manual"):
        db.session.add(manual_tx)
        db.session.flush()

    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == manual_time

    # Class-scoped anchors must ignore payroll/manual payment activity from other classes
    other_class_id, other_student = _create_class_and_student("payroll-B")
    other_seat_id, other_class_id = _resolve_scope(other_student.user_id, other_class_id)
    other_join_time = manual_time + timedelta(hours=1)
    other_join_tx = Transaction(
        user_id=other_student.user_id,
        seat_id=other_seat_id,
        class_id=other_class_id,
        amount=7,
        type="payroll",
        timestamp=other_join_time,
    )
    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:get_last_payroll_time:other"):
        db.session.add(other_join_tx)
        db.session.flush()

    assert get_last_payroll_time(seat_id=other_seat_id, class_id=other_class_id) == other_join_time
    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == manual_time

def test_calculate_unpaid_attendance_seconds(client):
    class_id, student = _create_class_and_student("unpaid-A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=30)
    tap_out_time = now - timedelta(minutes=15)
    seat_id, class_id = _resolve_scope(student.user_id, class_id)

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:unpaid_seconds"):
        db.session.add(
            AttendanceSession(
                seat_id=seat_id,
                class_id=class_id,
                started_at=tap_in_time,
                ended_at=tap_out_time,
                duration_seconds=900,
            )
        )
        db.session.flush()

    last_payroll_time = now - timedelta(days=1)
    unpaid_seconds = calculate_unpaid_attendance_seconds(seat_id, class_id, last_payroll_time)

    # 15 minutes of attendance = 900 seconds
    assert unpaid_seconds == 900

def test_calculate_period_attendance(client):
    class_id, student = _create_class_and_student("period-A")
    now = datetime.now(timezone.utc)
    today = now.date()
    tap_in_time = now - timedelta(minutes=20)
    tap_out_time = now - timedelta(minutes=10)
    seat_id, class_id = _resolve_scope(student.user_id, class_id)

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:period_attendance"):
        db.session.add(
            AttendanceSession(
                seat_id=seat_id,
                class_id=class_id,
                started_at=tap_in_time,
                ended_at=tap_out_time,
                duration_seconds=600,
            )
        )
        db.session.flush()

    period_attendance = calculate_period_attendance(seat_id, class_id, today)

    # 10 minutes of attendance = 600 seconds
    assert period_attendance == 600

def test_get_session_status(client):
    class_id, student = _create_class_and_student("session-A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=5)
    seat_id, class_id = _resolve_scope(student.user_id, class_id)

    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:get_session_status"):
        session = AttendanceSession(
            seat_id=seat_id,
            class_id=class_id,
            started_at=tap_in_time,
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(
            SeatAttendanceState(
                seat_id=seat_id,
                class_id=class_id,
                is_active=True,
                open_session_id=session.id,
                last_event_at=tap_in_time,
                last_event_status="active",
                last_reason="start_work",
            )
        )
        db.session.flush()

    is_active, done, duration = get_session_status(seat_id, class_id)
    assert is_active is True
    assert done is False
    assert duration > 0

def test_get_all_block_statuses(client):
    class_id_a, student = _create_class_and_student("blocks-A", section="A")
    class_id_b, student_b = _create_class_and_student("blocks-B", section="B")

    now = datetime.now(timezone.utc)
    tap_in_time_a = now - timedelta(minutes=10)
    seat_id_a, class_id_a = _resolve_scope(student.user_id, class_id_a)
    seat_id_b, class_id_b = _resolve_scope(student_b.user_id, class_id_b)
    with FEATContext("FEAT-ATTN-001", idempotency_key="attendance:get_all_block_statuses"):
        session_a = AttendanceSession(
            seat_id=seat_id_a,
            class_id=class_id_a,
            started_at=tap_in_time_a,
        )
        db.session.add(session_a)
        db.session.flush()
        db.session.add(
            SeatAttendanceState(
                seat_id=seat_id_a,
                class_id=class_id_a,
                is_active=True,
                open_session_id=session_a.id,
                last_event_at=tap_in_time_a,
                last_event_status="active",
            )
        )
        db.session.flush()

    student_user = SimpleNamespace(id=student.user_id)  # user_id is the User pk
    statuses_a = get_all_block_statuses(student_user, class_id=class_id_a)
    assert "A" in statuses_a
    assert "B" not in statuses_a
    assert statuses_a["A"]["active"] is True
    assert statuses_a["A"]["projected_pay"] is None

    student_user_b = SimpleNamespace(id=student_b.user_id)
    statuses_b = get_all_block_statuses(student_user_b, class_id=class_id_b)
    assert "B" in statuses_b
    assert statuses_b["B"]["active"] is False
