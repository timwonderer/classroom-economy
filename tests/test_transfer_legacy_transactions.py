"""
Test for student transfer functionality with legacy transactions.

Ensures that students can transfer between checking and savings accounts
even when they have legacy transactions without join_code.
"""

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, TeacherBlock
from app.extensions import db
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_student_with_legacy_transactions(client):
    """Create a student with both legacy (NULL join_code) and new transactions."""
    # Create teacher
    teacher = Admin(
        username="teacher1",
        totp_secret="secret123"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create student
    salt = get_random_salt()
    student = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt,
        username_hash=hash_username("alice_a", salt),
        passphrase_hash=generate_password_hash("alice_pass"),
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()

    join_code = "MATH1A"
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Alice",
        last_initial="A",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt,
        first_half_hash="hash1",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    db.session.commit()

    # Add legacy transaction (NULL join_code) with $100 in checking
    legacy_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=None,  # Legacy transaction without join_code
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Legacy balance'
    )
    
    # Add new transaction with join_code with $50 in checking
    new_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=50.0,
        account_type='checking',
        type='Deposit',
        description='New balance'
    )
    
    db.session.add_all([legacy_tx, new_tx])
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_with_legacy_transactions(client, setup_student_with_legacy_transactions):
    """Test that students can transfer when they have legacy transactions."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Student should have $150 total in checking ($100 legacy + $50 new)
    # Try to transfer $75 from checking to savings
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '75.00',
        'passphrase': 'alice_pass'
    }, follow_redirects=False)
    
    # Should succeed (redirect to dashboard)
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Verify transactions were created
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).limit(2).all()
    
    # Should have 2 new transactions (withdrawal and deposit)
    assert len(transactions) == 2
    
    # Find withdrawal and deposit
    withdrawal = next((tx for tx in transactions if tx.amount < 0), None)
    deposit = next((tx for tx in transactions if tx.amount > 0), None)
    
    assert withdrawal is not None
    assert withdrawal.amount == -75.0
    assert withdrawal.account_type == 'checking'
    
    assert deposit is not None
    assert deposit.amount == 75.0
    assert deposit.account_type == 'savings'


def test_insufficient_funds_with_only_new_transactions(client, setup_student_with_legacy_transactions):
    """Test that insufficient funds check works correctly."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Student has $150 in checking
    # Try to transfer $200 (more than available)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '200.00',
        'passphrase': 'alice_pass'
    }, follow_redirects=True)
    
    # Should fail with insufficient funds error
    assert response.status_code == 200
    assert b'Insufficient checking funds' in response.data


def test_transfer_includes_both_legacy_and_new_in_balance(client, setup_student_with_legacy_transactions):
    """Test that balance calculation includes both legacy and new transactions."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Try to transfer exactly $150 (legacy $100 + new $50)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '150.00',
        'passphrase': 'alice_pass'
    }, follow_redirects=False)
    
    # Should succeed
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
