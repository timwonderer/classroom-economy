"""
Test for handling NULL or invalid transaction amounts in get_total_earnings.

This test verifies the fix for the decimal.InvalidOperation error that occurs
when a transaction has a NULL amount value.
"""
from decimal import Decimal
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope, make_student_seat
from app import db
from app.models import Student, Transaction, Admin, ClassEconomy, IdentityProfile
from app.hash_utils import get_random_salt


def _make_student(suffix):
    """Create a v2-canonical Student with required IdentityProfile."""
    profile = IdentityProfile(
        profile_type="student",
        first_name=f"TestStudent{suffix}",
        last_name=suffix[0] if suffix else "T",
    )
    db.session.add(profile)
    db.session.flush()
    student = Student(
        identity_profile=profile,
        block="Period 1",
        salt=get_random_salt(),
        first_half_hash=f"test_hash_{suffix}",
    )
    db.session.add(student)
    db.session.flush()
    return student


def test_get_total_earnings_defensive_checks(client, app):
    """Test that get_total_earnings defensive NULL checks don't break normal operations.

    This test verifies that the added defensive programming (checking for
    is not None) doesn't break normal transaction processing.
    """
    with app.app_context():
        teacher = make_admin("test_teacher_null1", "test_secret")
        db.session.add(teacher)
        db.session.flush()

        student = _make_student("A1")
        class_row = create_class_scope(teacher=teacher, join_code="TXNULL1", student=student, block="A")
        db.session.flush()

        seat = make_student_seat(
            class_id=class_row.class_id,
            join_code="TXNULL1",
            block="A",
            first_name="TestStudent",
            last_name="A1",
        )
        db.session.commit()

        valid_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL1",
            amount=Decimal('10.50'),
            account_type='checking',
            type='deposit',
            description="Valid earning",
            is_void=False,
        )
        db.session.add(valid_tx)
        db.session.commit()

        # Verify normal case works with the is not None check
        earnings = student.get_total_earnings(class_id=class_row.class_id)
        assert earnings == 10.50

        # Unscoped path should not return cross-class aggregates.
        earnings_all = student.get_total_earnings()
        assert earnings_all == 0.0

        # Add another transaction to verify aggregation still works
        another_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL1",
            amount=Decimal('5.25'),
            account_type='checking',
            type='deposit',
            description="Another earning",
            is_void=False,
        )
        db.session.add(another_tx)
        db.session.commit()

        # Should now be 15.75
        earnings = student.get_total_earnings(class_id=class_row.class_id)
        assert earnings == 15.75


def test_get_total_earnings_with_negative_amounts(client, app):
    """Test that get_total_earnings correctly filters negative amounts (expenses)."""
    with app.app_context():
        teacher = make_admin("test_teacher_null2", "test_secret")
        db.session.add(teacher)
        db.session.flush()

        student = _make_student("B2")
        class_row = create_class_scope(teacher=teacher, join_code="TXNULL2", student=student, block="A")
        db.session.flush()

        seat = make_student_seat(
            class_id=class_row.class_id,
            join_code="TXNULL2",
            block="A",
            first_name="TestStudent2",
            last_name="B",
        )
        db.session.commit()

        positive_tx1 = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL2",
            amount=Decimal('15.00'),
            account_type='checking',
            type='deposit',
            description="Earning 1",
            is_void=False,
        )
        positive_tx2 = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL2",
            amount=Decimal('25.50'),
            account_type='checking',
            type='deposit',
            description="Earning 2",
            is_void=False,
        )
        negative_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL2",
            amount=Decimal('-10.00'),
            account_type='checking',
            type='purchase',
            description="Expense",
            is_void=False,
        )
        voided_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL2",
            amount=Decimal('100.00'),
            account_type='checking',
            type='deposit',
            description="Voided earning",
            is_void=True,
        )

        db.session.add_all([positive_tx1, positive_tx2, negative_tx, voided_tx])
        db.session.commit()

        # Earnings should only include positive, non-voided transactions
        earnings = student.get_total_earnings(class_id=class_row.class_id)
        assert earnings == 40.50  # 15.00 + 25.50


def test_get_total_earnings_with_zero_amount(client, app):
    """Test that get_total_earnings handles zero amounts correctly."""
    with app.app_context():
        teacher = make_admin("test_teacher_null3", "test_secret")
        db.session.add(teacher)
        db.session.flush()

        student = _make_student("C3")
        class_row = create_class_scope(teacher=teacher, join_code="TXNULL3", student=student, block="A")
        db.session.flush()

        seat = make_student_seat(
            class_id=class_row.class_id,
            join_code="TXNULL3",
            block="A",
            first_name="TestStudent3",
            last_name="C",
        )
        db.session.commit()

        zero_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL3",
            amount=Decimal('0.00'),
            account_type='checking',
            type='adjustment',
            description="Zero transaction",
            is_void=False,
        )
        positive_tx = Transaction(
            seat_id=seat.id,
            class_id=class_row.class_id,
            join_code="TXNULL3",
            amount=Decimal('5.00'),
            account_type='checking',
            type='deposit',
            description="Positive transaction",
            is_void=False,
        )

        db.session.add_all([zero_tx, positive_tx])
        db.session.commit()

        # Earnings should not include zero amounts (> 0 condition)
        earnings = student.get_total_earnings(class_id=class_row.class_id)
        assert earnings == 5.00
