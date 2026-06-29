"""
Tests for insurance multi-tenancy scoping by class/join_code.

This test verifies that when a teacher switches between classes on the
Insurance Management page, only the policies, enrollments, and claims
for the selected class are displayed.

Related issue: Insurance class selector was not filtering data properly,
showing all classes' data regardless of selection.
"""

from tests.helpers.v2_fixtures import make_admin
import pytest
from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    Admin, ClassEconomy, IdentityProfile,
    InsurancePolicy, InsurancePolicyBlock, InsuranceEnrollment, InsuranceClaim,
    Seat,
)
from tests.helpers.class_scope import create_class_scope, make_student_seat


@pytest.fixture
def teacher_with_two_classes(client):
    """Create a teacher with two class periods, each with a different join_code."""
    teacher = make_admin("multi-class-teacher", "test-secret")
    db.session.add(teacher)
    db.session.flush()

    # Use create_class_scope for canonical v2 class creation.
    # create_class_scope auto-creates a User; class_row.user_id holds that User id.
    class_a = create_class_scope(teacher=teacher, join_code="JOINA123", block="A")
    class_b = create_class_scope(teacher=teacher, join_code="JOINB456", block="B")
    db.session.commit()
    return teacher, class_a, class_b


@pytest.fixture
def seats_in_two_classes(client, teacher_with_two_classes):
    """Create student seats in two different class periods."""
    teacher, class_a, class_b = teacher_with_two_classes

    seat_a = make_student_seat(
        class_id=class_a.class_id,
        join_code="JOINA123",
        block="A",
        first_name="Alice",
        last_name="A",
    )
    seat_b = make_student_seat(
        class_id=class_b.class_id,
        join_code="JOINB456",
        block="B",
        first_name="Bob",
        last_name="B",
    )
    db.session.commit()
    return {'seat_a': seat_a, 'seat_b': seat_b}


@pytest.fixture
def policies_for_two_classes(client, teacher_with_two_classes):
    """Create insurance policies, one for each class period."""
    teacher, class_a, class_b = teacher_with_two_classes
    # InsurancePolicy.teacher_id is FK to users.id; class_row.user_id is the auto-created User.
    teacher_user_id = class_a.user_id

    # Policy for Period A only
    policy_a = InsurancePolicy(
        policy_code="POLICY-A-001",
        teacher_id=teacher_user_id,
        class_id=class_a.class_id,
        join_code="JOINA123",
        title="Period A Coverage",
        description="Coverage only for Period A",
        premium=10.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True,
    )
    db.session.add(policy_a)
    db.session.flush()

    policy_block_a = InsurancePolicyBlock(policy_id=policy_a.id, block="A",
                                          class_id=class_a.class_id, join_code="JOINA123")
    db.session.add(policy_block_a)

    # Policy for Period B only
    policy_b = InsurancePolicy(
        policy_code="POLICY-B-001",
        teacher_id=teacher_user_id,
        class_id=class_b.class_id,
        join_code="JOINB456",
        title="Period B Coverage",
        description="Coverage only for Period B",
        premium=15.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True,
    )
    db.session.add(policy_b)
    db.session.flush()

    policy_block_b = InsurancePolicyBlock(policy_id=policy_b.id, block="B",
                                          class_id=class_b.class_id, join_code="JOINB456")
    db.session.add(policy_block_b)

    # Policy for ALL classes (no InsurancePolicyBlock entries)
    policy_all = InsurancePolicy(
        policy_code="POLICY-ALL-001",
        teacher_id=teacher_user_id,
        title="Universal Coverage",
        description="Available to all classes",
        premium=20.0,
        claim_type="transaction_monetary",
        is_monetary=True,
        is_active=True,
    )
    db.session.add(policy_all)
    db.session.commit()
    return {'policy_a': policy_a, 'policy_b': policy_b, 'policy_all': policy_all}


def test_insurance_policies_filtered_by_selected_block(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that only policies for the selected block are returned."""
    teacher, class_a, class_b = teacher_with_two_classes
    teacher_user_id = class_a.user_id
    policies = policies_for_two_classes

    from sqlalchemy import or_

    selected_block = "A"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher_user_id)
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
    teacher, class_a, class_b = teacher_with_two_classes
    teacher_user_id = class_a.user_id
    policies = policies_for_two_classes

    from sqlalchemy import or_

    selected_block = "B"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher_user_id)
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


def test_student_insurance_enrollments_filtered_by_join_code(
    client, teacher_with_two_classes, seats_in_two_classes, policies_for_two_classes
):
    """Test that student enrollments are filtered by join_code."""
    seats = seats_in_two_classes
    policies = policies_for_two_classes

    seat_a = seats['seat_a']
    seat_b = seats['seat_b']

    enrollment_a = InsuranceEnrollment(
        seat_id=seat_a.id,
        class_id=seat_a.class_id,
        policy_id=policies['policy_a'].id,
        join_code="JOINA123",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True,
    )
    enrollment_a.freeze_policy_snapshot(policies['policy_a'])
    db.session.add(enrollment_a)

    enrollment_b = InsuranceEnrollment(
        seat_id=seat_b.id,
        class_id=seat_b.class_id,
        policy_id=policies['policy_b'].id,
        join_code="JOINB456",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True,
    )
    enrollment_b.freeze_policy_snapshot(policies['policy_b'])
    db.session.add(enrollment_b)
    db.session.commit()

    period_a_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINA123")
        .filter(InsuranceEnrollment.status == "active")
        .all()
    )

    assert len(period_a_enrollments) == 1
    assert period_a_enrollments[0].seat_id == seat_a.id

    period_b_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINB456")
        .filter(InsuranceEnrollment.status == "active")
        .all()
    )

    assert len(period_b_enrollments) == 1
    assert period_b_enrollments[0].seat_id == seat_b.id


def test_claims_filtered_by_join_code(
    client, teacher_with_two_classes, seats_in_two_classes, policies_for_two_classes
):
    """Test that insurance claims are filtered by join_code via canonical InsuranceEnrollment."""
    teacher, class_a, class_b = teacher_with_two_classes
    seats = seats_in_two_classes
    policies = policies_for_two_classes

    seat_a = seats['seat_a']
    seat_b = seats['seat_b']

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

    period_a_claims = (
        InsuranceClaim.query
        .join(InsuranceEnrollment, InsuranceClaim.enrollment_id == InsuranceEnrollment.id)
        .filter(InsuranceEnrollment.join_code == "JOINA123")
        .all()
    )

    assert len(period_a_claims) == 1
    assert period_a_claims[0].description == "Claim from Period A"

    period_b_claims = (
        InsuranceClaim.query
        .join(InsuranceEnrollment, InsuranceClaim.enrollment_id == InsuranceEnrollment.id)
        .filter(InsuranceEnrollment.join_code == "JOINB456")
        .all()
    )

    assert len(period_b_claims) == 1
    assert period_b_claims[0].description == "Claim from Period B"


def test_no_data_shown_for_class_without_insurance(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that switching to a class with no insurance shows empty data."""
    teacher, class_a, class_b = teacher_with_two_classes
    teacher_user_id = class_a.user_id
    policies = policies_for_two_classes

    # Add a third class period with no insurance policies
    class_c = create_class_scope(teacher=teacher, join_code="JOINC789", block="C")
    db.session.commit()

    from sqlalchemy import or_

    selected_block = "C"

    filtered_policies = (
        InsurancePolicy.query
        .filter_by(teacher_id=teacher_user_id)
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

    period_c_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINC789")
        .all()
    )
    assert len(period_c_enrollments) == 0
