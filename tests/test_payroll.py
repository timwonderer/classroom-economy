import pytest
from app import app, db, Student, TapEvent, Transaction
from payroll import calculate_payroll
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

def test_calculate_payroll(client):
    # Create a student
    student = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=b'salt',
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()

    # Create TapEvents to simulate attendance
    now = datetime.now(timezone.utc)
    tap_in_time = now - timedelta(minutes=60)
    tap_out_time = now - timedelta(minutes=30)

    tap_in = TapEvent(student_id=student.id, period="A", status="active", timestamp=tap_in_time)
    tap_out = TapEvent(student_id=student.id, period="A", status="inactive", timestamp=tap_out_time)
    db.session.add_all([tap_in, tap_out])
    db.session.commit()

    # Calculate payroll
    students = [student]
    last_payroll_time = now - timedelta(days=1)
    payroll_summary = calculate_payroll(students, last_payroll_time)

    # Assert the payroll amount is correct
    # 30 minutes of attendance = 1800 seconds
    # 1800 seconds * ($0.25 / 60 seconds) = $7.50
    expected_payroll = 7.50
    assert student.id in payroll_summary
    assert payroll_summary[student.id] == expected_payroll

    # Test case with no attendance
    student2 = Student(first_name="Test2", last_initial="S", block="B", salt=b'salt2', has_completed_setup=True)
    db.session.add(student2)
    db.session.commit()
    students2 = [student2]
    payroll_summary2 = calculate_payroll(students2, last_payroll_time)
    assert student2.id not in payroll_summary2