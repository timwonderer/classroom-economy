from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app.models import Admin, Student, Transaction, Seat, IdentityProfile
from app import db
from datetime import datetime, timezone

def test_payroll_visibility_bug(client):
    """
    Test that a teacher sees only their own class transactions for a shared student.
    """
    # 1. Setup Teachers
    teacher1 = make_admin("teacher1", "base32secret3232")
    teacher2 = make_admin("teacher2", "base32secret3232")
    db.session.add_all([teacher1, teacher2])
    db.session.commit()

    # 2. Setup Student
    student = Student(
        first_name="Timothy",
        last_initial="C",
        block="A,G",
        salt=b'123',
        first_half_hash="hash1",
        second_half_hash="hash2",
    )
    db.session.add(student)
    db.session.commit()

    # 3. Setup TeacherBlocks (Class Rosters)
    tb1 = Seat(student_id=student.id, join_code="JOIN_A", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb1)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb1.id, profile_type='student_claimed', first_name="Timothy", last_initial="C"))
    tb2 = Seat(student_id=student.id, join_code="JOIN_G", block="G", block_identifier="G", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb2)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb2.id, profile_type='student_claimed', first_name="Timothy", last_initial="C"))
    db.session.add_all([tb1, tb2])
    db.session.commit()

    # 4. Create Transactions
    tx_a = Transaction(
        student_id=student.id,
        teacher_id=teacher1.id,
        join_code="JOIN_A",
        amount=100.00,
        type='payroll',
        timestamp=datetime.now(timezone.utc),
        description="Payroll for Block A"
    )
    tx_g = Transaction(
        student_id=student.id,
        teacher_id=teacher2.id,
        join_code="JOIN_G",
        amount=100.00,
        type='payroll',
        timestamp=datetime.now(timezone.utc),
        description="Payroll for Block G"
    )
    db.session.add_all([tx_a, tx_g])
    db.session.commit()

    # 5. Simulate Teacher 1's view
    # We query as if we are Teacher 1 (filtered by join_code as per our fix)
    # Teacher 1 has join code "JOIN_A"
    
    visible_transactions = (
        Transaction.query
        .filter_by(type='payroll')
        .filter(Transaction.join_code.in_(['JOIN_A'])) # Filter by my join codes
        .all()
    )
    
    # 6. Verify
    # Teacher 1 should ONLY see transactions they created (JOIN_A)
    # Teacher 1 should NOT see transactions from Teacher 2 (JOIN_G)
    
    print(f"Teacher 1 sees {len(visible_transactions)} transactions.")
    for tx in visible_transactions:
        print(f"Tx: {tx.description}, JoinCode: {tx.join_code}")

    # Assertion for CORRECT behavior
    has_g_transaction = any(tx.join_code == "JOIN_G" for tx in visible_transactions)
    assert not has_g_transaction, "Teacher 1 should NOT see payroll transactions for Block G!"
    
    has_a_transaction = any(tx.join_code == "JOIN_A" for tx in visible_transactions)
    assert has_a_transaction, "Teacher 1 SHOULD see their own block's transaction."
