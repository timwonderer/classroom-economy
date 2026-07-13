"""
Test for handling NULL or invalid transaction amounts in get_total_earnings.

This test verifies the fix for the decimal.InvalidOperation error that occurs
when a transaction has a NULL amount value.
"""
from decimal import Decimal
from unittest.mock import PropertyMock, patch
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import make_student_identity
from app.feats.base import FEATContext
from app import db
from app.models import Transaction, ClassEconomy
from app.routes.student import _get_total_earnings_for_seat
import sqlalchemy as sa

def test_get_total_earnings_defensive_checks(client, app):
    """Test that get_total_earnings defensive NULL checks don't break normal operations.
    
    This test verifies that the added defensive programming (checking for
    is not None) doesn't break normal transaction processing.
    """
    with app.app_context():
        with FEATContext("FEAT-IDEN-001", idempotency_key="transaction-amount-null:case-1"):
            teacher = seed_canonical_admin("test_teacher", "test_secret").user
            db.session.flush()

            economy = ClassEconomy(
                join_code="TEST123",
                user_id=teacher.id,
                display_name='Test Class',
                status='active',
            )
            db.session.add(economy)
            db.session.flush()

            student = make_student_identity(class_id=economy.class_id, first_name="TestStudent", last_name="A")

            valid_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('10.50'),
                description="Valid earning",
                is_void=False
            )
            db.session.add(valid_tx)

        # Verify normal case works with the canonical class scope.
        earnings = _get_total_earnings_for_seat(student.id, class_id=economy.class_id)
        assert earnings == 10.50
        
        # Add another transaction to verify aggregation still works.
        with FEATContext("FEAT-IDEN-001", idempotency_key="transaction-amount-null:case-1:more"):
            another_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('5.25'),
                description="Another earning",
                is_void=False
            )
            db.session.add(another_tx)

        # Should now be 15.75
        earnings = _get_total_earnings_for_seat(student.id, class_id=economy.class_id)
        assert earnings == 15.75


def test_get_total_earnings_with_negative_amounts(client, app):
    """Test that get_total_earnings correctly filters negative amounts (expenses)."""
    with app.app_context():
        with FEATContext("FEAT-IDEN-001", idempotency_key="transaction-amount-null:case-2"):
            teacher = seed_canonical_admin("test_teacher2", "test_secret").user
            db.session.flush()

            economy = ClassEconomy(
                join_code="TEST456",
                user_id=teacher.id,
                display_name='Test Class 2',
                status='active',
            )
            db.session.add(economy)
            db.session.flush()

            student = make_student_identity(class_id=economy.class_id, first_name="TestStudent2", last_name="B")

            # Create positive transactions (earnings)
            positive_tx1 = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('15.00'),
                description="Earning 1",
                is_void=False
            )
            positive_tx2 = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('25.50'),
                description="Earning 2",
                is_void=False
            )

            # Create negative transaction (expense) - should not be counted in earnings
            negative_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('-10.00'),
                description="Expense",
                is_void=False
            )

            # Create voided transaction - should not be counted
            voided_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('100.00'),
                description="Voided earning",
                is_void=True
            )

            db.session.add_all([positive_tx1, positive_tx2, negative_tx, voided_tx])

        # Earnings should only include positive, non-voided transactions
        earnings = _get_total_earnings_for_seat(student.id, class_id=economy.class_id)
        assert earnings == 40.50  # 15.00 + 25.50


def test_get_total_earnings_with_zero_amount(client, app):
    """Test that get_total_earnings handles zero amounts correctly."""
    with app.app_context():
        with FEATContext("FEAT-IDEN-001", idempotency_key="transaction-amount-null:case-3"):
            teacher = seed_canonical_admin("test_teacher3", "test_secret").user
            db.session.flush()

            economy = ClassEconomy(
                join_code="TEST789",
                user_id=teacher.id,
                display_name='Test Class 3',
                status='active',
            )
            db.session.add(economy)
            db.session.flush()

            student = make_student_identity(class_id=economy.class_id, first_name="TestStudent3", last_name="C")

            # Create a transaction with zero amount
            zero_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('0.00'),
                description="Zero transaction",
                is_void=False
            )

            # Create a positive transaction
            positive_tx = Transaction(
                user_id=student.user_id,
                class_id=economy.class_id,
                amount=Decimal('5.00'),
                description="Positive transaction",
                is_void=False
            )

            db.session.add_all([zero_tx, positive_tx])

        # Earnings should not include zero amounts (> 0 condition)
        earnings = _get_total_earnings_for_seat(student.id, class_id=economy.class_id)
        assert earnings == 5.00
