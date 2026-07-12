"""
Tests for Decimal precision in financial calculations.

These tests verify that the fixes for floating-point rounding bugs work correctly:
1. Transfers that zero out checking account don't trigger -0.00 overdraft fees
2. Partial rent payments with problematic float values can be fully paid off
"""
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.models import (
    ClassEconomy, Seat, Transaction, RentSettings, RentPayment, BankingSettings, _quantize_currency
)
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan
from sqlalchemy import text
from app.services.obligations_service import create_and_schedule_rent_policy_version


def _setup_student_in_class(teacher, join_code):
    """Create a class and student, return (class_id, seat_id, student_seat)."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"decimal_precision:setup:{join_code}"):
        economy = ClassEconomy(join_code=join_code, user_id=teacher.id)
        db.session.add(economy)
        db.session.flush()

        student = make_student_identity(class_id=economy.class_id, first_name="Test", last_name="S")
        db.session.flush()
        seat = Seat.query.filter_by(user_id=student.user_id, class_id=economy.class_id, role="student").first()
    return economy.class_id, seat.id, student


def _get_balance(seat_id, account_type):
    result = db.session.execute(
        text(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger_transaction "
            "WHERE seat_id = :sid AND account_type = :account_type"
        ),
        {"sid": seat_id, "account_type": account_type},
    ).scalar()
    return Decimal(str(result))


class TestDecimalPrecision:
    """Test that Decimal types fix floating-point rounding bugs."""

    def test_quantize_currency_helper(self):
        """Test that _quantize_currency properly handles various inputs."""
        assert _quantize_currency(100.00) == Decimal('100.00')
        assert _quantize_currency(100.123456) == Decimal('100.12')
        assert _quantize_currency(0.0) == Decimal('0.00')
        assert _quantize_currency(-0.0) == Decimal('0.00')
        assert _quantize_currency(None) == Decimal('0.00')
        assert _quantize_currency(Decimal('50.50')) == Decimal('50.50')

        # Test rounding (ROUND_HALF_EVEN - banker's rounding)
        assert _quantize_currency(10.125) == Decimal('10.12')  # Rounds to even (2)
        assert _quantize_currency(10.135) == Decimal('10.14')  # Rounds to even (4)
        assert _quantize_currency(10.126) == Decimal('10.13')  # Rounds up (not halfway)

    def test_transfer_to_zero_no_overdraft_fee(self, client):
        """
        CRITICAL BUG FIX TEST: Transfer that zeros out checking should not trigger overdraft fee.
        """
        with FEATContext("FEAT-LED-001", idempotency_key="decimal_precision:overdraft_setup"):
            teacher = make_admin('teacher_overdraft_test', 'test_secret')
            db.session.flush()

            join_code = 'OVERDRAFT_TEST'
            class_id, seat_id, student = _setup_student_in_class(teacher, join_code)
            student_user_id = student.user_id

            banking_settings = BankingSettings(
                class_id=class_id,
                block='A',
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)
            db.session.flush()

            # Give student $100.00 in checking
            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=Decimal('100.00'),
                account_type='checking',
                type='Initial Deposit',
                description='Starting balance'
            ))
            db.session.flush()

        checking_balance = _get_balance(seat_id, "checking")
        assert checking_balance == Decimal('100.00')

        transfer_amount = Decimal('100.00')

        with FEATContext("FEAT-LED-001", idempotency_key="decimal_precision:overdraft_transfer"):
            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=-transfer_amount,
                account_type='checking',
                type='Withdrawal',
                description='Transfer to savings'
            ))
            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=transfer_amount,
                account_type='savings',
                type='Deposit',
                description='Transfer from checking'
            ))
            db.session.flush()

        checking_balance_after = _get_balance(seat_id, "checking")
        savings_balance_after = _get_balance(seat_id, "savings")

        assert checking_balance_after == Decimal('0.00')
        assert savings_balance_after == Decimal('100.00')

        overdraft_txs = Transaction.query.filter_by(
            user_id=student_user_id,
            join_code=join_code,
            type='overdraft_fee'
        ).all()
        assert len(overdraft_txs) == 0

        final_checking = _get_balance(seat_id, "checking")
        assert final_checking == Decimal('0.00')

    def test_partial_rent_payment_rounding(self, client):
        """
        CRITICAL BUG FIX TEST: Partial rent payments with float-problematic values should pay off completely.
        """
        with FEATContext("FEAT-OBL-001", idempotency_key="decimal_precision:rent_setup"):
            teacher = make_admin('teacher_rent_test', 'test_secret')
            db.session.flush()

            join_code = 'RENT_TEST'
            class_id, seat_id, student = _setup_student_in_class(teacher, join_code)
            student_user_id = student.user_id

            rent_settings = RentSettings(
                class_id=class_id,
                rent_amount=Decimal('50.00'),
                allow_incremental_payment=True,
                frequency_type='monthly',
                first_rent_due_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                grace_period_days=0,
                late_penalty_amount=Decimal('0.00'),
                late_penalty_type='once',
            )
            db.session.add(rent_settings)

            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=Decimal('60.00'),
                account_type='checking',
                type='Initial Deposit',
                description='Starting balance'
            ))
            db.session.flush()
            create_and_schedule_rent_policy_version(class_id)

        now = datetime.now()
        current_month = now.month
        current_year = now.year

        payment1_amount = Decimal('33.33')
        with FEATContext("FEAT-OBL-001", idempotency_key="decimal_precision:rent_payment_1"):
            db.session.add(RentPayment(
                seat_id=seat_id,
                class_id=class_id,
                period='A',
                join_code=join_code,
                amount_paid=payment1_amount,
                period_month=current_month,
                period_year=current_year,
                was_late=False
            ))
            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=-payment1_amount,
                account_type='checking',
                type='Rent Payment',
                description='Partial rent payment 1/2'
            ))
            db.session.flush()

        total_due = Decimal('50.00')
        paid_so_far = payment1_amount
        remaining = _quantize_currency(total_due - paid_so_far)
        assert remaining == Decimal('16.67')

        payment2_amount = remaining
        with FEATContext("FEAT-OBL-001", idempotency_key="decimal_precision:rent_payment_2"):
            db.session.add(RentPayment(
                seat_id=seat_id,
                class_id=class_id,
                period='A',
                join_code=join_code,
                amount_paid=payment2_amount,
                period_month=current_month,
                period_year=current_year,
                was_late=False
            ))
            db.session.add(Transaction(
                user_id=student_user_id, class_id=class_id,
                join_code=join_code,
                amount=-payment2_amount,
                account_type='checking',
                type='Rent Payment',
                description='Final rent payment 2/2'
            ))
            db.session.flush()

        all_payments = RentPayment.query.filter_by(
            seat_id=seat_id,
            period='A',
            join_code=join_code,
            period_month=current_month,
            period_year=current_year
        ).all()

        total_paid = sum(_quantize_currency(p.amount_paid) for p in all_payments)
        assert total_paid == Decimal('50.00')

        remaining_final = _quantize_currency(total_due - total_paid)
        assert remaining_final == Decimal('0.00')

        final_checking = _get_balance(seat_id, "checking")
        assert final_checking == Decimal('10.00')

    def test_near_zero_balance_normalization(self, client):
        """Test that near-zero balances are normalized to exactly zero."""
        with FEATContext("FEAT-LED-001", idempotency_key="decimal_precision:near_zero_setup"):
            teacher = make_admin('teacher_zero_test', 'test_secret')
            db.session.flush()

            join_code = 'ZERO_TEST'
            class_id, seat_id, student = _setup_student_in_class(teacher, join_code)
            student_user_id = student.user_id

            banking_settings = BankingSettings(
                class_id=class_id,
                block='A',
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)
            db.session.flush()

        test_cases = [
            Decimal('0.001'),
            Decimal('-0.001'),
            Decimal('0.004'),
            Decimal('-0.004'),
        ]

        for near_zero_amount in test_cases:
            with FEATContext("FEAT-LED-001", idempotency_key=f"decimal_precision:near_zero:{near_zero_amount}"):
                tx = Transaction(
                    user_id=student_user_id, class_id=class_id,
                    join_code=join_code,
                    amount=near_zero_amount,
                    account_type='checking',
                    type='Test',
                    description=f'Near-zero test: {near_zero_amount}'
                )
                db.session.add(tx)
                db.session.flush()

            balance = _get_balance(seat_id, "checking")

            intended_plan = build_intended_ledger_plan(
                seat_id=seat_id,
                class_id=class_id,
                user_id=student_user_id,
                debit_amount=Decimal("0.00"),
                description="near-zero overdraft check",
            )
            resolved_plan = resolve_intended_ledger_plan(
                plan=intended_plan,
                banking_settings=banking_settings,
                idempotency_key=f"decimal_precision:near_zero_resolve:{near_zero_amount}",
            )
            assert resolved_plan.outcome == "ACCEPT", f"Resolver should accept zero balance for {near_zero_amount}"
            assert resolved_plan.overdraft_fee_amount == Decimal('0.00')

            with FEATContext("FEAT-LED-001", idempotency_key=f"decimal_precision:near_zero_cleanup:{near_zero_amount}"):
                db.session.delete(tx)
                db.session.flush()

    def test_actually_negative_balance_charges_fee(self, client):
        """Test that genuinely negative balances still trigger overdraft fees correctly."""
        with FEATContext("FEAT-LED-001", idempotency_key="decimal_precision:negative_setup"):
            teacher = make_admin('teacher_negative_test', 'test_secret')
            db.session.flush()

            join_code = 'NEG_TEST'
            class_id, seat_id, student = _setup_student_in_class(teacher, join_code)
            student_user_id = student.user_id

            banking_settings = BankingSettings(
                class_id=class_id,
                overdraft_fee_enabled=True,
                overdraft_fee_type='flat',
                overdraft_fee_flat_amount=Decimal('35.00')
            )
            db.session.add(banking_settings)
            db.session.flush()

            rent_settings = RentSettings(
                class_id=class_id,
                rent_amount=Decimal('10.00'),
                allow_incremental_payment=False,
                frequency_type='monthly',
                first_rent_due_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
                grace_period_days=0,
                late_penalty_amount=Decimal('0.00'),
                late_penalty_type='once',
            )
            db.session.add(rent_settings)
            db.session.flush()
            create_and_schedule_rent_policy_version(class_id)

        with client.session_transaction() as sess:
            sess['user_id'] = student_user_id
            sess['current_join_code'] = join_code
            from tests.helpers.canonical_session import set_canonical_context
            set_canonical_context(
                sess,
                user_id=student_user_id,
                class_id=class_id,
                seat_id=seat_id,
                role="student",
            )
            sess['login_time'] = datetime.now(timezone.utc).isoformat()
            sess['last_activity'] = datetime.now(timezone.utc).isoformat()

        with FEATContext("FEAT-OBL-001", idempotency_key="decimal_precision:negative_rent_post"):
            response = client.post(
                '/student/rent/pay/A',
                data={'amount': '10.00'},
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)

        overdraft_txs = Transaction.query.filter_by(
            seat_id=seat_id,
            type='overdraft_fee'
        ).all()
        assert len(overdraft_txs) == 1
        assert overdraft_txs[0].amount == Decimal('-35.00')
