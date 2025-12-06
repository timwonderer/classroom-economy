import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Admin, InsurancePolicy, StudentInsurance, InsuranceClaim, Transaction


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


def test_voided_transaction_cannot_be_approved(client, test_student, admin_user):
    test_student.teacher_id = admin_user.id
    db.session.commit()

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    tx = _create_transaction(test_student.id, admin_user.id, is_void=True)

    claim = _build_claim(enrollment, policy, test_student.id, tx)
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
