"""Integration tests for obligation view model rendering with canonical test identity."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import BillCycle, ObligationAssessment, Transaction, TransactionStatus
from app.services.obligation_view_model import build_student_obligation_view, build_class_obligation_summary
from app.feats.base import FEATContext
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_with_seat


@pytest.fixture
def canonical_class_with_student(app):
    """Set up canonical teacher and student using production service layer."""
    with app.app_context():
        # Create teacher through production service
        teacher_seed = seed_canonical_admin("test_teacher")
        teacher = teacher_seed.user
        teacher_id = teacher.id

        # Create class and student through production service
        class_seed = seed_class_with_seat(
            teacher=teacher,
            join_code="TEST123",
            display_name="Test Class",
            section="A",
            student_first_name="Test",
            student_last_name="Student",
        )
        class_id = class_seed.class_row.class_id
        seat_id = class_seed.seat.id

        return {
            'teacher_id': teacher_id,
            'class_id': class_id,
            'seat_id': seat_id,
        }


def test_obligation_view_renders_with_canonical_identity(app, canonical_class_with_student):
    """Test view model rendering with canonical test identity."""
    ids = canonical_class_with_student

    with app.app_context():
        from app.models import Seat, ClassEconomy

        class_id = ids['class_id']
        seat_id = ids['seat_id']

        # Verify canonical identity exists
        seat = db.session.get(Seat, seat_id)
        class_econ = db.session.get(ClassEconomy, class_id)
        assert seat is not None, f"Seat {seat_id} should exist"
        assert class_econ is not None, f"Class {class_id} should exist"

        # Create obligation data in canonical way
        with FEATContext("FEAT-TEST-RENDERING", idempotency_key="test-render-001"):
            now_utc = datetime.now(timezone.utc)

            # Create bill cycle
            bill_cycle = BillCycle(
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Create assessment event (liability)
            assessment = ObligationAssessment(
                correlation_id='test-rent-render-001',
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

            # Create payment transaction
            txn = Transaction(
                seat_id=seat_id,
                actor_seat_id=seat_id,
                target_seat_id=seat_id,
                class_id=class_id,
                amount=Decimal('50.00'),
                status=TransactionStatus.POSTED,
                timestamp=now_utc + timedelta(hours=1),
            )
            db.session.add(txn)
            db.session.flush()

            # Create payment satisfaction event
            payment_event = ObligationAssessment(
                correlation_id='test-rent-render-001',
                seat_id=seat_id,
                class_id=class_id,
                obligation_type='RENT',
                event_type='PAYMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                ledger_transaction_id=txn.id,
                timestamp=now_utc + timedelta(hours=2),
            )
            db.session.add(payment_event)
            db.session.flush()

        # Build view model from canonical identity
        view = build_student_obligation_view(
            seat_id=seat_id,
            class_id=class_id,
            obligation_type='RENT',
        )

        # Verify view model structure
        assert view is not None
        assert view.obligation_type == 'RENT'
        assert view.seat_id == seat_id
        assert view.class_id == class_id

        # Verify current period exists
        assert view.current_period is not None
        assert 'amount_due' in view.current_period
        assert 'amount_paid' in view.current_period
        assert 'balance' in view.current_period
        assert 'is_past_due' in view.current_period
        assert 'days_until_due' in view.current_period

        # Verify payment history captured
        assert len(view.payment_history) > 0
        payment_entries = [p for p in view.payment_history if p['type'] == 'PAYMENT']
        assert len(payment_entries) > 0
        assert payment_entries[0]['amount'] == Decimal('50.00')

        # Verify totals computed
        assert view.totals is not None
        assert 'total_paid_all_time' in view.totals
        assert view.totals['total_paid_all_time'] == Decimal('50.00')


def test_class_summary_renders_with_canonical_identity(app, canonical_class_with_student):
    """Test class summary rendering with canonical test identity."""
    ids = canonical_class_with_student

    with app.app_context():
        from app.models import Seat

        class_id = ids['class_id']
        seat_id = ids['seat_id']
        seat = db.session.get(Seat, seat_id)
        assert seat is not None, f"Seat {seat_id} should exist"

        # Create obligation data
        with FEATContext("FEAT-TEST-SUMMARY-RENDER", idempotency_key="test-summary-render-001"):
            now_utc = datetime.now(timezone.utc)

            # Create bill cycle
            bill_cycle = BillCycle(
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Create assessment
            assessment = ObligationAssessment(
                correlation_id='test-summary-render-001',
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

        # Verify summary structure
        assert summary is not None
        assert summary.class_id == class_id
        assert summary.obligation_type == 'RENT'

        # Verify status breakdown exists
        assert summary.status_breakdown is not None
        assert 'up_to_date' in summary.status_breakdown
        assert 'outstanding' in summary.status_breakdown
        assert 'past_due_grace' in summary.status_breakdown
        assert 'past_due_overdue' in summary.status_breakdown

        # Verify student rows include canonical identity display
        assert len(summary.student_rows) > 0
        row = summary.student_rows[0]
        assert row['seat_id'] == seat_id
        assert 'student_name' in row
        assert row['student_name'] == 'Test Student'  # From canonical identity
        assert 'status' in row
        assert 'amount_due' in row
        assert 'balance' in row


def test_view_model_respects_multi_tenancy(app):
    """Test that view models are scoped by class_id and don't leak cross-class data."""
    with app.app_context():
        # Create two separate class contexts
        teacher_seed = seed_canonical_admin("multi_tenant_teacher")
        teacher = teacher_seed.user
        db.session.flush()

        # Class 1
        class1_seed = seed_class_with_seat(
            teacher=teacher,
            join_code="CLASS1",
            display_name="Class 1",
            student_first_name="Student",
            student_last_name="One",
        )
        class1_id = class1_seed.class_row.class_id
        seat1_id = class1_seed.seat.id
        db.session.flush()

        # Class 2
        class2_seed = seed_class_with_seat(
            teacher=teacher,
            join_code="CLASS2",
            display_name="Class 2",
            student_first_name="Student",
            student_last_name="Two",
        )
        class2_id = class2_seed.class_row.class_id
        seat2_id = class2_seed.seat.id
        db.session.flush()

        # Add obligation data only to Class 1
        with FEATContext("FEAT-TEST-MULTI", idempotency_key="test-multi-tenant-001"):
            now_utc = datetime.now(timezone.utc)

            bill_cycle = BillCycle(
                internal_ref='rent:monthly',
                cycle_number=1,
                cycle_boundary_at=now_utc - timedelta(days=1),
                next_assessment_at=now_utc + timedelta(days=30),
            )
            db.session.add(bill_cycle)
            db.session.flush()

            # Assessment only in Class 1
            assessment = ObligationAssessment(
                correlation_id='test-multi-001',
                seat_id=seat1_id,
                class_id=class1_id,
                obligation_type='RENT',
                event_type='ASSESSMENT',
                internal_ref='rent:monthly',
                bill_cycle_id=bill_cycle.id,
                timestamp=now_utc,
            )
            db.session.add(assessment)
            db.session.flush()

        # Query views for both classes
        view1 = build_student_obligation_view(seat1_id, class1_id, 'RENT')
        view2 = build_student_obligation_view(seat2_id, class2_id, 'RENT')

        # Class 1 should have data
        assert view1 is not None, "Class 1 student should have obligations"
        assert view1.seat_id == seat1_id
        assert view1.class_id == class1_id

        # Class 2 should NOT see Class 1's data
        assert view2 is None, "Class 2 student should not see Class 1 obligations (multi-tenancy violation)"

        # Summary should also respect scoping
        summary1 = build_class_obligation_summary(class1_id, 'RENT')
        summary2 = build_class_obligation_summary(class2_id, 'RENT')

        assert len(summary1.student_rows) > 0
        assert len(summary2.student_rows) == 0
