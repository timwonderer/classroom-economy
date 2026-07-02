from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import Transaction, apply_savings_interest, db
from tests.helpers.canonical_session import set_canonical_context


def test_apply_savings_interest_with_naive_datetimes(client, test_student):
    from unittest.mock import patch
    from app import app

    past_date = datetime.now(timezone.utc) - timedelta(days=31)
    savings_tx = Transaction(
        user_id=test_student.user_id,
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
    with app.test_request_context():
        with patch('app.routes.student.get_current_class_context', return_value=mock_context):
            apply_savings_interest(test_student)

    interest_tx = (
        Transaction.query.filter_by(
            user_id=test_student.user_id,
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
    from app.models import Admin, StudentTeacher

    # Create a teacher and link the student
    teacher = make_admin("testteacher", "SECRET123")
    db.session.add(teacher)
    db.session.flush()

    # Create join code for the student
    join_code = "TEST123"
    test_student.join_code = join_code

    # Link student to teacher
    st = StudentTeacher(user_id=test_student.user_id, teacher_id=teacher.id)
    db.session.add(st)
    db.session.commit()

    recent_deposit_time = datetime.now(timezone.utc) - timedelta(hours=12)
    mature_savings_time = datetime.now(timezone.utc) - timedelta(days=31)

    recent_deposit = Transaction(
        user_id=test_student.user_id,
        join_code=join_code,
        amount=50.0,
        account_type='checking',
        description='Payroll Deposit',
        timestamp=recent_deposit_time,
        date_funds_available=recent_deposit_time,
    )
    mature_savings = Transaction(
        user_id=test_student.user_id,
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
        set_canonical_context(
            session,
            user_id=test_student.user_id,
            class_id=test_student.class_id,
            seat_id=test_student.id,
            role="student",
            join_code=join_code,
        )

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    assert b"You received a deposit of" in response.data
    assert b"$50.00" in response.data

    interest_tx = Transaction.query.filter_by(
        user_id=test_student.user_id,
        description="Monthly Savings Interest",
        account_type='savings',
    ).first()

    assert interest_tx is None
