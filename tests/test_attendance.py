import pytest
from app import app, db, Student, TapEvent, Transaction
from attendance import (
    get_last_payroll_time,
    calculate_unpaid_attendance_seconds,
    calculate_period_attendance,
    get_session_status,
    get_all_block_statuses
)
from datetime import datetime, timedelta, timezone

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_get_last_payroll_time(client):
    # Test with no payroll transactions
    assert get_last_payroll_time() is None

    # Test with a payroll transaction
    now = datetime.now(timezone.utc)
    tx = Transaction(student_id=1, amount=10, type="payroll", timestamp=now)
    db.session.add(tx)
    db.session.commit()
    assert get_last_payroll_time() == now

def test_calculate_unpaid_attendance_seconds(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=30)
    tap_out_time = now - timedelta(minutes=15)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    last_payroll_time = now - timedelta(days=1)
    unpaid_seconds = calculate_unpaid_attendance_seconds(student.id, "A", last_payroll_time)

    # 15 minutes of attendance = 900 seconds
    assert unpaid_seconds == 900

def test_calculate_period_attendance(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    now = datetime.now(timezone.utc)
    today = now.date()
    tap_in_time = now - timedelta(minutes=20)
    tap_out_time = now - timedelta(minutes=10)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    period_attendance = calculate_period_attendance(student.id, "A", today)

    # 10 minutes of attendance = 600 seconds
    assert period_attendance == 600

def test_get_session_status(client):
    student = Student(first_name="Test", last_initial="S", block="A", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=5)
    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time)
    db.session.add(tap_in)
    db.session.commit()

    is_active, done, duration = get_session_status(student.id, "A")
    assert is_active is True
    assert done is False
    assert duration > 0

def test_get_all_block_statuses(client):
    student = Student(first_name="Test", last_initial="S", block="A,B", salt=b'salt', has_completed_setup=True)
    db.session.add(student)
    db.session.commit()

    now = datetime.now(timezone.utc)
    tap_in_time_a = now - timedelta(minutes=10)
    tap_in_a = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time_a)
    db.session.add(tap_in_a)
    db.session.commit()

    statuses = get_all_block_statuses(student)
    assert "A" in statuses
    assert "B" in statuses
    assert statuses["A"]["active"] is True
    assert statuses["B"]["active"] is False
    assert statuses["A"]["projected_pay"] > 0
    assert statuses["B"]["projected_pay"] == 0

def test_unpaid_seconds_new_student_after_payroll(client):
    """
    Simulates the bug scenario:
    1. A legacy student has work history.
    2. A payroll is run.
    3. A new student taps in for the first time.
    4. The new student's unpaid time should be near zero, not affected by legacy data.
    """
    # 1. Create legacy student and their work history
    legacy_student = Student(id=1, first_name="Legacy", last_initial="L", block="A", salt=b'salt1', has_completed_setup=True)
    db.session.add(legacy_student)
    db.session.commit()

    time1 = datetime.now(timezone.utc) - timedelta(hours=2)
    time2 = datetime.now(timezone.utc) - timedelta(hours=1)
    db.session.add(TapEvent(student_id=legacy_student.id, period="A", status="active", timestamp=time1))
    db.session.add(TapEvent(student_id=legacy_student.id, period="A", status="inactive", timestamp=time2))
    db.session.commit()

    # 2. Define a payroll time after the legacy student's work
    last_payroll_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    # 3. Create a new student with no history
    new_student = Student(id=2, first_name="New", last_initial="N", block="C", salt=b'salt2', has_completed_setup=True)
    db.session.add(new_student)
    db.session.commit()

    # 4. New student taps in *after* the payroll time
    tap_in_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.session.add(TapEvent(student_id=new_student.id, period="C", status="active", timestamp=tap_in_time))
    db.session.commit()

    # 5. Calculate unpaid seconds for the new, currently active student
    unpaid_seconds = calculate_unpaid_attendance_seconds(new_student.id, "C", last_payroll_time)

    # 6. Assert the time is small (around 10s), not a large number of hours
    assert unpaid_seconds < 60  # Should be around 10 seconds, definitely less than a minute