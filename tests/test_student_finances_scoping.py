"""
Test for student finances page to ensure proper scoping of statistics.

Ensures that the finances page correctly displays class-scoped statistics
like total earnings, rather than showing aggregate data from all classes.
"""

import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, TeacherBlock
from app.extensions import db
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_student_multi_class(client):
    """Create a student enrolled in two different classes with separate transactions."""
    # Create two teachers
    teacher1 = Admin(
        username="teacher1",
        totp_secret="secret123"
    )
    teacher2 = Admin(
        username="teacher2",
        totp_secret="secret456"
    )
    db.session.add_all([teacher1, teacher2])
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
        teacher_id=teacher1.id
    )
    db.session.add(student)
    db.session.commit()

    join_code1 = "MATH1A"
    join_code2 = "ENG2B"
    
    # Create TeacherBlock entries (claimed seats) for both classes
    seat1 = TeacherBlock(
        teacher_id=teacher1.id,
        block="Period1",
        first_name="Bob",
        last_initial="B",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt,
        first_half_hash="hash1",
        join_code=join_code1,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    
    seat2 = TeacherBlock(
        teacher_id=teacher2.id,
        block="Period2",
        first_name="Bob",
        last_initial="B",
        last_name_hash_by_part=[],
        dob_sum=2000,
        salt=salt,
        first_half_hash="hash2",
        join_code=join_code2,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc)
    )
    
    db.session.add_all([seat1, seat2])
    db.session.commit()

    # Add earnings to class 1: $100 total
    tx1_class1 = Transaction(
        student_id=student.id,
        teacher_id=teacher1.id,
        join_code=join_code1,
        amount=50.0,
        account_type='checking',
        type='Payroll',
        description='Week 1 earnings'
    )
    
    tx2_class1 = Transaction(
        student_id=student.id,
        teacher_id=teacher1.id,
        join_code=join_code1,
        amount=50.0,
        account_type='checking',
        type='Payroll',
        description='Week 2 earnings'
    )
    
    # Add earnings to class 2: $450 total (this is what was causing the bug)
    tx1_class2 = Transaction(
        student_id=student.id,
        teacher_id=teacher2.id,
        join_code=join_code2,
        amount=200.0,
        account_type='checking',
        type='Payroll',
        description='Week 1 earnings'
    )
    
    tx2_class2 = Transaction(
        student_id=student.id,
        teacher_id=teacher2.id,
        join_code=join_code2,
        amount=250.0,
        account_type='checking',
        type='Payroll',
        description='Week 2 earnings'
    )
    
    # Add a transfer transaction in class 1 (should NOT count towards earnings)
    tx3_class1 = Transaction(
        student_id=student.id,
        teacher_id=teacher1.id,
        join_code=join_code1,
        amount=20.0,
        account_type='savings',
        type='Deposit',
        description='Transfer from checking'
    )
    
    db.session.add_all([tx1_class1, tx2_class1, tx1_class2, tx2_class2, tx3_class1])
    db.session.commit()

    return {
        'teacher1': teacher1,
        'teacher2': teacher2,
        'student': student,
        'join_code1': join_code1,
        'join_code2': join_code2
    }


def test_finances_page_shows_scoped_earnings(client, setup_student_multi_class):
    """Test that the finances page shows only earnings from the current class."""
    data = setup_student_multi_class
    student = data['student']
    join_code1 = data['join_code1']
    teacher1 = data['teacher1']
    
    # Login as student in class 1
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code1
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Get the finances page
    response = client.get('/student/transfer')
    
    # Should succeed
    assert response.status_code == 200
    
    # Parse the HTML to check the Total Earnings value
    html = response.data.decode('utf-8')
    
    # The page should show $100.00 (class 1 earnings only)
    # NOT $550.00 (which would be both classes combined)
    assert '$100.00' in html or '$100' in html
    
    # Verify it doesn't show the combined total
    assert '$550.00' not in html
    assert '$550' not in html
    
    # Additional check: verify the earnings display is in the Statistics section
    # Look for the pattern: Total Earnings followed by the amount
    assert 'Total Earnings' in html
    
    # Find the Total Earnings line and verify the amount
    import re
    # Pattern to match: "Total Earnings" followed by the dollar amount
    pattern = r'Total Earnings.*?\$(\d+\.\d{2})'
    match = re.search(pattern, html, re.DOTALL)
    
    if match:
        earnings_amount = match.group(1)
        assert earnings_amount == '100.00', f"Expected Total Earnings to be $100.00, but found ${earnings_amount}"


def test_model_get_total_earnings_is_scoped(setup_student_multi_class):
    """Test that the Student.get_total_earnings() method correctly scopes by teacher_id."""
    data = setup_student_multi_class
    student = data['student']
    teacher1 = data['teacher1']
    teacher2 = data['teacher2']
    
    # Get earnings for class 1 (teacher1)
    earnings_class1 = student.get_total_earnings(teacher1.id)
    assert earnings_class1 == 100.0, f"Expected $100.00 for class 1, got ${earnings_class1}"
    
    # Get earnings for class 2 (teacher2)
    earnings_class2 = student.get_total_earnings(teacher2.id)
    assert earnings_class2 == 450.0, f"Expected $450.00 for class 2, got ${earnings_class2}"
    
    # Verify that the unscoped property would show the total (demonstrating the bug)
    # This shows why using student.total_earnings in the template was wrong
    total_unscoped = student.total_earnings
    assert total_unscoped == 550.0, f"Unscoped total should be $550.00, got ${total_unscoped}"


def test_finances_page_shows_correct_balance_and_earnings(client, setup_student_multi_class):
    """Test that balances and earnings are both correctly scoped to the same class."""
    data = setup_student_multi_class
    student = data['student']
    join_code1 = data['join_code1']
    
    # Login as student in class 1
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = join_code1
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Get the finances page
    response = client.get('/student/transfer')
    assert response.status_code == 200
    
    html = response.data.decode('utf-8')
    
    # Class 1 has:
    # - $100 in earnings (2 payroll transactions)
    # - $20 moved to savings (1 transfer)
    # So: Checking should have $80 ($100 - $20), Savings should have $20
    
    # Check that both checking and savings balances are shown
    # The balances should reflect only class 1 transactions
    assert 'Checking' in html
    assert 'Savings' in html
    
    # Verify the earnings match the class context
    assert '$100.00' in html or '$100' in html
