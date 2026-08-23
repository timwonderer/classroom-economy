"""Tests for generic obligation view models (StudentObligationView, ClassObligationSummary)."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import (
    User, UserRole, Seat, ClassEconomy, IdentityProfile,
    ObligationAssessment, BillCycle, Transaction, TransactionStatus
)
from app.services.obligation_view_model import build_student_obligation_view, build_class_obligation_summary
from app.feats.base import FEATContext


def setup_test_class_and_students(app):
    """Set up a test class with a student and basic config. Returns IDs."""
    with app.app_context():
        with FEATContext("FEAT-TEST-SETUP", idempotency_key="test-obligation-models"):
            # Create teacher user first (so we can use their ID for class)
            teacher = User(
                username_hash='teacher_hash',
                user_role=UserRole.TEACHER,
            )
            db.session.add(teacher)
            db.session.flush()

            # Create class
            class_econ = ClassEconomy(
                class_id='test-class-001',
                section='A',
                display_name='Test Class',
                teacher_user_id=teacher.id,
                join_code='TEST123',
            )
            db.session.add(class_econ)
            db.session.flush()

            # Create student user
            student_user = User(
                username_hash='student_hash',
                user_role=UserRole.STUDENT,
            )
            db.session.add(student_user)
            db.session.flush()

            # Create seat
            seat = Seat(
                user_id=student_user.id,
                class_id=class_econ.class_id,
            )
            db.session.add(seat)
            db.session.flush()

            # Create identity profile for student
            profile = IdentityProfile(
                seat_id=seat.id,
                first_name='Test',
                last_name='Student',
                profile_type='student',
                class_id=class_econ.class_id,
            )
            db.session.add(profile)
            db.session.flush()

            # Save IDs for later retrieval
            teacher_id = teacher.id
            class_id = class_econ.class_id
            student_id = student_user.id
            seat_id = seat.id

        # Return IDs (entities are detached after FEATContext)
        return {
            'class_id': class_id,
            'teacher_id': teacher_id,
            'student_id': student_id,
            'seat_id': seat_id,
        }


def test_build_student_obligation_view_no_assessments(app):
    """Test that view returns None when no assessments exist."""
    ids = setup_test_class_and_students(app)

    with app.app_context():
        view = build_student_obligation_view(
            seat_id=ids['seat_id'],
            class_id=ids['class_id'],
            obligation_type='RENT',
        )

        assert view is None, "Should return None when no assessments exist"


def test_build_student_obligation_view_with_assessment(app):
    """Test view with single RENT assessment and no payments."""
    ids = setup_test_class_and_students(app)

    with app.app_context():
        class_id = ids['class_id']
        seat_id = ids['seat_id']

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="test-assessment-001"):
            # Create bill cycle (class_id required per INV-CORE-000 multi-tenancy)
            now_utc = datetime.now(timezone.utc)
            bill_cycle = BillCycle(
                class_id=class_id,
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Create ASSESSMENT event
            assessment = ObligationAssessment(
                correlation_id='test-rent-liability-001',
                seat_id=seat_id,
                class_id=class_id,
                obligation_type='RENT',
                event_type='ASSESSMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                timestamp=now_utc,
            )
            db.session.add(assessment)
            db.session.flush()

        # Build view
        view = build_student_obligation_view(
            seat_id=seat_id,
            class_id=class_id,
            obligation_type='RENT',
        )

        assert view is not None
        assert view.obligation_type == 'RENT'
        assert view.seat_id == seat_id
        assert view.class_id == class_id

        # Current period should exist
        assert view.current_period is not None
        # NOTE: amount_due is 0 because schema doesn't store amounts on assessment events (per DOM-OBL-001 v2.5)
        # amounts come from PolicyVersion or ClassConfiguration
        assert view.current_period['amount_due'] == Decimal('0.00')
        assert view.current_period['amount_paid'] == Decimal('0.00')
        assert view.current_period['balance'] == Decimal('0.00')
        assert view.current_period['is_paid'] is True  # 0 balance means paid
        assert view.current_period['is_waived'] is False


def test_build_student_obligation_view_with_payment(app):
    """Test view with assessment and partial payment."""
    ids = setup_test_class_and_students(app)

    with app.app_context():
        class_id = ids['class_id']
        seat_id = ids['seat_id']

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="test-payment-001"):
            # Create bill cycle (class_id required per INV-CORE-000 multi-tenancy)
            now_utc = datetime.now(timezone.utc)
            bill_cycle = BillCycle(
                class_id=class_id,
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Create ASSESSMENT event
            assessment = ObligationAssessment(
                correlation_id='test-rent-payment-001',
                seat_id=seat_id,
                class_id=class_id,
                obligation_type='RENT',
                event_type='ASSESSMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                timestamp=now_utc,
            )
            db.session.add(assessment)
            db.session.flush()

            # Create a Transaction for the payment
            txn = Transaction(
                seat_id=seat_id,
                actor_seat_id=seat_id,
                target_seat_id=seat_id,
                class_id=class_id,
                amount=Decimal('60.00'),
                status=TransactionStatus.POSTED,
                timestamp=now_utc,
            )
            db.session.add(txn)
            db.session.flush()

            # Create PAYMENT event linking to transaction
            payment_event = ObligationAssessment(
                correlation_id='test-rent-payment-001',  # Same as assessment
                seat_id=seat_id,
                class_id=class_id,
                obligation_type='RENT',
                event_type='PAYMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                ledger_transaction_id=txn.id,
                timestamp=now_utc + timedelta(hours=1),
            )
            db.session.add(payment_event)
            db.session.flush()

        # Build view
        view = build_student_obligation_view(
            seat_id=seat_id,
            class_id=class_id,
            obligation_type='RENT',
        )

        assert view is not None
        # NOTE: amount_due is 0 because schema doesn't store amounts on assessment events
        assert view.current_period['amount_due'] == Decimal('0.00')
        assert view.current_period['amount_paid'] == Decimal('60.00')
        assert view.current_period['balance'] == Decimal('-60.00')  # paid more than due
        assert view.current_period['is_paid'] is True


def test_build_class_obligation_summary_no_students(app):
    """Test class summary with no students."""
    ids = setup_test_class_and_students(app)

    with app.app_context():
        summary = build_class_obligation_summary(
            class_id=ids['class_id'],
            obligation_type='RENT',
        )

        assert summary is not None
        assert summary.class_id == ids['class_id']
        assert summary.obligation_type == 'RENT'
        assert summary.status_breakdown == {
            'up_to_date': 0,
            'outstanding': 0,
            'past_due_grace': 0,
            'past_due_overdue': 0,
        }
        assert len(summary.student_rows) == 0


def test_build_class_obligation_summary_with_obligations(app):
    """Test class summary with multiple students and obligations."""
    ids = setup_test_class_and_students(app)

    with app.app_context():
        class_id = ids['class_id']
        seat_id = ids['seat_id']

        with FEATContext("FEAT-TEST-SETUP", idempotency_key="test-summary-001"):
            # Create bill cycle (class_id required per INV-CORE-000 multi-tenancy)
            now_utc = datetime.now(timezone.utc)
            bill_cycle = BillCycle(
                class_id=class_id,
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Create ASSESSMENT event
            assessment = ObligationAssessment(
                correlation_id='test-class-summary-001',
                seat_id=seat_id,
                class_id=class_id,
                obligation_type='RENT',
                event_type='ASSESSMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                timestamp=now_utc,
            )
            db.session.add(assessment)
            db.session.flush()

        # Build class summary
        summary = build_class_obligation_summary(
            class_id=class_id,
            obligation_type='RENT',
        )

        assert summary is not None
        assert len(summary.student_rows) == 1
        row = summary.student_rows[0]
        assert row['seat_id'] == seat_id
        assert row['student_name'] == 'Test Student'  # first_name + last_name
        # NOTE: amount_due is 0 because schema doesn't store amounts on assessment events
        assert row['amount_due'] == Decimal('0.00')
        assert row['balance'] == Decimal('0.00')
        # Status should be 'up_to_date' since balance is 0 (considered paid)
        assert row['status'] == 'up_to_date'
