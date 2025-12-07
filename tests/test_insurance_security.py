import os

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Admin, InsurancePolicy, StudentInsurance, InsuranceClaim, Transaction, Student, TeacherBlock, StudentTeacher
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def admin_user():
    admin = Admin(username="teacher-insurance", totp_secret="totp-secret")
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_policy(admin_id):
    policy = InsurancePolicy(
        policy_code="POLICY-001",
        teacher_id=admin_id,
        title="Test Coverage",
        description="",
        premium=10.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    db.session.add(policy)
    db.session.commit()
    return policy


def _enroll_student(student_id, policy_id):
    enrollment = StudentInsurance(
        student_id=student_id,
        policy_id=policy_id,
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True,
    )
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def _create_transaction(student_id, teacher_id, is_void=False):
    tx = Transaction(
        student_id=student_id,
        teacher_id=teacher_id,
        amount=-25.0,
        account_type="checking",
        description="Test purchase",
        type="purchase",
        is_void=is_void,
    )
    db.session.add(tx)
    db.session.commit()
    return tx


def _build_claim(enrollment, policy, student_id, transaction):
    return InsuranceClaim(
        student_insurance_id=enrollment.id,
        policy_id=policy.id,
        student_id=student_id,
        incident_date=transaction.timestamp,
        description="Test claim",
        claim_amount=abs(transaction.amount),
        transaction_id=transaction.id,
        status="pending",
    )


def _create_student_with_seat(admin, block="A", join_code="JOINA"):
    """Helper to create a student and claimed TeacherBlock seat."""
    salt = get_random_salt()
    student = Student(
        first_name="Policy",
        last_initial="T",
        block=block,
        salt=salt,
        username_hash=hash_username(f"policy_{block.lower()}", salt),
        pin_hash="fake-hash",
        teacher_id=admin.id,
    )
    db.session.add(student)
    db.session.commit()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=admin.id))
    db.session.commit()

    seat = TeacherBlock(
        teacher_id=admin.id,
        block=block,
        class_label=f"Advisory {block}",
        first_name=b"Policy",
        last_initial="T",
        last_name_hash_by_part=['hash'],
        dob_sum=2024,
        salt=os.urandom(16),
        first_half_hash='hash',
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()

    return student, seat


def test_duplicate_transaction_claim_blocked(client, test_student, admin_user):
    test_student.teacher_id = admin_user.id
    db.session.commit()

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    tx = _create_transaction(test_student.id, admin_user.id)

    first_claim = _build_claim(enrollment, policy, test_student.id, tx)
    db.session.add(first_claim)
    db.session.commit()

    duplicate_claim = _build_claim(enrollment, policy, test_student.id, tx)
    db.session.add(duplicate_claim)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
    assert InsuranceClaim.query.filter_by(transaction_id=tx.id).count() == 1


def test_voided_transaction_cannot_be_approved(client, test_student, admin_user, monkeypatch):
    class NaiveDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.utcnow()

    monkeypatch.setattr('app.routes.admin.datetime', NaiveDateTime)
    test_student.teacher_id = admin_user.id
    db.session.add(StudentTeacher(student_id=test_student.id, admin_id=admin_user.id))
    db.session.commit()

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    enrollment.coverage_start_date = None  # Avoid timezone comparison issues in tests
    db.session.commit()
    tx = _create_transaction(test_student.id, admin_user.id, is_void=True)
    tx.timestamp = datetime.now(timezone.utc)
    db.session.commit()

    claim = _build_claim(enrollment, policy, test_student.id, tx)
    claim.incident_date = datetime.now(timezone.utc)
    db.session.add(claim)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_user.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={
            "status": "approved",
            "approved_amount": "",
            "rejection_reason": "",
            "admin_notes": "",
        },
        follow_redirects=True,
    )

    db.session.refresh(claim)
    assert claim.status == "pending"
    assert b"voided" in response.data


def test_insurance_marketplace_filters_by_block(client):
    admin = Admin(username="teacher-blocks", totp_secret="totp-secret")
    db.session.add(admin)
    db.session.commit()

    student, seat = _create_student_with_seat(admin, block="A", join_code="JOINA")

    open_policy = InsurancePolicy(
        policy_code="OPEN-POLICY",
        teacher_id=admin.id,
        title="All Blocks Policy",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    block_a_policy = InsurancePolicy(
        policy_code="BLOCK-A",
        teacher_id=admin.id,
        title="Block A Only",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    block_b_policy = InsurancePolicy(
        policy_code="BLOCK-B",
        teacher_id=admin.id,
        title="Block B Only",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    db.session.add_all([open_policy, block_a_policy, block_b_policy])
    db.session.commit()

    block_a_policy.set_blocks(["A"])
    block_b_policy.set_blocks(["B"])
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = seat.join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = seat.block

    response = client.get('/student/insurance')
    assert response.status_code == 200
    body = response.data

    assert b"All Blocks Policy" in body
    assert b"Block A Only" in body
    assert b"Block B Only" not in body


def test_cannot_purchase_policy_for_other_block(client):
    admin = Admin(username="teacher-blocks2", totp_secret="totp-secret")
    db.session.add(admin)
    db.session.commit()

    student, seat = _create_student_with_seat(admin, block="A", join_code="JOINA2")

    allowed_policy = InsurancePolicy(
        policy_code="ALLOW-A",
        teacher_id=admin.id,
        title="Allowed", 
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    blocked_policy = InsurancePolicy(
        policy_code="BLOCK-ONLY-B",
        teacher_id=admin.id,
        title="Blocked", 
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    db.session.add_all([allowed_policy, blocked_policy])
    db.session.commit()

    allowed_policy.set_blocks(["A"])
    blocked_policy.set_blocks(["B"])
    db.session.commit()

    # Fund the student's checking account for purchase attempts
    deposit = Transaction(
        student_id=student.id,
        teacher_id=admin.id,
        join_code=seat.join_code,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(deposit)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = seat.join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_period'] = seat.block

    response = client.post(
        f"/student/insurance/purchase/{blocked_policy.id}",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"not available for your current class" in response.data
    assert StudentInsurance.query.filter_by(policy_id=blocked_policy.id).count() == 0


def test_admin_insurance_filtering_respects_block_visibility(client):
    admin = Admin(username="admin-policy-filters", totp_secret="totp-secret")
    db.session.add(admin)
    db.session.commit()

    student_a, seat_a = _create_student_with_seat(admin, block="A", join_code="JOINA3")
    student_b, seat_b = _create_student_with_seat(admin, block="B", join_code="JOINB3")

    open_policy = InsurancePolicy(
        policy_code="OPEN-ADMIN",
        teacher_id=admin.id,
        title="Admin All Blocks",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    block_a_policy = InsurancePolicy(
        policy_code="ADMIN-A",
        teacher_id=admin.id,
        title="Admin Block A",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    block_b_policy = InsurancePolicy(
        policy_code="ADMIN-B",
        teacher_id=admin.id,
        title="Admin Block B",
        description="",
        premium=5.0,
        claim_type="transaction_monetary",
        is_monetary=True,
    )
    db.session.add_all([open_policy, block_a_policy, block_b_policy])
    db.session.commit()

    block_a_policy.set_blocks(["A"])
    block_b_policy.set_blocks(["B"])
    db.session.commit()

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    response_a = client.get('/admin/insurance?block=A')
    assert response_a.status_code == 200
    body_a = response_a.data
    assert b"Admin All Blocks" in body_a
    assert b"Admin Block A" in body_a
    assert b"Admin Block B" not in body_a
    assert seat_a.class_label.encode() in body_a

    response_b = client.get('/admin/insurance?block=B')
    assert response_b.status_code == 200
    body_b = response_b.data
    assert b"Admin All Blocks" in body_b
    assert b"Admin Block B" in body_b
    assert b"Admin Block A" not in body_b

    response_all = client.get('/admin/insurance?block=InvalidBlock')
    assert response_all.status_code == 200
    body_all = response_all.data
    assert b"Admin All Blocks" in body_all
    assert b"Admin Block A" in body_all
    assert b"Admin Block B" in body_all
