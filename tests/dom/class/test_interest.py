from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import Transaction, apply_savings_interest, db
from app.models import TransactionStatus, LedgerBalanceSnapshot as BalanceCache
from app.feats.base import FEATContext
from unittest.mock import patch
from tests.helpers.classroom_initializer import initialize


def test_DOM_CLASS_001__apply_savings_interest_with_naive_datetimes(client, app):
    classroom = initialize("chemistry_p1", app)
    test_student = classroom.students[0].seat
    past_date = datetime.now(timezone.utc) - timedelta(days=31)
    savings_tx = Transaction(
        seat_id=test_student.id,
        target_seat_id=test_student.id,
        actor_seat_id=test_student.id,
        mechanism="self",
        user_id=test_student.user_id,
        class_id=test_student.class_id,
        amount=100.0,
        account_type='savings',
        description='Initial savings deposit',
        timestamp=past_date,
        date_funds_available=past_date,
        status=TransactionStatus.POSTED,
        posting_sequence=1,
    )
    with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest"):
        db.session.add(savings_tx)
        db.session.flush()
        # One snapshot row per account (DOM-LED-001 §2); only savings is relevant here.
        db.session.add(BalanceCache(
            seat_id=test_student.id,
            class_id=test_student.class_id,
            account_type="savings",
            posted_balance_cents=10000,
        ))
        db.session.flush()

    with patch("app.routes.student.resolve_canonical_context", return_value=type("Ctx", (), {"class_id": test_student.class_id})()), patch("app.routes.student.get_current_seat", return_value=test_student):
        from app.services.ledger_interest_service import apply_monthly_savings_interest
        with FEATContext("FEAT-LED-001", idempotency_key="interest:test_apply_savings_interest_run"):
            # The rate is a Class-Config policy input and this classroom configures
            # none. SPEC-ECON-001 §11 forbids a hidden default APY, so an
            # unconfigured class pays nothing. Supply the rate explicitly — the
            # documented deterministic-replay override — because what this test
            # pins is naive-datetime handling, not rate resolution.
            apply_monthly_savings_interest(test_student, annual_rate=Decimal("0.045"))

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
