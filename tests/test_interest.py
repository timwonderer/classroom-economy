from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_sysadmin
from app import Transaction, apply_savings_interest, db
from app.models import TransactionStatus, BalanceCache
from app.feats.base import FEATContext
from unittest.mock import patch


def test_apply_savings_interest_with_naive_datetimes(client, test_student):
    past_date = datetime.now(timezone.utc) - timedelta(days=31)
    savings_tx = Transaction(
        seat_id=test_student.id,
        user_id=test_student.user_id,
        class_id=test_student.class_id,
        amount=100.0,
        account_type='savings',
        description='Initial savings deposit',
        timestamp=past_date,
        date_funds_available=past_date,
        status=TransactionStatus.POSTED,
    )
    with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest"):
        db.session.add(savings_tx)
        db.session.flush()
        db.session.add(BalanceCache(
            seat_id=test_student.id,
            class_id=test_student.class_id,
            posted_checking_balance_cents=0,
            posted_savings_balance_cents=10000,
        ))
        db.session.flush()

    with patch("app.routes.student.resolve_canonical_context", return_value=type("Ctx", (), {"class_id": test_student.class_id})()), patch("app.routes.student.get_current_seat", return_value=test_student):
        from app.services.ledger_service import _apply_monthly_savings_interest
        with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest_run"):
            _apply_monthly_savings_interest(test_student)

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
    # Expected: 100 * (0.045 / 12) = 0.375 -> rounds to 0.38
    assert interest_tx.amount == Decimal('0.38')
