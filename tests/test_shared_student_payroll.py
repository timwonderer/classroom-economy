
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import uuid
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Admin, AttendanceSession, Seat, IdentityProfile, Student, StudentTeacher, PayrollSettings, Transaction
from app.payroll import calculate_payroll_breakdown
from tests.helpers.class_scope import create_class_scope


def test_shared_student_diff_teacher_diff_period(client):
    """
    Scenario A: Student S is in T1's 'Period 1' and T2's 'Period 2'.
    Verify T1 payroll only pays for Period 1 attendance.
    Verify T2 payroll only pays for Period 2 attendance.
    """
    # 1. Setup
    t1 = make_admin(f"t1_{uuid.uuid4().hex[:8]}", 's')
    t2 = make_admin(f"t2_{uuid.uuid4().hex[:8]}", 's')
    db.session.add_all([t1, t2])
    db.session.commit()

    profile_a = IdentityProfile(profile_type='student', first_name='ScenarioA', last_name='S')
    db.session.add(profile_a)
    db.session.flush()
    student = Student(identity_profile=profile_a, block="P1,P2", salt=b's')
    db.session.add(student)
    db.session.commit()

    # Links & canonical class scopes
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=t1.id))
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=t2.id))
    class_1 = create_class_scope(
        teacher=t1,
        join_code="JC1",
        student=student,
        block="P1",
        display_name="T1-P1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_2 = create_class_scope(
        teacher=t2,
        join_code="JC2",
        student=student,
        block="P2",
        display_name="T2-P2",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()
    seat_1 = Seat.query.filter_by(student_id=student.id, class_id=class_1.class_id).first()
    seat_2 = Seat.query.filter_by(student_id=student.id, class_id=class_2.class_id).first()
    assert seat_1 is not None
    assert seat_2 is not None
    
    # Settings: Both pay $10/hr ($600/60min)
    db.session.add(PayrollSettings(class_id=class_1.class_id, pay_rate=10, is_active=True))
    db.session.add(PayrollSettings(class_id=class_2.class_id, pay_rate=10, is_active=True))
    db.session.commit()

    # 2. Attendance sessions
    now = datetime.now(timezone.utc)
    db.session.add(AttendanceSession(
        student_id=student.id,
        seat_id=seat_1.id,
        class_id=class_1.class_id,
        period="P1",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        duration_seconds=3600,
    ))
    db.session.add(AttendanceSession(
        student_id=student.id,
        seat_id=seat_2.id,
        class_id=class_2.class_id,
        period="P2",
        started_at=now - timedelta(minutes=30),
        ended_at=now,
        duration_seconds=1800,
    ))
    db.session.commit()

    # 3. Pay T1
    # Should pay for 60 mins ($600)
    # Should NOT pay for 30 mins from Period 2
    s1 = calculate_payroll_breakdown(class_1.class_id, [seat_1.id], now-timedelta(days=1))
    assert seat_1.id in s1
    assert abs(float(s1[seat_1.id]) - 600.0) < 0.1

    # 4. Pay T2
    # Should pay for 30 mins ($300)
    # Should NOT pay for Period 1
    s2 = calculate_payroll_breakdown(class_2.class_id, [seat_2.id], now-timedelta(days=1))
    assert seat_2.id in s2
    assert abs(float(s2[seat_2.id]) - 300.0) < 0.1


def test_same_teacher_same_block_diff_context(client):
    """
    Scenario B: Same Teacher, Same Block Name ("PERIOD 1"), Diff Join Codes (JC1, JC2).
    A "Collision" within the same teacher's scope.
    Verify attendance in JC1 is NOT counted for JC2.
    """
    # 1. Setup
    t1 = make_admin(f"t1_{uuid.uuid4().hex[:8]}", 's')
    db.session.add(t1)
    db.session.commit()

    profile_b = IdentityProfile(profile_type='student', first_name='ScenarioB', last_name='S')
    db.session.add(profile_b)
    db.session.flush()
    student = Student(identity_profile=profile_b, block="P1", salt=b's')
    db.session.add(student)
    db.session.commit()

    # Links & canonical class scopes
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=t1.id))
    class_1 = create_class_scope(
        teacher=t1,
        join_code="JC1",
        student=student,
        block="P1",
        display_name="P1-JC1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_2 = create_class_scope(
        teacher=t1,
        join_code="JC2",
        student=student,
        block="P1",
        display_name="P1-JC2",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()
    seat_1 = Seat.query.filter_by(student_id=student.id, class_id=class_1.class_id).first()
    seat_2 = Seat.query.filter_by(student_id=student.id, class_id=class_2.class_id).first()
    assert seat_1 is not None
    assert seat_2 is not None
    
    # Settings: class-scoped and equal across both classes.
    db.session.add(PayrollSettings(class_id=class_1.class_id, pay_rate=10, is_active=True))
    db.session.add(PayrollSettings(class_id=class_2.class_id, pay_rate=10, is_active=True))
    db.session.commit()

    # 2. Attendance in JC1 only.
    now = datetime.now(timezone.utc)
    db.session.add(AttendanceSession(
        student_id=student.id,
        seat_id=seat_1.id,
        class_id=class_1.class_id,
        period="P1",
        started_at=now - timedelta(hours=1),
        ended_at=now,
        duration_seconds=3600,
    ))
    db.session.commit()

    # 3. Pay T1 for JC2 context to verify no leakage from JC1
    summary = calculate_payroll_breakdown(class_2.class_id, [seat_2.id], now-timedelta(days=1))

    paid_amount = summary.get(seat_2.id, 0)
    assert paid_amount == 0.0, "Attendance from JC1 context leaked into JC2 context!"


def test_balance_separation_by_join_code(client):
    """
    Verify that a student has distinct balances for different join codes,
    representing different class contexts.
    """
    from app.models import Transaction, Admin
    from app.routes.student import calculate_scoped_balances

    # 1. Setup Student & Teacher
    t1 = make_admin(f"t1_{uuid.uuid4().hex[:8]}", 'secret')
    db.session.add(t1)
    db.session.commit()

    profile_bal = IdentityProfile(profile_type='student', first_name='BalanceTest', last_name='B')
    db.session.add(profile_bal)
    db.session.flush()
    student = Student(identity_profile=profile_bal, block="P1", salt=b'salt')
    db.session.add(student)
    db.session.flush()
    create_class_scope(
        teacher=t1,
        join_code="JC1",
        student=student,
        block="P1",
        display_name="P1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    create_class_scope(
        teacher=t1,
        join_code="JC2",
        student=student,
        block="P1",
        display_name="P1",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()
    seat_1 = Seat.query.filter_by(student_id=student.id, join_code='JC1').first()
    seat_2 = Seat.query.filter_by(student_id=student.id, join_code='JC2').first()
    assert seat_1 is not None
    assert seat_2 is not None

    # 2. Add Transactions for JC1
    # Checking: +100
    # Savings: +50
    db.session.add(Transaction(student_id=student.id, seat_id=seat_1.id, amount=100, account_type='checking', type='deposit', join_code='JC1', teacher_id=t1.id))
    db.session.add(Transaction(student_id=student.id, seat_id=seat_1.id, amount=50, account_type='savings', type='deposit', join_code='JC1', teacher_id=t1.id))
    
    # 3. Add Transactions for JC2
    # Checking: +200
    # Savings: +100
    db.session.add(Transaction(student_id=student.id, seat_id=seat_2.id, amount=200, account_type='checking', type='deposit', join_code='JC2', teacher_id=t1.id))
    db.session.add(Transaction(student_id=student.id, seat_id=seat_2.id, amount=100, account_type='savings', type='deposit', join_code='JC2', teacher_id=t1.id))
    
    db.session.commit()

    # 4. Verify Context for JC1
    # Should ignore JC2 transactions
    chk1, sav1 = calculate_scoped_balances(student, join_code='JC1', teacher_id=t1.id)
    assert chk1 == 100.0
    assert sav1 == 50.0

    # 5. Verify Context for JC2
    # Should ignore JC1 transactions
    chk2, sav2 = calculate_scoped_balances(student, join_code='JC2', teacher_id=t1.id)
    assert chk2 == 200.0
    assert sav2 == 100.0
