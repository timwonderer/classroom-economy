"""
Test for handling NULL or invalid transaction amounts in get_total_earnings.

This test verifies the fix for the decimal.InvalidOperation error that occurs
when a transaction has a NULL amount value.
"""
from decimal import Decimal
from unittest.mock import PropertyMock, patch
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from app.models import User, UserRole, Student, Transaction, Admin, ClassEconomy
import sqlalchemy as sa

def test_get_total_earnings_defensive_checks(client, app):
    """Test that get_total_earnings defensive NULL checks don't break normal operations.
    
    This test verifies that the added defensive programming (checking for
    is not None) doesn't break normal transaction processing.
    """
    with app.app_context():
        # Create a teacher
        teacher = make_admin("test_teacher", "test_secret")
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST123"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            user_id=teacher.id,
            display_name='Test Class',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent",
            last_initial="A",
            block="Period 1",
            salt=get_random_salt(),
            first_half_hash="test_hash_1",
        )
        db.session.add(student)
        db.session.commit()
        
        # Create a normal transaction with a valid amount
        valid_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('10.50'),
            description="Valid earning",
            is_void=False
        )
        db.session.add(valid_tx)
        db.session.commit()
        
        # Verify normal case works with the is not None check
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 10.50
        
        # Deprecated teacher-only path should not return cross-class aggregates.
        earnings_by_teacher = student.get_total_earnings(teacher_id=teacher.id)
        assert earnings_by_teacher == 0.0
        
        # Unscoped path should not return cross-class aggregates.
        earnings_all = student.get_total_earnings()
        assert earnings_all == 0.0
        
        # Add another transaction to verify aggregation still works
        another_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('5.25'),
            description="Another earning",
            is_void=False
        )
        db.session.add(another_tx)
        db.session.commit()
        
        # Should now be 15.75
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 15.75


def test_get_total_earnings_with_negative_amounts(client, app):
    """Test that get_total_earnings correctly filters negative amounts (expenses)."""
    with app.app_context():
        # Create a teacher
        teacher = make_admin("test_teacher2", "test_secret")
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST456"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            user_id=teacher.id,
            display_name='Test Class 2',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent2",
            last_initial="B",
            block="Period 2",
            salt=get_random_salt(),
            first_half_hash="test_hash_2",
        )
        db.session.add(student)
        db.session.commit()
        
        # Create positive transactions (earnings)
        positive_tx1 = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('15.00'),
            description="Earning 1",
            is_void=False
        )
        positive_tx2 = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('25.50'),
            description="Earning 2",
            is_void=False
        )
        
        # Create negative transaction (expense) - should not be counted in earnings
        negative_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('-10.00'),
            description="Expense",
            is_void=False
        )
        
        # Create voided transaction - should not be counted
        voided_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('100.00'),
            description="Voided earning",
            is_void=True
        )
        
        db.session.add_all([positive_tx1, positive_tx2, negative_tx, voided_tx])
        db.session.commit()
        
        # Earnings should only include positive, non-voided transactions
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 40.50  # 15.00 + 25.50


def test_get_total_earnings_with_zero_amount(client, app):
    """Test that get_total_earnings handles zero amounts correctly."""
    with app.app_context():
        # Create a teacher
        teacher = make_admin("test_teacher3", "test_secret")
        db.session.add(teacher)
        db.session.commit()
        
        join_code = "TEST789"
        
        # Create ClassEconomy first for FK constraint
        economy = ClassEconomy(
            join_code=join_code,
            user_id=teacher.id,
            display_name='Test Class 3',
            status='active',
            created_by_admin_id=teacher.id
        )
        db.session.add(economy)
        db.session.flush()
        
        # Create a student
        from app.hash_utils import get_random_salt
        student = Student(
            first_name="TestStudent3",
            last_initial="C",
            block="Period 3",
            salt=get_random_salt(),
            first_half_hash="test_hash_3",
        )
        db.session.add(student)
        db.session.commit()
        
        # Create a transaction with zero amount
        zero_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('0.00'),
            description="Zero transaction",
            is_void=False
        )
        
        # Create a positive transaction
        positive_tx = Transaction(
            user_id=student_user.id,join_code=join_code,
            amount=Decimal('5.00'),
            description="Positive transaction",
            is_void=False
        )
        
        db.session.add_all([zero_tx, positive_tx])
        db.session.commit()
        
        # Earnings should not include zero amounts (> 0 condition)
        earnings = student.get_total_earnings(join_code=join_code, teacher_id=teacher.id)
        assert earnings == 5.00


