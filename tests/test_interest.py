from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import Transaction, apply_savings_interest, db


def test_apply_savings_interest_with_naive_datetimes(client, test_student):
    past_date = datetime.utcnow() - timedelta(days=31)
    savings_tx = Transaction(
        student_id=test_student.id,
        amount=100.0,
        account_type='savings',
        description='Initial savings deposit',
        timestamp=past_date,
        date_funds_available=past_date,
    )
    db.session.add(savings_tx)
    db.session.commit()

    # Mock get_current_teacher_id to return None (uses default banking settings)
    with patch('app.routes.student.get_current_teacher_id', return_value=None):
        apply_savings_interest(test_student)

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
    assert interest_tx.amount == round(100.0 * (0.045 / 12), 2)


def test_dashboard_renders_recent_deposit(client, test_student):
    recent_deposit_time = datetime.utcnow() - timedelta(hours=12)
    mature_savings_time = datetime.utcnow() - timedelta(days=31)

    recent_deposit = Transaction(
        student_id=test_student.id,
        amount=50.0,
        account_type='checking',
        description='Payroll Deposit',
        timestamp=recent_deposit_time,
        date_funds_available=recent_deposit_time,
    )
    mature_savings = Transaction(
        student_id=test_student.id,
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

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    assert b"You received a deposit of $50.00" in response.data

    interest_tx = Transaction.query.filter_by(
        student_id=test_student.id,
        description="Monthly Savings Interest",
        account_type='savings',
    ).first()

    assert interest_tx is not None
