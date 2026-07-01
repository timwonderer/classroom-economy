from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    User,
    UserRole,
    Admin,
    InsuranceEnrollment,
    InsurancePolicy,
    Seat,
    InsuranceEnrollment,
    InsuranceClaim,
    Transaction,
    TransactionStatus,
    StoreItem,
    RentSettings,
    RentItem,
)
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope


@pytest.fixture
def admin_user():
    admin = make_admin("teacher-insurance", "totp-secret")
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
    seat = Seat.query.filter_by(student_id=student_id).first()
    assert seat is not None, f"No seat for student_id={student_id}"
    enrollment = InsuranceEnrollment(
        seat_id=seat.id,
        class_id=seat.class_id,
        policy_id=policy_id,
        join_code=seat.join_code,
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(db.session.get(InsurancePolicy, policy_id))
    db.session.add(enrollment)
    db.session.commit()
    return enrollment


def _create_transaction(student_id, teacher_id, is_void=False):
    tx = Transaction(
        student_id=student_id,amount=-25.0,
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
        enrollment_id=enrollment.id,
        policy_id=policy.id,
        seat_id=enrollment.seat_id,
        class_id=enrollment.class_id,
        join_code=enrollment.join_code,
        incident_date=transaction.timestamp,
        description="Test claim",
        claim_amount=abs(transaction.amount),
        transaction_id=transaction.id,
        status="pending",
    )


def _ensure_admin_class_scope(admin, student, join_code="JOIN-INS-SEC", block="A"):
    from app.models import StudentTeacher

    if not db.session.query(StudentTeacher.id).filter_by(user_id=student_user.id, teacher_id=admin.id).first():
        db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=admin.id))
    if not db.session.query(InsurancePolicy.id).filter_by(teacher_id=admin.id).first():
        pass
    class_row = create_class_scope(teacher=admin, join_code=join_code, student=student, block=block)
    db.session.commit()
    return class_row


def test_duplicate_transaction_claim_blocked(client, test_student, admin_user):
    from app.models import StudentTeacher

    # Create StudentTeacher association for proper scoping
    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

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
    from app.models import StudentTeacher

    # Create StudentTeacher association for proper scoping
    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    tx = _create_transaction(test_student.id, admin_user.id, is_void=True)

    claim = _build_claim(enrollment, policy, test_student.id, tx)
    db.session.add(claim)
    db.session.commit()

    login_admin(client, admin_user.id, "JOIN-INS-SEC")

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


def test_hard_deny_transaction_type_cannot_be_approved(client, test_student, admin_user):
    from app.models import StudentTeacher

    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    rent_tx = Transaction(
        user_id=test_student_user.id,amount=-40.0,
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="Rent Payment",
        description="Rent for Period A",
    )
    db.session.add(rent_tx)
    db.session.commit()

    claim = _build_claim(enrollment, policy, test_student.id, rent_tx)
    db.session.add(claim)
    db.session.commit()

    login_admin(client, admin_user.id, "JOIN-INS-SEC")

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
    assert b"Resolve validation errors before approving or paying out this claim." in response.data


def test_duplicate_reimbursement_for_same_source_and_policy_blocked(client, test_student, admin_user):
    from app.models import StudentTeacher

    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

    policy = _create_policy(admin_user.id)
    source_tx = Transaction(
        user_id=test_student_user.id,amount=-12.0,
        account_type="checking",
        status=TransactionStatus.PENDING,
        type="purchase",
        description="Purchase: Pen",
    )
    db.session.add(source_tx)
    db.session.commit()

    reimbursement_one = Transaction(
        user_id=test_student_user.id,amount=12.0,
        account_type="checking",
        status=TransactionStatus.PENDING,
        type="insurance_reimbursement",
        original_transaction_id=source_tx.id,
        policy_id=policy.id,
        description="Insurance reimbursement #1",
    )
    reimbursement_two = Transaction(
        user_id=test_student_user.id,amount=12.0,
        account_type="checking",
        status=TransactionStatus.PENDING,
        type="insurance_reimbursement",
        original_transaction_id=source_tx.id,
        policy_id=policy.id,
        description="Insurance reimbursement #2",
    )
    db.session.add(reimbursement_one)
    db.session.commit()
    db.session.add(reimbursement_two)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_pending_transaction_cannot_be_approved(client, test_student, admin_user):
    from app.models import StudentTeacher

    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)
    pending_tx = Transaction(
        user_id=test_student_user.id,amount=-20.0,
        account_type="checking",
        status=TransactionStatus.PENDING,
        type="purchase",
        description="Purchase: Notebook",
    )
    db.session.add(pending_tx)
    db.session.commit()

    claim = _build_claim(enrollment, policy, test_student.id, pending_tx)
    db.session.add(claim)
    db.session.commit()

    login_admin(client, admin_user.id, "JOIN-INS-SEC")

    response = client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={"status": "approved", "approved_amount": "", "rejection_reason": "", "admin_notes": ""},
        follow_redirects=True,
    )

    db.session.refresh(claim)
    assert claim.status == "pending"
    assert b"Resolve validation errors before approving or paying out this claim." in response.data


def test_rent_privilege_purchase_cannot_be_approved(client, test_student, admin_user):
    from app.models import StudentTeacher

    st = StudentTeacher(user_id=test_student_user.id, teacher_id=admin_user.id)
    db.session.add(st)
    db.session.commit()
    class_row = _ensure_admin_class_scope(admin_user, test_student)

    policy = _create_policy(admin_user.id)
    enrollment = _enroll_student(test_student.id, policy.id)

    store_item = StoreItem(
        user_id=admin_user.id,
        class_id=class_row.class_id,
        name="Desk Pass",
        price=5.0,
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.flush()

    rent_settings = RentSettings(
        class_id=class_row.class_id,
        is_enabled=True,
        rent_amount=10.0,
    )
    db.session.add(rent_settings)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=rent_settings.id,
            store_item_id=store_item.id,
            name=store_item.name,
            rent_item_type="privilege",
        )
    )

    privilege_purchase = Transaction(
        user_id=test_student_user.id,class_id=class_row.class_id,
        join_code=class_row.join_code,
        amount=-5.0,
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="purchase",
        description="Purchase: Desk Pass",
    )
    db.session.add(privilege_purchase)
    db.session.commit()

    claim = _build_claim(enrollment, policy, test_student.id, privilege_purchase)
    db.session.add(claim)
    db.session.commit()

    login_admin(client, admin_user.id, "JOIN-INS-SEC")

    response = client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={"status": "approved", "approved_amount": "", "rejection_reason": "", "admin_notes": ""},
        follow_redirects=True,
    )

    db.session.refresh(claim)
    assert claim.status == "pending"
    assert b"never eligible" in response.data
