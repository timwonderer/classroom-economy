"""
Test Obligations Domain reconstruction.

Validates DOM-OBL-001 canonical implementations:
- FEAT-OBLI-001: assess_obligation
- FEAT-OBL-002: advance_bill_cycle
- FEAT-OBL-003: satisfy_obligation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import (
    ObligationAssessment,
    BillCycle,
    User,
    ClassEconomy,
    Seat,
    IdentityProfile,
)
from app.services import obligations_service
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.advance_bill_cycle_feat import execute_advance_bill_cycle
from app.feats.satisfy_obligation_feat import (
    execute_satisfy_obligation_payment,
    execute_satisfy_obligation_waiver,
)
from app.utils.time import utc_now


class TestObligationsServiceReads:
    """Test obligations_service read models."""

    def test_get_assessment_for_correlation_returns_none_when_not_found(self, app):
        """No error on missing correlation."""
        with app.app_context():
            result = obligations_service.get_assessment_for_correlation("nonexistent")
            assert result is None

    def test_get_bill_cycles_returns_empty_list_for_missing_ref(self, app):
        """No error on missing internal_ref."""
        with app.app_context():
            result = obligations_service.get_bill_cycles_for_internal_ref("nonexistent")
            assert result == []

    def test_idempotency_checks_return_false_when_not_found(self, app):
        """Idempotency checks return False for new keys."""
        with app.app_context():
            assert not obligations_service.check_idempotency_assessment("ref", "corr")
            assert not obligations_service.check_idempotency_satisfaction("corr", "PAYMENT")
            assert not obligations_service.check_idempotency_bill_cycle("ref", 1)


class TestAssessObligation:
    """Test FEAT-OBLI-001: Assess Obligation."""

    def test_create_assessment_creates_assessment_event(self, app, create_class_scope):
        """Assess obligation creates immutable ASSESSMENT event."""
        with app.app_context():
            context = create_class_scope()
            seat_id = context['seat_id']
            class_id = context['class_id']

            now = utc_now()
            due_at = now + timedelta(days=30)

            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
                due_at=due_at,
            )

            db.session.commit()

            # Verify row created
            assert assessment.id is not None
            assert assessment.event_type == 'ASSESSMENT'
            assert assessment.obligation_type == 'RENT'
            assert assessment.seat_id == seat_id
            assert assessment.class_id == class_id

            # Verify retrievable by correlation
            retrieved = obligations_service.get_assessment_for_correlation("rent-2026-08-monthly")
            assert retrieved.id == assessment.id

    def test_assess_obligation_idempotent_by_lineage(self, app, create_class_scope):
        """Replaying same assessment returns existing row (idempotent)."""
        with app.app_context():
            context = create_class_scope()
            seat_id = context['seat_id']
            class_id = context['class_id']

            due_at = utc_now() + timedelta(days=30)

            # First call
            first = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
                due_at=due_at,
            )
            db.session.commit()
            first_id = first.id

            # Replay with same lineage
            second = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
                due_at=due_at,
            )
            db.session.commit()

            # Should return same row, not create duplicate
            assert second.id == first_id


class TestAdvanceBillCycle:
    """Test FEAT-OBL-002: Advance Bill Cycle."""

    def test_create_bill_cycle_creates_reminder_state(self, app):
        """Advance bill cycle creates identity-blind successor reminder."""
        with app.app_context():
            now = utc_now()
            cycle_boundary = now + timedelta(days=30)
            next_assessment = cycle_boundary + timedelta(days=1)

            cycle = execute_advance_bill_cycle(
                internal_ref="rent:monthly",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary,
                next_assessment_at=next_assessment,
            )

            db.session.commit()

            # Verify row created
            assert cycle.id is not None
            assert cycle.internal_ref == "rent:monthly"
            assert cycle.cycle_number == 1
            assert cycle.cycle_boundary_at == cycle_boundary

            # Verify retrievable
            retrieved = obligations_service.get_latest_bill_cycle("rent:monthly")
            assert retrieved.id == cycle.id

    def test_advance_bill_cycle_idempotent_by_cycle_number(self, app):
        """Replaying same cycle returns existing row."""
        with app.app_context():
            now = utc_now()
            cycle_boundary = now + timedelta(days=30)
            next_assessment = cycle_boundary + timedelta(days=1)

            first = execute_advance_bill_cycle(
                internal_ref="rent:monthly",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary,
                next_assessment_at=next_assessment,
            )
            db.session.commit()
            first_id = first.id

            # Replay same cycle number
            second = execute_advance_bill_cycle(
                internal_ref="rent:monthly",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary,
                next_assessment_at=next_assessment,
            )
            db.session.commit()

            # Should return same row
            assert second.id == first_id


class TestSatisfyObligation:
    """Test FEAT-OBL-003: Satisfy Obligation."""

    def test_satisfy_obligation_creates_waived_event(self, app, create_class_scope):
        """Waiving rent creates immutable WAIVED event."""
        with app.app_context():
            context = create_class_scope()
            seat_id = context['seat_id']
            class_id = context['class_id']

            # First, create an assessment
            due_at = utc_now() + timedelta(days=30)
            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
                due_at=due_at,
            )
            db.session.commit()

            # Now waive it
            waiver = execute_satisfy_obligation_waiver(
                correlation_id=assessment.correlation_id,
                class_id=class_id,
                seat_id=seat_id,
            )

            db.session.commit()

            # Verify WAIVED event created
            assert waiver.id is not None
            assert waiver.event_type == 'WAIVED'
            assert waiver.correlation_id == assessment.correlation_id
            assert waiver.ledger_transaction_id is None

    def test_waiver_only_for_rent(self, app, create_class_scope):
        """WAIVED cannot be used for non-rent obligations."""
        with app.app_context():
            context = create_class_scope()
            seat_id = context['seat_id']
            class_id = context['class_id']

            # Create insurance assessment
            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="insurance:premium",
                correlation_id="ins-2026-08-premium",
                obligation_type="INSURANCE_PREMIUM",
                due_at=utc_now() + timedelta(days=30),
            )
            db.session.commit()

            # Try to waive (should fail)
            with pytest.raises(ValueError, match="only lawful for RENT"):
                execute_satisfy_obligation_waiver(
                    correlation_id=assessment.correlation_id,
                    class_id=class_id,
                    seat_id=seat_id,
                )
