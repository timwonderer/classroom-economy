"""
Tests for insurance multi-tenancy scoping by class/join_code.

This test verifies that when a teacher switches between classes on the
Insurance Management page, only the policies, enrollments, and claims
for the selected class are displayed.

Related issue: Insurance class selector was not filtering data properly,
showing all classes' data regardless of selection.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    User,
    UserRole,
    Admin, ClassEconomy, IdentityProfile, Student, StudentBlock, StudentTeacher,
    InsurancePolicy, InsurancePolicyBlock, InsuranceEnrollment, InsuranceClaim,
    Seat,
)
from app.hash_utils import hash_username
from tests.helpers.class_scope import create_class_scope


@pytest.fixture
def teacher_with_two_classes(client):
    """Create a teacher with two class periods, each with a different join_code."""
    # Create teacher
    teacher = make_admin("multi-class-teacher", "test-secret")
    db.session.add(teacher)
    db.session.flush()

    salt = get_random_salt()

    # Create Seat for Period A with join_code JOINA123
    # Auto-injected Canonical User
    student_a_user = User(username_hash=f"auto_{student_a.id}", username_lookup_hash=f"auto_l_{student_a.id}", user_role=UserRole.STUDENT)
    db.session.add(student_a_user)
    db.session.flush()
    tb_a = Seat(join_code="JOINA123", block="A", block_identifier="A", role="student")
    db.session.add(tb_a)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb_a.id, profile_type='student_unclaimed', first_name="Placeholder", last_initial="P"))
    db.session.add(tb_a)

    # Create Seat for Period B with join_code JOINB456
    tb_b = Seat(join_code="JOINB456", block="B", block_identifier="B", role="student")
    db.session.add(tb_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb_b.id, profile_type='student_unclaimed', first_name="Placeholder", last_initial="P"))
    db.session.add(tb_b)

    db.session.commit()
    return teacher


@pytest.fixture
def students_in_two_classes(client, teacher_with_two_classes):
    """Create students in two different class periods."""
    teacher = teacher_with_two_classes
    salt = get_random_salt()

    # Student in Period A
    student_a = Student(
        first_name="Alice",
        last_initial="A",
        block="A",
        salt=salt,
        username_hash=hash_username("alice_a", salt),
        pin_hash="fake-hash"
    )
    db.session.add(student_a)
    db.session.flush()

    # StudentTeacher relationship
    st_a = StudentTeacher(user_id=student_a_user.id, teacher_id=teacher.id)
    db.session.add(st_a)

    # StudentBlock for Period A with join_code JOINA123
    sb_a = StudentBlock(
        user_id=student_a_user.id,
        join_code="JOINA123",
        period="A"
    )
    db.session.add(sb_a)

    # Add transaction to set balance
    from app.models import Transaction
    db.session.add(Transaction(
        user_id=student_a_user.id,join_code="JOINA123",
        amount=100.0,
        type="deposit",
        description="Initial balance",
        account_type="checking"
    ))

    # Student in Period B
    student_b = Student(
        first_name="Bob",
        last_initial="B",
        block="B",
        salt=salt,
        username_hash=hash_username("bob_b", salt),
        pin_hash="fake-hash"
    )
    db.session.add(student_b)
    db.session.flush()

    # StudentTeacher relationship
    st_b = StudentTeacher(user_id=student_b_user.id, teacher_id=teacher.id)
    db.session.add(st_b)

    # StudentBlock for Period B with join_code JOINB456
    sb_b = StudentBlock(
        user_id=student_b_user.id,
        join_code="JOINB456",
        period="B"
    )
    db.session.add(sb_b)

    # Add transaction to set balance
    db.session.add(Transaction(
        user_id=student_b_user.id,join_code="JOINB456",
        amount=200.0,
        type="deposit",
        description="Initial balance",
        account_type="checking"
    ))

    db.session.commit()
    return {'student_a': student_a, 'student_b': student_b}


@pytest.fixture
def policies_for_two_classes(client, teacher_with_two_classes):
    """Create insurance policies, one for each class period."""
    teacher = teacher_with_two_classes

    # Policy for Period A only
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

    # Set policy to be visible only in Period A
    policy_block_a = InsurancePolicyBlock(policy_id=policy_a.id, block="A")
    db.session.add(policy_block_a)

    # Policy for Period B only
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

    # Set policy to be visible only in Period B
    policy_block_b = InsurancePolicyBlock(policy_id=policy_b.id, block="B")
    db.session.add(policy_block_b)

    # Policy for ALL classes (no InsurancePolicyBlock entries)
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

    # Simulate the filtering logic from insurance_management route
    import sqlalchemy as sa
    from sqlalchemy import or_

    selected_block = "A"

    # This should return policy_a (visible in A) and policy_all (visible everywhere)
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

    # Should include policy_a (Period A) and policy_all (no restrictions)
    assert policies['policy_a'].id in policy_ids
    assert policies['policy_all'].id in policy_ids
    # Should NOT include policy_b (Period B only)
    assert policies['policy_b'].id not in policy_ids


def test_insurance_policies_filtered_for_block_b(
    client, teacher_with_two_classes, policies_for_two_classes
):
    """Test that switching to block B shows different policies."""
    teacher = teacher_with_two_classes
    policies = policies_for_two_classes

    import sqlalchemy as sa
    from sqlalchemy import or_

    selected_block = "B"

    # This should return policy_b (visible in B) and policy_all (visible everywhere)
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

    # Should include policy_b (Period B) and policy_all (no restrictions)
    assert policies['policy_b'].id in policy_ids
    assert policies['policy_all'].id in policy_ids
    # Should NOT include policy_a (Period A only)
    assert policies['policy_a'].id not in policy_ids


def test_student_insurance_enrollments_filtered_by_join_code(
    client, teacher_with_two_classes, students_in_two_classes, policies_for_two_classes
):
    """Test that student enrollments are filtered by join_code."""
    students = students_in_two_classes
    policies = policies_for_two_classes

    # Create enrollment for student A in Period A
    seat_a = Seat.query.filter_by(student_id=students['student_a'].id).first()
    seat_b = Seat.query.filter_by(student_id=students['student_b'].id).first()
    assert seat_a is not None
    assert seat_b is not None
    enrollment_a = InsuranceEnrollment(
        seat_id=seat_a.id,
        class_id=seat_a.class_id,
        policy_id=policies['policy_a'].id,
        join_code="JOINA123",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True
    )
    db.session.add(enrollment_a)

    # Create enrollment for student B in Period B
    enrollment_b = InsuranceEnrollment(
        seat_id=seat_b.id,
        class_id=seat_b.class_id,
        policy_id=policies['policy_b'].id,
        join_code="JOINB456",
        status="active",
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        payment_current=True
    )
    db.session.add(enrollment_b)
    db.session.commit()

    # Query enrollments for Period A only
    period_a_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINA123")
        .filter(InsuranceEnrollment.status == "active")
        .all()
    )

    # Should only include enrollment_a
    assert len(period_a_enrollments) == 1
    assert period_a_enrollments[0].student_id == students['student_a'].id

    # Query enrollments for Period B only
    period_b_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINB456")
        .filter(InsuranceEnrollment.status == "active")
        .all()
    )

    # Should only include enrollment_b
    assert len(period_b_enrollments) == 1
    assert period_b_enrollments[0].student_id == students['student_b'].id


def test_claims_filtered_by_join_code(
    client, teacher_with_two_classes, students_in_two_classes, policies_for_two_classes
):
    """Test that insurance claims are filtered by join_code via canonical InsuranceEnrollment."""
    teacher = teacher_with_two_classes
    students = students_in_two_classes
    policies = policies_for_two_classes

    from app.models import ClassEconomy
    class_a = ClassEconomy.query.filter_by(join_code="JOINA123").first()
    class_b = ClassEconomy.query.filter_by(join_code="JOINB456").first()
    if class_a is None:
        class_a = create_class_scope(teacher=teacher, join_code="JOINA123", student=students['student_a'], block="A")
    if class_b is None:
        class_b = create_class_scope(teacher=teacher, join_code="JOINB456", student=students['student_b'], block="B")
    db.session.flush()

    seat_a = Seat.query.filter_by(student_id=students['student_a'].id, class_id=class_a.class_id).first()
    seat_b = Seat.query.filter_by(student_id=students['student_b'].id, class_id=class_b.class_id).first()

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
    teacher = teacher_with_two_classes
    salt = get_random_salt()

    # Add a third class period with no insurance policies
    tb_c = Seat(join_code="JOINC789", block="C", block_identifier="C", role="student")
    db.session.add(tb_c)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb_c.id, profile_type='student_unclaimed', first_name="Placeholder", last_initial="P"))
    db.session.add(tb_c)
    db.session.commit()

    import sqlalchemy as sa
    from sqlalchemy import or_

    selected_block = "C"

    # Query policies for Period C
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

    # Should only include "Universal Coverage" (available to all classes)
    # and NOT the period-specific policies
    assert "Universal Coverage" in policy_titles
    assert "Period A Coverage" not in policy_titles
    assert "Period B Coverage" not in policy_titles

    # Query enrollments for Period C - should be empty
    period_c_enrollments = (
        InsuranceEnrollment.query
        .filter(InsuranceEnrollment.join_code == "JOINC789")
        .all()
    )
    assert len(period_c_enrollments) == 0
