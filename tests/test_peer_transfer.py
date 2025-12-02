"""
Tests for student-to-student (peer) transfer functionality.

Ensures that peer transfers work correctly with:
- Passphrase verification for security
- Balance checking to prevent overdrafts
- Class isolation (can only send to classmates)
- Transaction recording for both sender and recipient
- Prevention of self-transfers
- Validation of recipient existence
- Amount validation (must be positive)
"""

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import (
    Student, Admin, Transaction, TeacherBlock
)
from app.extensions import db
from hash_utils import get_random_salt, hash_username, hash_username_lookup


@pytest.fixture
def setup_peer_transfer_scenario(client):
    """Create teacher, students in same class for testing peer transfers."""
    # Create teacher
    teacher = Admin(
        username="teacher1",
        totp_secret="secret123"
    )
    db.session.add(teacher)
    db.session.commit()

    # Create two students in the same class
    salt1 = get_random_salt()
    student1 = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt1,
        username_hash=hash_username("alice_a", salt1),
        username_lookup_hash=hash_username_lookup("alice_a"),
        passphrase_hash=generate_password_hash("alice_pass"),
        teacher_id=teacher.id
    )
    
    salt2 = get_random_salt()
    student2 = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt2,
        username_hash=hash_username("bob_b", salt2),
        username_lookup_hash=hash_username_lookup("bob_b"),
        passphrase_hash=generate_password_hash("bob_pass"),
        teacher_id=teacher.id
    )

    # Create student in different class
    salt3 = get_random_salt()
    student3 = Student(
        first_name="Charlie",
        last_initial="C",
        block="Period2",
        salt=salt3,
        username_hash=hash_username("charlie_c", salt3),
        username_lookup_hash=hash_username_lookup("charlie_c"),
        passphrase_hash=generate_password_hash("charlie_pass"),
        teacher_id=teacher.id
    )

    db.session.add_all([student1, student2, student3])
    db.session.commit()

    # Create TeacherBlock entries (claimed seats) with join codes
    join_code_period1 = "MATH1A"
    join_code_period2 = "MATH2B"
    
    seat1 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Alice",
        last_initial="A",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt1,
        first_half_hash="hash1",
        join_code=join_code_period1,
        student_id=student1.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    
    seat2 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Bob",
        last_initial="B",
        last_name_hash_by_part=[],
        dob_sum=2001,
        salt=salt2,
        first_half_hash="hash2",
        join_code=join_code_period1,
        student_id=student2.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    
    seat3 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period2",
        first_name="Charlie",
        last_initial="C",
        last_name_hash_by_part=[],
        dob_sum=2002,
        salt=salt3,
        first_half_hash="hash3",
        join_code=join_code_period2,
        student_id=student3.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )

    db.session.add_all([seat1, seat2, seat3])
    db.session.commit()

    # Give Alice some money in checking account
    initial_tx = Transaction(
        student_id=student1.id,
        teacher_id=teacher.id,
        join_code=join_code_period1,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(initial_tx)
    db.session.commit()

    return {
        'teacher': teacher,
        'student1': student1,
        'student2': student2,
        'student3': student3,
        'join_code_period1': join_code_period1,
        'join_code_period2': join_code_period2
    }


def test_peer_transfer_successful(client, setup_peer_transfer_scenario):
    """Test successful peer transfer between students in same class."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    student2 = data['student2']
    join_code = data['join_code_period1']
    
    # Login as student1
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Send money to student2
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'bob_b',
        'amount': '25.50',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert 'Bob B.' in json_data['message']
    
    # Verify transactions were created
    sender_txs = Transaction.query.filter_by(
        student_id=student1.id,
        type='Transfer',
        join_code=join_code
    ).all()
    
    # Should have one debit transaction
    debit_tx = next((tx for tx in sender_txs if tx.amount < 0), None)
    assert debit_tx is not None
    assert debit_tx.amount == -25.50
    assert 'Bob B.' in debit_tx.description
    
    # Verify recipient transaction
    recipient_txs = Transaction.query.filter_by(
        student_id=student2.id,
        type='Transfer',
        join_code=join_code
    ).all()
    
    credit_tx = next((tx for tx in recipient_txs if tx.amount > 0), None)
    assert credit_tx is not None
    assert credit_tx.amount == 25.50
    assert 'Alice A.' in credit_tx.description


def test_peer_transfer_wrong_passphrase(client, setup_peer_transfer_scenario):
    """Test that peer transfer fails with wrong passphrase."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Attempt transfer with wrong passphrase
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'bob_b',
        'amount': '25.00',
        'passphrase': 'wrong_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'passphrase' in json_data['message'].lower()


def test_peer_transfer_insufficient_balance(client, setup_peer_transfer_scenario):
    """Test that peer transfer fails with insufficient balance."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1 (has $100)
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Attempt to transfer more than available
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'bob_b',
        'amount': '150.00',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'insufficient' in json_data['message'].lower()


def test_peer_transfer_to_self(client, setup_peer_transfer_scenario):
    """Test that students cannot send money to themselves."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Attempt self-transfer
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'alice_a',
        'amount': '10.00',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'yourself' in json_data['message'].lower()


def test_peer_transfer_different_class(client, setup_peer_transfer_scenario):
    """Test that students cannot send money to students in different classes."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1 (Period1)
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Attempt to send to student3 who is in Period2
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'charlie_c',
        'amount': '10.00',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'class' in json_data['message'].lower()


def test_peer_transfer_nonexistent_recipient(client, setup_peer_transfer_scenario):
    """Test that transfer fails for non-existent recipient."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Attempt transfer to non-existent user
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'nonexistent_user',
        'amount': '10.00',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'not found' in json_data['message'].lower()


def test_peer_transfer_invalid_amount(client, setup_peer_transfer_scenario):
    """Test that transfer fails with invalid amounts."""
    data = setup_peer_transfer_scenario
    student1 = data['student1']
    join_code = data['join_code_period1']
    
    # Login as student1
    with client.session_transaction() as sess:
        sess['student_id'] = student1.id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Test zero amount
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'bob_b',
        'amount': '0',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    
    # Test negative amount
    response = client.post('/student/transfer-to-student', data={
        'recipient_username': 'bob_b',
        'amount': '-10.00',
        'passphrase': 'alice_pass'
    })
    
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['status'] == 'error'
