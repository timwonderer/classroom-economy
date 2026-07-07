from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from app.services import obligations_service
from app.models import (
    User,
    UserRole,
    Admin,
    ClassEconomy,
    InsurancePolicy,
    InsuranceClaim,
    ObligationAssessment,
    Seat,
    InsuranceEnrollment,
    Transaction,
    TransactionStatus,
)
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope


def _create_policy(admin_id: int, *, title: str = "Snapshot Coverage", max_claim_amount=Decimal("75.00")):
    policy = InsurancePolicy(
        policy_code=f"POL-{title[:3].upper()}-{admin_id}",
        teacher_id=admin_id,
        title=title,
        description="Base policy",
        premium=Decimal("10.00"),
        claim_type="transaction_monetary",
        is_monetary=True,
        max_claim_amount=max_claim_amount,
        max_claims_period="month",
        claim_time_limit_days=30,
        is_active=True,
    )
    db.session.add(policy)
    db.session.commit()
    return policy


def test_insurance_policy_version_increments_on_edit(client):
    admin = make_admin("policy-version-admin", "secret")
    db.session.add(admin)
    db.session.commit()

    policy = _create_policy(admin.id)
    assert policy.version_number == 1

    policy.title = "Snapshot Coverage Updated"
    db.session.commit()

    db.session.refresh(policy)
    assert policy.version_number == 2


def test_student_insurance_keeps_frozen_snapshot_after_policy_edit(client, test_student):
    admin = make_admin("snapshot-admin", "secret")
    db.session.add(admin)
    db.session.commit()

    policy = _create_policy(admin.id, title="Original Policy", max_claim_amount=Decimal("42.00"))

    class_row = create_class_scope(
        teacher=admin,
        student=test_student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=False,
    )
    seat = Seat.query.filter_by(class_id=class_row.class_id, role="student").first()
    assert seat is not None
    _snap_class = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
    enrollment = InsuranceEnrollment(
        seat_id=seat.id,
        class_id=seat.class_id,
        policy_id=policy.id,
        status="active",
        purchase_date=datetime.now(timezone.utc),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)
    db.session.commit()

    policy.title = "Mutated Template Title"
    policy.description = "Mutated template description"
    policy.max_claim_amount = Decimal("999.00")
    policy.max_claims_count = 99
    policy.claim_time_limit_days = 5
    db.session.commit()

    db.session.refresh(enrollment)

    assert enrollment.contract_title == "Original Policy"
    assert enrollment.contract_description == "Base policy"
    assert enrollment.contract_max_claim_amount == Decimal("42.00")
    assert enrollment.contract_claim_time_limit_days == 30
    assert enrollment.policy_version == 1


def test_admin_claim_approval_uses_frozen_claim_cap(client, test_student):
    admin = make_admin("snapshot-claim-admin", "secret")
    db.session.add(admin)
    db.session.flush()

    db.session.commit()
    class_row = create_class_scope(teacher=admin, student=test_student, block="A")
    db.session.commit()

    policy = _create_policy(admin.id, title="Claim Cap Policy", max_claim_amount=Decimal("100.00"))

    student_seat = Seat.query.filter_by(class_id=class_row.class_id, role="student").first()
    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert student_seat is not None, "test_student must have a seat (created by create_class_scope)"
    assert teacher_seat is not None, "teacher must have a seat (created by create_class_scope)"

    enrollment = InsuranceEnrollment(
        seat_id=student_seat.id,
        class_id=student_seat.class_id,
        policy_id=policy.id,
        status="active",
        purchase_date=datetime.now(timezone.utc) - timedelta(days=10),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=9),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    enrollment.frozen_max_claim_amount = Decimal("20.00")
    db.session.add(enrollment)
    db.session.flush()

    tx = Transaction(
        user_id=test_student_user.id,
        amount=Decimal("-50.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="fine",
        description="Fine: Lost calculator",
    )
    db.session.add(tx)
    db.session.flush()

    claim = obligations_service.record_insurance_claim(
        enrollment_id=enrollment.id,
        policy_id=policy.id,
        seat_id=enrollment.seat_id,
        class_id=enrollment.class_id,
        incident_date=tx.timestamp,
        description="Need reimbursement",
        claim_amount=Decimal("50.00"),
        claim_item=None,
        comments=None,
        transaction_id=tx.id,
    )
    db.session.commit()

    obligations_service.apply_claim_resolution(
        claim,
        status="approved",
        teacher_notes="",
        rejection_reason="",
        processed_by_user_id=admin.id,
        processed_at=tx.timestamp,
        approved_amount=Decimal("20.00"),
    )
    db.session.commit()

    db.session.refresh(claim)
    assert claim.status == "approved"
    assert claim.approved_amount == Decimal("20.00")

    assessment = ObligationAssessment.query.filter_by(
        seat_id=claim.seat_id,
        class_id=claim.class_id,
        cycle_idempotency_key=f"insurance-claim:{claim.id}",
    ).one()
    assert assessment.obligation_type == "INSURANCE_CLAIM"
    assert assessment.amount_snap == Decimal("50.00")
    assert assessment.lifecycle is not None
    assert assessment.lifecycle.status == "PAID"
    assert assessment.satisfaction is not None
    assert assessment.satisfaction.amount_paid == Decimal("20.00")
