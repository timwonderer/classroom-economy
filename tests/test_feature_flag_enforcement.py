"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, TeacherBlock, FeatureSettings
from app.extensions import db
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
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
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt,
        username_hash=hash_username("bob_b", salt),
        passphrase_hash=generate_password_hash("bob_pass"),
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()

    join_code = "MATH1B"
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Bob",
        last_initial="B",
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

    # Add some money to checking account
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.commit()

    # Create feature settings with banking disabled
    feature_settings = FeatureSettings(
        teacher_id=teacher.id,
        block="Period1",
        banking_enabled=False,  # Disable banking
        payroll_enabled=False,  # Disable payroll
        insurance_enabled=True,
        rent_enabled=True,
        hall_pass_enabled=True,
        store_enabled=True
    )
    db.session.add(feature_settings)
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer route is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to access transfer page (GET)
    response = client.get('/student/transfer', follow_redirects=False)
    
    # Should redirect to dashboard
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Follow redirect and check for warning message
    response = client.get('/student/transfer', follow_redirects=True)
    assert response.status_code == 200
    assert b'banking feature is currently disabled' in response.data


def test_transfer_post_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer POST is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to submit a transfer (POST)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'bob_pass'
    }, follow_redirects=False)
    
    # Should redirect to dashboard
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Verify no transactions were created
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code,
        type='Withdrawal'
    ).all()
    
    # Should only have the initial transaction, no transfer
    all_transactions = Transaction.query.filter_by(student_id=student.id).all()
    assert len(all_transactions) == 1
    assert all_transactions[0].type == 'Initial'


def test_payroll_blocked_when_payroll_disabled(client, setup_student_with_disabled_banking):
    """Test that payroll route is blocked when payroll is disabled."""
    data = setup_student_with_disabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period1'
    
    # Try to access payroll page
    response = client.get('/student/payroll', follow_redirects=False)
    
    # Should redirect to dashboard
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Follow redirect and check for warning message
    response = client.get('/student/payroll', follow_redirects=True)
    assert response.status_code == 200
    assert b'payroll feature is currently disabled' in response.data


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    # Create teacher
    teacher = Admin(
        username="teacher2",
        totp_secret="secret456"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create student
    salt = get_random_salt()
    student = Student(
        first_name="Carol",
        last_initial="C",
        block="Period2",
        salt=salt,
        username_hash=hash_username("carol_c", salt),
        passphrase_hash=generate_password_hash("carol_pass"),
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()

    join_code = "MATH2C"
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period2",
        first_name="Carol",
        last_initial="C",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt,
        first_half_hash="hash2",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    db.session.commit()

    # Add some money to checking account
    tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.commit()

    # Create feature settings with banking ENABLED
    feature_settings = FeatureSettings(
        teacher_id=teacher.id,
        block="Period2",
        banking_enabled=True,  # Enable banking
        payroll_enabled=True,  # Enable payroll
        insurance_enabled=True,
        rent_enabled=True,
        hall_pass_enabled=True,
        store_enabled=True
    )
    db.session.add(feature_settings)
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code
    }


def test_transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer works normally when banking is enabled."""
    data = setup_student_with_enabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period2'
    
    # Access transfer page (GET) should work
    response = client.get('/student/transfer', follow_redirects=False)
    assert response.status_code == 200
    assert b'Transfer Details' in response.data or b'Finances' in response.data
    
    # Submit a transfer (POST) should work
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'carol_pass'
    }, follow_redirects=False)
    
    # Should redirect to dashboard (success)
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Verify transactions were created
    transactions = Transaction.query.filter_by(
        student_id=student.id,
        join_code=join_code
    ).order_by(Transaction.timestamp.desc()).limit(2).all()
    
    # Should have withdrawal and deposit from transfer
    assert len(transactions) == 2
    withdrawal = next((tx for tx in transactions if tx.amount < 0), None)
    deposit = next((tx for tx in transactions if tx.amount > 0 and tx.type == 'Deposit'), None)
    
    assert withdrawal is not None
    assert withdrawal.amount == -50.0
    assert deposit is not None
    assert deposit.amount == 50.0


def test_payroll_allowed_when_payroll_enabled(client, setup_student_with_enabled_banking):
    """Test that payroll works normally when payroll is enabled."""
    data = setup_student_with_enabled_banking
    student = data['student']
    join_code = data['join_code']
    
    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = 'Period2'
    
    # Access payroll page should work
    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data
