from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import Transaction, apply_savings_interest, db


def test_apply_savings_interest_with_naive_datetimes(client, test_student):
    from unittest.mock import patch
    from app import app

    past_date = datetime.now(timezone.utc) - timedelta(days=31)
    savings_tx = Transaction(
        student_id=test_student.id,
        join_code='TEST',
        amount=100.0,
        account_type='savings',
        description='Initial savings deposit',
        timestamp=past_date,
        date_funds_available=past_date,
    )
    db.session.add(savings_tx)
    db.session.commit()

    # Mock get_current_class_context to return minimal context (uses default banking settings)
    mock_context = {
        'teacher_id': None,
        'join_code': 'TEST',
        'student_teacher_id': None
    }
    mock_context = type('MockContext', (), {'class_id': 'TEST', 'seat_id': 1})()
    
    with app.test_request_context():
        from flask import g
        g.canonical_context = mock_context
        g._auth_current_seat_cache = type('MockSeat', (), {'id': 1, 'class_id': 'TEST'})()
        
        apply_savings_interest(mock_context, test_student)

    interest_tx = (
        Transaction.query.filter_by(
            student_id=test_student.id,
            description="Monthly Savings Interest",
            account_type='savings',
        )
        .order_by(Transaction.id.desc())
        .first()
    )

    assert interest_tx is not None
    from decimal import Decimal
    # Expected: 100 * (0.045 / 12) = 0.375 -> rounds to 0.38
    assert interest_tx.amount == Decimal('0.38')


def test_dashboard_renders_recent_deposit(client, test_student):
    from app.models import Admin, StudentTeacher, Seat, IdentityProfile

    # Create a teacher and link the student
    teacher = make_admin("testteacher", "SECRET123")
    db.session.add(teacher)
    db.session.flush()

    # Create join code for the student
    join_code = "TEST123"
    test_student.join_code = join_code

    # Link student to teacher
    st = StudentTeacher(student_id=test_student.id, teacher_id=teacher.id)
    db.session.add(st)

    # Create TeacherBlock (required for dashboard context)
    tb = Seat(student_id=test_student.id, join_code=join_code, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name=test_student.display_first_name, last_name=test_student.display_last_initial))
    db.session.add(tb)

    db.session.commit()

    recent_deposit_time = datetime.now(timezone.utc) - timedelta(hours=12)
    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)

    recent_deposit = Transaction(
        student_id=test_student.id,
        join_code=join_code,
        amount=50.0,
        account_type='checking',
        description='Payroll Deposit',
        timestamp=recent_deposit_time,
        date_funds_available=recent_deposit_time,
    )
    mature_savings = Transaction(
        student_id=test_student.id,
        join_code=join_code,
        amount=200.0,
        account_type='savings',
        description='Savings Seed',
        timestamp=mature_savings_time,
        date_funds_available=mature_savings_time,
    )

    db.session.add_all([recent_deposit, mature_savings])
    db.session.commit()

    with client.session_transaction() as session:
        session['student_id'] = test_student.id
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['current_join_code'] = join_code

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    assert b"You received a deposit of" in response.data
    assert b"$50.00" in response.data

    interest_tx = Transaction.query.filter_by(
        student_id=test_student.id,
        description="Monthly Savings Interest",
        account_type='savings',
    ).first()

    assert interest_tx is None
