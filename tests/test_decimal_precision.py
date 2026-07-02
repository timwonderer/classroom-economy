"""
Tests for Decimal precision in financial calculations.

These tests verify that the fixes for floating-point rounding bugs work correctly:
1. Transfers that zero out checking account don't trigger -0.00 overdraft fees
2. Partial rent payments with problematic float values can be fully paid off
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.models import (
    User, UserRole, Admin, ClassEconomy, IdentityProfile, Seat, Student, Transaction, RentSettings, RentPayment, BankingSettings, _quantize_currency
)
from app.extensions import db
from app.utils.overdraft import charge_overdraft_fee_if_needed


def _attach_class_scope(teacher, student, join_code, block='A'):
    economy = ClassEconomy(join_code=join_code, user_id=teacher.id, )
    db.session.add(economy)
    db.session.flush()
    # Auto-injected Canonical User
    student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
    if not student_user:
        student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
        db.session.add(student_user)
        db.session.flush()
    seat = Seat(
        user_id=student_user.id,
        class_id=economy.class_id,
        join_code=join_code,
        block=block,
        role='student',
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    return economy.class_id, seat.id


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

        Bug: Student transfers exact checking balance to savings, balance becomes -0.00 due to
        floating-point errors, triggering $35 overdraft fee.

        Fix: Use Decimal for exact representation and normalize near-zero balances.
        """
        # client fixture creates db tables
        # Create teacher with overdraft fees enabled
        teacher = make_admin('teacher_overdraft_test', 'test_secret')
        db.session.add(teacher)
        db.session.flush()

        join_code = 'OVERDRAFT_TEST'
        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        block = Seat(join_code=join_code, block='A', block_identifier='A', role="student")
        db.session.add(block)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name='Test', last_name='S'))
        db.session.add(block)

        student = make_student_identity(block='A', first_name='Test', last_name='S')

        class_id, seat_id = _attach_class_scope(teacher, student, join_code, block='A')
        banking_settings = BankingSettings(
            class_id=class_id,
            block='A',
            overdraft_fee_enabled=True,
            overdraft_fee_type='flat',
            overdraft_fee_flat_amount=Decimal('35.00')
        )
        db.session.add(banking_settings)
        db.session.commit()

        # Give student $100.00 in checking
        initial_deposit = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=Decimal('100.00'),
            account_type='checking',
            type='Initial Deposit',
            description='Starting balance'
        )
        db.session.add(initial_deposit)
        db.session.commit()

        # Verify initial balance
        checking_balance = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        assert checking_balance == Decimal('100.00')

        # Transfer EXACT balance to savings (this was triggering the bug)
        transfer_amount = Decimal('100.00')

        # Withdrawal from checking
        withdrawal_tx = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=-transfer_amount,
            account_type='checking',
            type='Withdrawal',
            description='Transfer to savings'
        )
        db.session.add(withdrawal_tx)

        # Deposit to savings
        deposit_tx = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=transfer_amount,
            account_type='savings',
            type='Deposit',
            description='Transfer from checking'
        )
        db.session.add(deposit_tx)
        db.session.commit()

        # Check balance after transfer
        checking_balance_after = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        savings_balance_after = student.get_savings_balance(class_id=class_id, seat_id=seat_id)

        # CRITICAL: Balance should be exactly 0.00, not -0.00
        assert checking_balance_after == Decimal('0.00')
        assert savings_balance_after == Decimal('100.00')

        # CRITICAL: No overdraft fee should be charged
        fee_charged, fee_amount = charge_overdraft_fee_if_needed(
            db.session.get(Seat, seat_id),
            banking_settings,
            force=False
        )

        assert fee_charged is False
        assert fee_amount == Decimal('0.00')

        # Verify no overdraft fee transaction was created
        overdraft_txs = Transaction.query.filter_by(
            user_id=student_user.id,
            join_code=join_code,
            type='overdraft_fee'
        ).all()
        assert len(overdraft_txs) == 0

        # Final balance should still be 0.00
        final_checking = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        assert final_checking == Decimal('0.00')

    def test_partial_rent_payment_rounding(self, client):
        """
        CRITICAL BUG FIX TEST: Partial rent payments with float-problematic values should pay off completely.

        Bug: Student pays rent in multiple payments. Due to float precision errors, a tiny
        unpayable balance remains (e.g., $0.0000001).

        Fix: Use Decimal for exact representation in rent calculations.
        """
        # client fixture creates db tables
        # Create teacher
        teacher = make_admin('teacher_rent_test', 'test_secret')
        db.session.add(teacher)
        db.session.flush()

        join_code = 'RENT_TEST'
        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        block = Seat(join_code=join_code, block='A', block_identifier='A', role="student")
        db.session.add(block)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name='Rent', last_name='T'))
        db.session.add(block)

        # Create rent settings with incremental payments enabled
        rent_settings = RentSettings(block='A',
            is_enabled=True,
            rent_amount=Decimal('50.00'),  # Total rent
            allow_incremental_payment=True
        )
        db.session.add(rent_settings)

        student = make_student_identity(block='A', first_name='Rent', last_name='T')

        class_id, seat_id = _attach_class_scope(teacher, student, join_code, block='A')

        # Give student money to pay rent
        initial_deposit = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=Decimal('60.00'),
            account_type='checking',
            type='Initial Deposit',
            description='Starting balance'
        )
        db.session.add(initial_deposit)
        db.session.commit()

        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Make first partial payment - problematic float value
        # 33.33 is a repeating decimal in binary, causes precision issues
        payment1_amount = Decimal('33.33')

        payment1 = RentPayment(
            user_id=student_user.id,
            period='A',
            join_code=join_code,
            amount_paid=payment1_amount,
            period_month=current_month,
            period_year=current_year,
            was_late=False
        )
        db.session.add(payment1)

        rent_tx1 = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=-payment1_amount,
            account_type='checking',
            type='Rent Payment',
            description='Partial rent payment 1/2'
        )
        db.session.add(rent_tx1)
        db.session.commit()

        # Calculate remaining rent
        total_due = Decimal('50.00')
        paid_so_far = payment1_amount
        remaining = _quantize_currency(total_due - paid_so_far)

        # Should be exactly $16.67
        assert remaining == Decimal('16.67')

        # Make second payment for exact remaining amount
        payment2_amount = remaining

        payment2 = RentPayment(
            user_id=student_user.id,
            period='A',
            join_code=join_code,
            amount_paid=payment2_amount,
            period_month=current_month,
            period_year=current_year,
            was_late=False
        )
        db.session.add(payment2)

        rent_tx2 = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=-payment2_amount,
            account_type='checking',
            type='Rent Payment',
            description='Final rent payment 2/2'
        )
        db.session.add(rent_tx2)
        db.session.commit()

        # Calculate total paid
        all_payments = RentPayment.query.filter_by(
            user_id=student_user.id,
            period='A',
            join_code=join_code,
            period_month=current_month,
            period_year=current_year
        ).all()

        total_paid = sum(_quantize_currency(p.amount_paid) for p in all_payments)

        # CRITICAL: Total should equal exactly $50.00
        assert total_paid == Decimal('50.00')

        # CRITICAL: Remaining balance should be exactly $0.00, not $0.0000001
        remaining_final = _quantize_currency(total_due - total_paid)
        assert remaining_final == Decimal('0.00')

        # Student should have exactly $10.00 left in checking (60 - 50)
        final_checking = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        assert final_checking == Decimal('10.00')

    def test_near_zero_balance_normalization(self, client):
        """Test that near-zero balances are normalized to exactly zero."""
        # client fixture creates db tables
        # Create teacher
        teacher = make_admin('teacher_zero_test', 'test_secret')
        db.session.add(teacher)
        db.session.flush()

        join_code = 'ZERO_TEST'
        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        block = Seat(join_code=join_code, block='A', block_identifier='A', role="student")
        db.session.add(block)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name='Zero', last_name='T'))
        db.session.add(block)

        # Create student
        student = make_student_identity(block='A', first_name='Zero', last_name='T')

        class_id, seat_id = _attach_class_scope(teacher, student, join_code, block='A')
        banking_settings = BankingSettings(
            class_id=class_id,
            block='A',
            overdraft_fee_enabled=True,
            overdraft_fee_type='flat',
            overdraft_fee_flat_amount=Decimal('35.00')
        )
        db.session.add(banking_settings)
        db.session.commit()

        # Test various near-zero balances
        # These values should all round to 0.00 with banker's rounding (ROUND_HALF_EVEN)
        # Values < 0.005 round to 0.00, values >= 0.005 round to 0.01
        test_cases = [
            Decimal('0.001'),   # Less than 0.005 - rounds to 0.00
            Decimal('-0.001'),  # Less than 0.005 - rounds to -0.00 = 0.00
            Decimal('0.004'),   # Less than 0.005 - rounds to 0.00
            Decimal('-0.004'),  # Less than 0.005 - rounds to -0.00 = 0.00
        ]

        for near_zero_amount in test_cases:
            # Create transaction with near-zero amount
            tx = Transaction(
                user_id=student_user.id,class_id=class_id,
                join_code=join_code,
                amount=near_zero_amount,
                account_type='checking',
                type='Test',
                description=f'Near-zero test: {near_zero_amount}'
            )
            db.session.add(tx)
            db.session.commit()

            # Get balance
            balance = student.get_checking_balance(class_id=class_id, seat_id=seat_id)

            # Near-zero balances should NOT trigger overdraft fee
            fee_charged, fee_amount = charge_overdraft_fee_if_needed(
                db.session.get(Seat, seat_id),
                banking_settings,
                force=False
            )

            assert fee_charged is False, f"Fee charged for balance {balance} from amount {near_zero_amount}"
            assert fee_amount == Decimal('0.00')

            # Clean up for next test
            db.session.delete(tx)
            db.session.commit()

    def test_actually_negative_balance_charges_fee(self, client):
        """Test that genuinely negative balances still trigger overdraft fees correctly."""
        # client fixture creates db tables
        # Create teacher
        teacher = make_admin('teacher_negative_test', 'test_secret')
        db.session.add(teacher)
        db.session.flush()

        join_code = 'NEG_TEST'
        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        block = Seat(join_code=join_code, block='A', block_identifier='A', role="student")
        db.session.add(block)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name='Negative', last_name='T'))
        db.session.add(block)

        # Create student
        student = make_student_identity(block='A', first_name='Negative', last_name='T')

        class_id, seat_id = _attach_class_scope(teacher, student, join_code, block='A')
        banking_settings = BankingSettings(
            class_id=class_id,
            block='A',
            overdraft_fee_enabled=True,
            overdraft_fee_type='flat',
            overdraft_fee_flat_amount=Decimal('35.00')
        )
        db.session.add(banking_settings)

        # Create a genuinely negative balance (-$10.00)
        negative_tx = Transaction(
            user_id=student_user.id,class_id=class_id,
            join_code=join_code,
            amount=Decimal('-10.00'),
            account_type='checking',
            type='Overdraft',
            description='Genuinely negative balance'
        )
        db.session.add(negative_tx)
        db.session.commit()

        # Check balance
        balance = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        assert balance == Decimal('-10.00')

        # SHOULD trigger overdraft fee
        fee_charged, fee_amount = charge_overdraft_fee_if_needed(
            db.session.get(Seat, seat_id),
            banking_settings,
            force=False
        )
        # The overdraft function only flushes, we need to commit
        db.session.commit()

        assert fee_charged is True
        assert fee_amount == Decimal('35.00')

        # Verify fee transaction was created
        overdraft_txs = Transaction.query.filter_by(
            user_id=student_user.id,
            join_code=join_code,
            type='overdraft_fee'
        ).all()
        assert len(overdraft_txs) == 1
        assert overdraft_txs[0].amount == Decimal('-35.00')

        # Final balance should be -$45.00 (-10 - 35)
        final_balance = student.get_checking_balance(class_id=class_id, seat_id=seat_id)
        assert final_balance == Decimal('-45.00')

    def test_partial_late_rent_payment_quantizes_allocated_late_fee_before_storage(self, client):
        teacher = make_admin('teacher_late_fee_quantize', 'test_secret')
        db.session.add(teacher)
        db.session.flush()

        join_code = 'LATE_FEE_Q'
        student = make_student_identity(block='A', first_name='Late', last_name='F')

        identity = IdentityProfile(profile_type="roster", first_name="Late", last_name="F")
        db.session.add(identity)
        db.session.flush()
        economy = ClassEconomy(join_code=join_code, user_id=teacher.id, )
        db.session.add(economy)
        db.session.flush()

        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        _tb_seat = Seat(user_id=student_user.id, class_id=economy.class_id, join_code=join_code, block='A', block_identifier='A', role="student", claimed_at=datetime.now(timezone.utc))

        db.session.add(_tb_seat)

        db.session.flush()

        db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name='Late', last_name='F'))

        db.session.add(RentSettings(join_code=join_code,
            class_id=economy.class_id,
            block='A',
            is_enabled=True,
            rent_amount=Decimal('570.00'),
            allow_incremental_payment=True,
            frequency_type='monthly',
            first_rent_due_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            grace_period_days=0,
            late_penalty_amount=Decimal('0.01'),
            late_penalty_type='once',
        ))

        # Auto-injected Canonical User
        student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
        if not student_user:
            student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT, current_session_nonce='test_nonce_123')
            db.session.add(student_user)
            db.session.flush()
        db.session.add(
            Seat(
                user_id=student_user.id,
                class_id=economy.class_id,
                join_code=join_code,
                block='A',
                role='student',
                claimed_at=datetime.now(timezone.utc),
            )
        )
        db.session.flush()
        seat = Seat.query.filter_by(user_id=student_user.id).first()

        db.session.execute(db.text("UPDATE users SET last_active_class_id = :cid, last_active_seat_id = :sid WHERE id = :uid"), {'cid': seat.class_id, 'sid': seat.id, 'uid': student_user.id})

        db.session.commit()

        with client.session_transaction() as sess:
            sess['user_id'] = student_user.id

            sess['current_session_nonce'] = student_user.current_session_nonce
            sess['current_join_code'] = join_code
            from tests.helpers.canonical_session import set_canonical_context
            set_canonical_context(
                sess,
                user_id=student_user.id,
                class_id=economy.class_id,
                seat_id=seat.id,
                role="student",
                join_code=join_code,
            )
            sess['login_time'] = datetime.now(timezone.utc).isoformat()
            sess['last_activity'] = datetime.now(timezone.utc).isoformat()

        response = client.post(
            '/student/rent/pay/A',
            data={'amount': '285.00'},
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)

        rent_payment = RentPayment.query.filter_by(
            user_id=student_user.id,
            join_code=join_code,
        ).order_by(RentPayment.id.desc()).first()
        assert rent_payment is not None
        assert rent_payment.late_fee_charged == Decimal('0.00')
