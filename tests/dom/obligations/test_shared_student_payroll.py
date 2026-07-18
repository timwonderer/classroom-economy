from datetime import datetime, timedelta, timezone
from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, Seat, PayrollSettings, Transaction
from app.payroll import calculate_payroll_breakdown
from tests.helpers.classroom_initializer import initialize


def test_FEAT_PAY_001__shared_student_diff_teacher_diff_period(client):
    """
    Scenario A: Student S is in T1's class and T2's class.
    Verify T1 payroll only pays for T1 attendance.
    Verify T2 payroll only pays for T2 attendance.
    """
    class_1 = initialize("chemistry_p1", client.application)
    class_2 = initialize("biology_block_a", client.application)
    student_seed = class_1.students[0]
    seat_1 = student_seed.seat
    seat_2_row = Seat(user_id=student_seed.user.id, class_id=class_2.class_id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_2_row)
    db.session.flush()
    seat_2 = Seat.query.filter_by(user_id=student_seed.user.id, class_id=class_2.class_id, role="student").first()
    assert seat_1 is not None
    assert seat_2 is not None

    with FEATContext("FEAT-ADMN-001", idempotency_key=f"shared_payroll:settings:{class_1.class_id}:{class_2.class_id}"):
        db.session.add(PayrollSettings(class_id=class_1.class_id, pay_rate=10, is_active=True))
        db.session.add(PayrollSettings(class_id=class_2.class_id, pay_rate=10, is_active=True))
        db.session.flush()

    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-ATTN-001", idempotency_key=f"shared_payroll:attendance:{class_1.class_id}:{class_2.class_id}"):
        db.session.add(AttendanceSession(
            seat_id=seat_1.id,
            class_id=class_1.class_id,
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1),
            duration_seconds=3600,
        ))
        db.session.add(AttendanceSession(
            seat_id=seat_2.id,
            class_id=class_2.class_id,
            started_at=now - timedelta(minutes=30),
            ended_at=now,
            duration_seconds=1800,
        ))
        db.session.flush()

    s1 = calculate_payroll_breakdown(class_1.class_id, [seat_1.id], now-timedelta(days=1))
    assert seat_1.id in s1
    assert abs(float(s1[seat_1.id]) - 600.0) < 0.1

    s2 = calculate_payroll_breakdown(class_2.class_id, [seat_2.id], now-timedelta(days=1))
    assert seat_2.id in s2
    assert abs(float(s2[seat_2.id]) - 300.0) < 0.1


def test_FEAT_PAY_001__same_teacher_same_block_diff_context(client):
    """
    Scenario B: Same Teacher, Diff Join Codes (JC1, JC2).
    Verify attendance in JC1 is NOT counted for JC2.
    """
    class_1 = initialize("chemistry_p1", client.application)
    class_2 = initialize("biology_block_a", client.application)
    student_seed = class_1.students[0]
    seat_1 = student_seed.seat
    seat_2_row = Seat(user_id=student_seed.user.id, class_id=class_2.class_id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_2_row)
    db.session.flush()
    seat_2 = Seat.query.filter_by(user_id=student_seed.user.id, class_id=class_2.class_id, role="student").first()
    assert seat_1 is not None
    assert seat_2 is not None

    with FEATContext("FEAT-ADMN-001", idempotency_key=f"shared_payroll:settings:{class_1.class_id}:{class_2.class_id}:scenario_b"):
        db.session.add(PayrollSettings(class_id=class_1.class_id, pay_rate=10, is_active=True))
        db.session.add(PayrollSettings(class_id=class_2.class_id, pay_rate=10, is_active=True))
        db.session.flush()

    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-ATTN-001", idempotency_key=f"shared_payroll:attendance:{class_1.class_id}:{class_2.class_id}:scenario_b"):
        db.session.add(AttendanceSession(
            seat_id=seat_1.id,
            class_id=class_1.class_id,
            started_at=now - timedelta(hours=1),
            ended_at=now,
            duration_seconds=3600,
        ))
        db.session.flush()

    summary = calculate_payroll_breakdown(class_2.class_id, [seat_2.id], now-timedelta(days=1))
    paid_amount = summary.get(seat_2.id, 0)
    assert paid_amount == 0.0, "Attendance from JC1 context leaked into JC2 context!"


def test_DOM_CLASS_001__balance_separation_by_class_scope(client):
    """
    Verify that a student has distinct balances for different class scopes.
    """
    from app.routes.student import calculate_scoped_balances

    class_1 = initialize("chemistry_p1", client.application)
    class_2 = initialize("biology_block_a", client.application)
    student_seed = class_1.students[0]
    seat_1 = student_seed.seat
    seat_2_row = Seat(user_id=student_seed.user.id, class_id=class_2.class_id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_2_row)
    db.session.flush()
    seat_2 = Seat.query.filter_by(user_id=student_seed.user.id, class_id=class_2.class_id, role="student").first()
    assert seat_1 is not None
    assert seat_2 is not None

    with FEATContext("FEAT-LED-001", idempotency_key=f"shared_payroll:balances:{class_1.class_id}:{class_2.class_id}"):
        db.session.add(Transaction(user_id=student_seed.user.id, seat_id=seat_1.id, target_seat_id=seat_1.id, actor_seat_id=seat_1.id, mechanism="self", amount=100, account_type='checking', type='deposit', join_code='JC1',))
        db.session.add(Transaction(user_id=student_seed.user.id, seat_id=seat_1.id, target_seat_id=seat_1.id, actor_seat_id=seat_1.id, mechanism="self", amount=50, account_type='savings', type='deposit', join_code='JC1',))

        db.session.add(Transaction(user_id=student_seed.user.id, seat_id=seat_2.id, target_seat_id=seat_2.id, actor_seat_id=seat_2.id, mechanism="self", amount=200, account_type='checking', type='deposit', join_code='JC2',))
        db.session.add(Transaction(user_id=student_seed.user.id, seat_id=seat_2.id, target_seat_id=seat_2.id, actor_seat_id=seat_2.id, mechanism="self", amount=100, account_type='savings', type='deposit', join_code='JC2',))
        db.session.flush()

    chk1, sav1 = calculate_scoped_balances(seat_1.id, class_1.class_id)
    assert chk1 == 100.0
    assert sav1 == 50.0

    chk2, sav2 = calculate_scoped_balances(seat_2.id, class_2.class_id)
    assert chk2 == 200.0
    assert sav2 == 100.0
