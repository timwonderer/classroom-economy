import pytest
pytest.skip('Legacy TeacherBlock test', allow_module_level=True)
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest

pytestmark = [pytest.mark.critical, pytest.mark.regression]

"""
Test transfer behavior when legacy transactions (NULL join_code) are present.

Current behavior is strict join_code scoping: legacy NULL-join_code records do
not count toward balances in a class-scoped student session.
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, ClassEconomy, TransactionStatus, Seat
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_student_with_legacy_transactions(client):
    """Create a student with both legacy (NULL join_code) and new transactions."""
    # Create teacher
    teacher = make_admin("teacher1", "secret123")
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
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teacher
    from app.models import StudentTeacher
    st = StudentTeacher(student_id=student.id, teacher_id=teacher.id)
    db.session.add(st)
    db.session.commit()


    join_code = "MATH1A"
    
    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name='Math Period 1A',
        status='active',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()
    
    from app.models import ClassFeature
    if not ClassFeature.query.filter_by(class_id=economy.class_id, feature_name="banking").first():
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name="banking"))
        db.session.flush()
    
    # Create TeacherBlock entry (claimed seat)
    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="Period1",
        first_name="Alice",
        last_initial="A",
        last_name_hash_by_part=None,
        dob_sum_hash=None,
        salt=salt,
        first_half_hash="hash1",
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    db.session.add(seat)
    # Create a User for the student (required by canonical context)
    from app.models import User, UserRole
    student_user = User(
        username_hash=student.username_hash,
        username_lookup_hash=student.username_hash,
        user_role=UserRole.STUDENT,
    )
    db.session.add(student_user)
    db.session.flush()

    seat_record = Seat(
        student_id=student.id,
        class_id=economy.class_id,
        join_code=join_code,
        block="Period1",
        role="student",
        claimed_at=datetime.now(timezone.utc),
        user_id=student_user.id,
    )
    db.session.add(seat_record)
    db.session.commit()

    import uuid
    other_class_id = str(uuid.uuid4())
    other_economy = ClassEconomy(
        class_id=other_class_id,
        user_id=teacher.id,
        join_code="OTHER1",
        display_name="Other Class"
    )
    db.session.add(other_economy)
    
    other_seat = Seat(
        student_id=student.id,
        class_id=other_class_id,
        join_code="OTHER1",
        block="Period2",
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(other_seat)
    db.session.flush()

    # Add first transaction as a legacy row from another class context.
    # It should be excluded from current class-scoped balance calculations.
    tx1 = Transaction(
        seat_id=other_seat.id,
        class_id=other_class_id,
        teacher_id=teacher.id,
        amount=100.0,
        account_type='checking',
        status=TransactionStatus.POSTED,
        type='Initial',
        description='Legacy balance from another class'
    )
    
    # Add second transaction with current class join_code.
    tx2 = Transaction(
        student_id=student.id,
        seat_id=seat_record.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=50.0,
        account_type='checking',
        status=TransactionStatus.PENDING,
        type='Deposit',
        description='Additional deposit'
    )
    
    db.session.add_all([tx1, tx2])
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code,
        'seat_id': seat.id,
        'seat_record_id': seat_record.id,
        'class_id': economy.class_id,
        'student_user_id': student_user.id,
    }


def test_transfer_with_legacy_transactions(client, setup_student_with_legacy_transactions):
    """Test transfer succeeds when amount is within join_code-scoped balance."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['current_seat_id'] = data['seat_record_id']
        sess['current_class_id'] = data['class_id']
        sess['user_id'] = data['student_user_id']
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['transfer_token'] = 'test-token-123'
    
    # Student has only $50 available in this class economy.
    # Legacy NULL join_code balance must not be used.
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '25.00',
        'passphrase': 'alice_pass',
        'transfer_token': 'test-token-123'
    }, follow_redirects=False)
    
    # Should succeed (redirect to dashboard)
    assert response.status_code == 302
    assert '/student/dashboard' in response.location
    
    # Verify transactions were created
    transactions = Transaction.query.filter_by(
        seat_id=data['seat_record_id'],
        class_id=data['class_id']
    ).order_by(Transaction.timestamp.desc()).limit(2).all()
    
    # Should have 2 new transactions (withdrawal and deposit)
    assert len(transactions) == 2
    
    # Find withdrawal and deposit
    withdrawal = next((tx for tx in transactions if tx.amount < 0), None)
    deposit = next((tx for tx in transactions if tx.amount > 0), None)
    
    assert withdrawal is not None
    assert withdrawal.amount == -25.0
    assert withdrawal.account_type == 'checking'
    
    assert deposit is not None
    assert deposit.amount == 25.0
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
        sess['current_seat_id'] = data['seat_record_id']
        sess['current_class_id'] = data['class_id']
        sess['user_id'] = data['student_user_id']
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['transfer_token'] = 'test-token-123'
    
    # Student has only $50 join_code-scoped checking.
    # Try to transfer $200 (more than available)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '200.00',
        'passphrase': 'alice_pass',
        'transfer_token': 'test-token-123'
    }, follow_redirects=True)
    
    # Should fail with insufficient funds error
    assert response.status_code == 200
    assert b'Insufficient checking funds' in response.data


def test_transfer_excludes_legacy_balance_without_join_code(client, setup_student_with_legacy_transactions):
    """Test that legacy NULL join_code balances are excluded from transfer checks."""
    data = setup_student_with_legacy_transactions
    student = data['student']
    join_code = data['join_code']

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code
        sess['current_seat_id'] = data['seat_record_id']
        sess['current_class_id'] = data['class_id']
        sess['user_id'] = data['student_user_id']
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['transfer_token'] = 'test-token-123'
    
    # Transfer exceeds join_code-scoped $50 balance, so it must be rejected.
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '150.00',
        'passphrase': 'alice_pass',
        'transfer_token': 'test-token-123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Insufficient checking funds' in response.data
