from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
from app import db, Transaction
from app.models import Student
from app.attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    calculate_period_attendance,
    get_session_status,
    get_all_block_statuses
)
from app.models import AttendanceSession, ClassEconomy, IdentityProfile, SeatAttendanceState
from datetime import datetime, timedelta, timezone


def _attach_student_to_class(student, join_code="ATTEND1", block="A"):
    from app.models import Admin, IdentityProfile, StudentTeacher, User, Seat, UserRole
    from tests.helpers.class_scope import create_class_scope
    from app.hash_utils import hash_username_lookup

    teacher = make_admin(f"teacher_{join_code}_{student.id or 'new'}", "s")
    db.session.add(teacher)
    db.session.flush()

    admin_user = User(
        user_role=UserRole.TEACHER,
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        password_hash="pw",
    )
    db.session.add(admin_user)
    db.session.flush()

    class_economy = create_class_scope(
        teacher=teacher,
        join_code=join_code,
        student=student,
        block=block,
        display_name=block,
        create_seat=False,
    )
    db.session.flush()

    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    
    student_username = f"user_{join_code}_{student.id}"
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username_lookup(student_username),
        username_lookup_hash=hash_username_lookup(student_username),
        password_hash="hash",
    )
    db.session.add(user)
    db.session.flush()
    db.session.add(
        Seat(
            user_id=user.id,
            class_id=class_economy.class_id,
            join_code=join_code,
            block=block,
            block_identifier=block,
            role="student",
            claimed_at=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    return join_code


def _resolve_scope(student_id, join_code):
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    assert class_row is not None
    seat = db.session.query(Seat).filter(Seat.user_id == student_id, Seat.class_id == class_row.class_id).first()
    seat_id = seat.id if seat else None
    assert seat_id is not None
    return seat_id, class_row.class_id

def test_get_last_payroll_time(client):
    with pytest.raises(ValueError):
        get_last_payroll_time(seat_id=None, class_id=None)

    # Create a student first
    student = make_student_identity(block="A", first_name="Test", last_name="S")
    db.session.commit()
    join_code = _attach_student_to_class(student, join_code="PAYROLL1", block="A")
    seat_id, class_id = _resolve_scope(student.id, join_code)

    # Test with a payroll transaction
    now = datetime.now(timezone.utc)
    # V2 requires seat_id/class_id, but compatibility layer supports join_code
    tx = Transaction(
        user_id=student_user.id, 
        seat_id=seat_id,
        class_id=class_id,
        amount=10, 
        type="payroll", 
        timestamp=now,
        join_code=join_code
    )
    db.session.add(tx)
    db.session.commit()
    
    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == now

    # Manual payments should only change the per-student anchor
    manual_time = now + timedelta(hours=1)
    manual_tx = Transaction(
        user_id=student_user.id, 
        seat_id=seat_id,
        class_id=class_id,
        amount=5, 
        type="manual_payment", 
        timestamp=manual_time,
        join_code=join_code
    )
    db.session.add(manual_tx)
    db.session.commit()

    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == manual_time

    # Class-scoped anchors must ignore payroll/manual payment activity from other classes
    other_join = _attach_student_to_class(student, join_code="OTHER", block="B")
    other_seat_id, other_class_id = _resolve_scope(student.id, other_join)
    other_join_time = manual_time + timedelta(hours=1)
    other_join_tx = Transaction(
        user_id=student_user.id,
        seat_id=other_seat_id,
        class_id=other_class_id,
        amount=7,
        type="payroll",
        timestamp=other_join_time,
        join_code=other_join,
    )
    db.session.add(other_join_tx)
    db.session.commit()

    assert get_last_payroll_time(seat_id=other_seat_id, class_id=other_class_id) == other_join_time
    assert get_last_payroll_time(seat_id=seat_id, class_id=class_id) == manual_time

def test_calculate_unpaid_attendance_seconds(client):
    student = make_student_identity(block="A", first_name="Test", last_name="S")
    db.session.commit()
    join_code = _attach_student_to_class(student, join_code="ATTEND2", block="A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=30)
    tap_out_time = now - timedelta(minutes=15)
    seat_id, class_id = _resolve_scope(student.id, join_code)

    db.session.add(
        AttendanceSession(
            seat_id=seat_id,
            class_id=class_id,
            started_at=tap_in_time,
            ended_at=tap_out_time,
            duration_seconds=900,
        )
    )
    db.session.commit()

    last_payroll_time = now - timedelta(days=1)
    unpaid_seconds = calculate_unpaid_attendance_seconds(seat_id, class_id, last_payroll_time)

    # 15 minutes of attendance = 900 seconds
    assert unpaid_seconds == 900

def test_calculate_period_attendance(client):
    student = make_student_identity(block="A", first_name="Test", last_name="S")
    db.session.commit()

    join_code = _attach_student_to_class(student, join_code="ATTEND6", block="A")
    now = datetime.now(timezone.utc)
    today = now.date()
    tap_in_time = now - timedelta(minutes=20)
    tap_out_time = now - timedelta(minutes=10)
    seat_id, class_id = _resolve_scope(student.id, join_code)

    db.session.add(
        AttendanceSession(
            seat_id=seat_id,
            class_id=class_id,
            started_at=tap_in_time,
            ended_at=tap_out_time,
            duration_seconds=600,
        )
    )
    db.session.commit()

    period_attendance = calculate_period_attendance(seat_id, class_id, today)

    # 10 minutes of attendance = 600 seconds
    assert period_attendance == 600

def test_get_session_status(client):
    student = make_student_identity(block="A", first_name="Test", last_name="S")
    db.session.commit()
    join_code = _attach_student_to_class(student, join_code="ATTEND3", block="A")

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=5)
    seat_id, class_id = _resolve_scope(student.id, join_code)

    session = AttendanceSession(
        seat_id=seat_id,
        class_id=class_id,
        started_at=tap_in_time,
    )
    db.session.add(session)
    db.session.flush()
    db.session.add(
        SeatAttendanceState(
            user_id=student_user.id,
            seat_id=seat_id,
            class_id=class_id,
            is_active=True,
            open_session_id=session.id,
            last_event_at=tap_in_time,
            last_event_status="active",
            last_reason="start_work",
        )
    )
    db.session.commit()

    is_active, done, duration = get_session_status(seat_id, class_id)
    assert is_active is True
    assert done is False
    assert duration > 0

def test_get_all_block_statuses(client):
    student = make_student_identity(block="A,B", first_name="Test", last_name="S")
    db.session.commit()
    join_code_a = _attach_student_to_class(student, join_code="ATTEND4", block="A")
    join_code_b = _attach_student_to_class(student, join_code="ATTEND5", block="B")

    now = datetime.now(timezone.utc)
    tap_in_time_a = now - timedelta(minutes=10)
    seat_id_a, class_id_a = _resolve_scope(student.id, join_code_a)
    session_a = AttendanceSession(
        seat_id=seat_id_a,
        class_id=class_id_a,
        started_at=tap_in_time_a,
    )
    db.session.add(session_a)
    db.session.flush()
    db.session.add(
        SeatAttendanceState(
            user_id=student_user.id,
            seat_id=seat_id_a,
            class_id=class_id_a,
            is_active=True,
            open_session_id=session_a.id,
            last_event_at=tap_in_time_a,
            last_event_status="active",
        )
    )
    db.session.commit()

    statuses_a = get_all_block_statuses(student, class_id=class_id_a)
    assert "A" in statuses_a
    assert "B" not in statuses_a
    assert statuses_a["A"]["active"] is True
    assert statuses_a["A"]["projected_pay"] is None

    _, class_id_b = _resolve_scope(student.id, join_code_b)
    statuses_b = get_all_block_statuses(student, class_id=class_id_b)
    assert "B" in statuses_b
    assert statuses_b["B"]["active"] is False
