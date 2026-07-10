"""
Tests for insurance multi-tenancy scoping by class/join_code.

This test verifies that when a teacher switches between classes on the
Insurance Management page, only the policies, enrollments, and claims
for the selected class are displayed.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    ClassEconomy,
    InsurancePolicy, InsurancePolicyBlock, InsuranceEnrollment, InsuranceClaim,
    Seat,
)
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_identity


@pytest.fixture
def teacher_with_two_classes(client):
    """Create a teacher with two class periods, each with a different join_code."""
    teacher = make_admin("multi-class-teacher", "test-secret")
    db.session.add(teacher)
    db.session.flush()
    db.session.commit()
    return teacher


@pytest.fixture
def students_in_two_classes(client, teacher_with_two_classes):
    """Create students in two different class periods."""
    teacher = teacher_with_two_classes

    class_a = create_class_scope(teacher_user=teacher, join_code="JOINA123", display_name="A")
    student_a = make_student_identity(class_id=class_a.class_id, first_name="Alice", last_name="A")

    class_b = create_class_scope(teacher_user=teacher, join_code="JOINB456", display_name="B")
    student_b = make_student_identity(class_id=class_b.class_id, first_name="Bob", last_name="B")

    from app.models import Transaction
    seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="student").first()
    seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="student").first()
    db.session.add(Transaction(
        seat_id=seat_a.id, user_id=student_a.user_id, class_id=class_a.class_id,
        join_code="JOINA123", amount=100.0, type="deposit",
        description="Initial balance", account_type="checking",
    ))
    db.session.add(Transaction(
        seat_id=seat_b.id, user_id=student_b.user_id, class_id=class_b.class_id,
        join_code="JOINB456", amount=200.0, type="deposit",
        description="Initial balance", account_type="checking",
    ))
    db.session.commit()
    return {'student_a': student_a, 'student_b': student_b, 'class_a': class_a, 'class_b': class_b}


@pytest.fixture
def policies_for_two_classes(client, teacher_with_two_classes):
    """Create insurance policies, one for each class period."""
    teacher = teacher_with_two_classes

    policy_a = InsurancePolicy(
        policy_code="POLICY-A-001",
        teacher_id=teacher.id,
        title="Period A Coverage",
        description="Coverage only for Period A",
        premium=10.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True
    )
    db.session.add(policy_a)
    db.session.flush()
    db.session.add(InsurancePolicyBlock(policy_id=policy_a.id, block="A"))

    policy_b = InsurancePolicy(
        policy_code="POLICY-B-001",
        teacher_id=teacher.id,
        title="Period B Coverage",
        description="Coverage only for Period B",
        premium=15.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True
    )
    db.session.add(policy_b)
    db.session.flush()
    db.session.add(InsurancePolicyBlock(policy_id=policy_b.id, block="B"))

    policy_all = InsurancePolicy(
        policy_code="POLICY-ALL-001",
        teacher_id=teacher.id,
        title="Universal Coverage",
        description="Available to all classes",
        premium=20.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True
    )
    db.session.add(policy_all)
    db.session.commit()
    return {'policy_a': policy_a, 'policy_b': policy_b, 'policy_all': policy_all}


def test_insurance_policies_filtered_by_selected_block(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that only policies for the selected block are returned."""
    teacher = teacher_with_two_classes
    policies = policies_for_two_classes

    from sqlalchemy import or_
    selected_block = "A"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher.id)
        .outerjoin(InsurancePolicyBlock, InsurancePolicy.id == InsurancePolicyBlock.policy_id)
        .filter(
            or_(
                InsurancePolicyBlock.block == selected_block.upper(),
                ~InsurancePolicy.id.in_(
                    db.session.query(InsurancePolicyBlock.policy_id).distinct()
                )
            )
        )
        .distinct()
        .all()
    )

    policy_ids = [p.id for p in filtered_policies]
    assert policies['policy_a'].id in policy_ids
    assert policies['policy_all'].id in policy_ids
    assert policies['policy_b'].id not in policy_ids


def test_insurance_policies_filtered_for_block_b(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that switching to block B shows different policies."""
    teacher = teacher_with_two_classes
    policies = policies_for_two_classes

    from sqlalchemy import or_
    selected_block = "B"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher.id)
        .outerjoin(InsurancePolicyBlock, InsurancePolicy.id == InsurancePolicyBlock.policy_id)
        .filter(
            or_(
                InsurancePolicyBlock.block == selected_block.upper(),
                ~InsurancePolicy.id.in_(
                    db.session.query(InsurancePolicyBlock.policy_id).distinct()
                )
            )
        )
        .distinct()
        .all()
    )

    policy_ids = [p.id for p in filtered_policies]
    assert policies['policy_b'].id in policy_ids
    assert policies['policy_all'].id in policy_ids
    assert policies['policy_a'].id not in policy_ids


def test_student_insurance_enrollments_filtered_by_class_id(
    client, teacher_with_two_classes, students_in_two_classes, policies_for_two_classes
):
    """Test that student enrollments are filtered by class_id."""
    students = students_in_two_classes
    policies = policies_for_two_classes
    class_a = students['class_a']
    class_b = students['class_b']

    seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="student").first()
    seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="student").first()
    assert seat_a is not None
    assert seat_b is not None

    enrollment_a = InsuranceEnrollment(
        seat_id=seat_a.id,
        class_id=class_a.class_id,
        policy_id=policies['policy_a'].id,
        join_code="JOINA123",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True
    )
    db.session.add(enrollment_a)

    enrollment_b = InsuranceEnrollment(
        seat_id=seat_b.id,
        class_id=class_b.class_id,
        policy_id=policies['policy_b'].id,
        join_code="JOINB456",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True
    )
    db.session.add(enrollment_b)
    db.session.commit()

    period_a_enrollments = (
        InsuranceEnrollment.query
        .filter_by(class_id=class_a.class_id, status="active")
        .all()
    )
    assert len(period_a_enrollments) == 1
    assert period_a_enrollments[0].seat_id == seat_a.id

    period_b_enrollments = (
        InsuranceEnrollment.query
        .filter_by(class_id=class_b.class_id, status="active")
        .all()
    )
    assert len(period_b_enrollments) == 1
    assert period_b_enrollments[0].seat_id == seat_b.id


def test_claims_filtered_by_class_id(
    client, teacher_with_two_classes, students_in_two_classes, policies_for_two_classes
):
    """Test that insurance claims are filtered by class_id."""
    teacher = teacher_with_two_classes
    students = students_in_two_classes
    policies = policies_for_two_classes
    class_a = students['class_a']
    class_b = students['class_b']

    seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="student").first()
    seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="student").first()

    enrollment_a = InsuranceEnrollment(
        seat_id=seat_a.id,
        class_id=class_a.class_id,
        policy_id=policies['policy_a'].id,
        join_code="JOINA123",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=10),
        payment_current=True,
    )
    enrollment_a.freeze_policy_snapshot(policies['policy_a'])
    db.session.add(enrollment_a)
    db.session.flush()

    claim_a = InsuranceClaim(
        enrollment_id=enrollment_a.id,
        policy_id=policies['policy_a'].id,
        seat_id=seat_a.id,
        class_id=class_a.class_id,
        join_code="JOINA123",
        incident_date=datetime.now(timezone.utc) - timedelta(days=1),
        description="Claim from Period A",
        claim_amount=25.0,
        status="pending",
    )
    db.session.add(claim_a)

    enrollment_b = InsuranceEnrollment(
        seat_id=seat_b.id,
        class_id=class_b.class_id,
        policy_id=policies['policy_b'].id,
        join_code="JOINB456",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=10),
        payment_current=True,
    )
    enrollment_b.freeze_policy_snapshot(policies['policy_b'])
    db.session.add(enrollment_b)
    db.session.flush()

    claim_b = InsuranceClaim(
        enrollment_id=enrollment_b.id,
        policy_id=policies['policy_b'].id,
        seat_id=seat_b.id,
        class_id=class_b.class_id,
        join_code="JOINB456",
        incident_date=datetime.now(timezone.utc) - timedelta(days=1),
        description="Claim from Period B",
        claim_amount=30.0,
        status="pending",
    )
    db.session.add(claim_b)
    db.session.commit()

    period_a_claims = InsuranceClaim.query.filter_by(class_id=class_a.class_id).all()
    assert len(period_a_claims) == 1
    assert period_a_claims[0].description == "Claim from Period A"

    period_b_claims = InsuranceClaim.query.filter_by(class_id=class_b.class_id).all()
    assert len(period_b_claims) == 1
    assert period_b_claims[0].description == "Claim from Period B"


def test_no_data_shown_for_class_without_insurance(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that a class with no insurance shows only universal policies."""
    teacher = teacher_with_two_classes
    policies = policies_for_two_classes

    from sqlalchemy import or_
    selected_block = "C"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher.id)
        .outerjoin(InsurancePolicyBlock, InsurancePolicy.id == InsurancePolicyBlock.policy_id)
        .filter(
            or_(
                InsurancePolicyBlock.block == selected_block.upper(),
                ~InsurancePolicy.id.in_(
                    db.session.query(InsurancePolicyBlock.policy_id).distinct()
                )
            )
        )
        .distinct()
        .all()
    )

    policy_titles = [p.title for p in filtered_policies]
    assert "Universal Coverage" in policy_titles
    assert "Period A Coverage" not in policy_titles
    assert "Period B Coverage" not in policy_titles

    period_c_enrollments = InsuranceEnrollment.query.filter_by(join_code="JOINC789").all()
    assert len(period_c_enrollments) == 0
