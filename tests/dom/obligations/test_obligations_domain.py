"""
Test Obligations Domain reconstruction (DOM-OBL-001).

Validates canonical obligation behavior through production code paths using
TEST-IDEN-001 canonical test identities and classroom_initializer.
"""

import pytest

from app.extensions import db
from app.models import ObligationAssessment, BillCycle
from app.services import obligations_service
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.advance_bill_cycle_feat import execute_advance_bill_cycle
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_waiver
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
    CLASS_LEVEL_EVALUATION,
)
from tests.helpers.classroom_initializer import initialize


class _TemporalContext:
    """Minimal context for canonical_temporal_resolver CLASS_LEVEL_EVALUATION."""
    def __init__(self, class_id: str):
        self.class_id = class_id


class TestObligationsServiceReads:
    """Test obligations_service read models (pure reads, no temporal dependency)."""

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
    """Test FEAT-OBL-001: Assess Obligation."""

    def test_create_assessment_creates_assessment_event(self, app):
        """Assess obligation creates immutable ASSESSMENT event per DOM-OBL-001."""
        # Use canonical test identities (TEST-IDEN-001)
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            student = classroom.students[0]
            seat_id = student.seat.id
            class_id = classroom.class_id

            # Create ASSESSMENT event
            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
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

    def test_assess_obligation_idempotent_by_lineage(self, app):
        """Replaying same assessment returns existing row (idempotent per DOM-OBL-001)."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            student = classroom.students[0]
            seat_id = student.seat.id
            class_id = classroom.class_id

            # First call
            assessment1 = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
            )

            db.session.commit()
            id1 = assessment1.id

            # Replay with same parameters
            assessment2 = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
            )

            db.session.commit()

            # Should be same row (idempotent)
            assert assessment2.id == id1


class TestAdvanceBillCycle:
    """Test FEAT-OBL-002: Advance Bill Cycle."""

    def test_create_bill_cycle_creates_reminder_state(self, app):
        """Create bill cycle creates reminder state per DOM-OBL-001."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            from datetime import timedelta
            ctx = _TemporalContext(class_id=classroom.class_id)
            now_eval = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            )
            now_utc = now_eval.canonical_now_utc

            # Bill cycle boundaries: cycle ends 30 days from now, reassessment at 60 days
            cycle_boundary_at = now_utc + timedelta(days=30)
            next_assessment_at = now_utc + timedelta(days=60)

            # Create bill cycle (identity-blind temporal reminder, class-scoped per INV-CORE-000)
            cycle = execute_advance_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="rent:cycle:2026-08",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary_at,
                next_assessment_at=next_assessment_at,
            )

            db.session.commit()

            assert cycle.id is not None
            assert cycle.internal_ref == "rent:cycle:2026-08"
            assert cycle.cycle_number == 1

    def test_advance_bill_cycle_idempotent_by_cycle_number(self, app):
        """Replaying bill cycle returns existing row (idempotent)."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            from datetime import timedelta
            ctx = _TemporalContext(class_id=classroom.class_id)
            now_eval = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            )
            now_utc = now_eval.canonical_now_utc

            cycle_boundary_at = now_utc + timedelta(days=30)
            next_assessment_at = now_utc + timedelta(days=60)

            # First call
            cycle1 = execute_advance_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="rent:cycle:2026-08",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary_at,
                next_assessment_at=next_assessment_at,
            )

            db.session.commit()
            id1 = cycle1.id

            # Replay with same parameters
            cycle2 = execute_advance_bill_cycle(
                class_id=classroom.class_id,
                internal_ref="rent:cycle:2026-08",
                cycle_number=1,
                cycle_boundary_at=cycle_boundary_at,
                next_assessment_at=next_assessment_at,
            )

            db.session.commit()

            # Should be same row (idempotent)
            assert cycle2.id == id1


class TestSatisfyObligation:
    """Test FEAT-OBL-003: Satisfy Obligation (waiver path)."""

    def test_satisfy_obligation_creates_waived_event(self, app):
        """Waiver creates WAIVED event with same correlation_id as ASSESSMENT per DOM-OBL-001."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            student = classroom.students[0]
            seat_id = student.seat.id
            class_id = classroom.class_id

            # Create ASSESSMENT
            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="rent:monthly",
                correlation_id="rent-2026-08-monthly",
                obligation_type="RENT",
            )

            db.session.commit()

            # Now waive it
            waiver = execute_satisfy_obligation_waiver(
                correlation_id=assessment.correlation_id,
                class_id=class_id,
                seat_id=seat_id,
                idempotency_key=f"test:waiver:{assessment.correlation_id}",
            )

            db.session.commit()

            # Verify WAIVED event created
            assert waiver.id is not None
            assert waiver.event_type == 'WAIVED'
            assert waiver.correlation_id == assessment.correlation_id

    def test_waiver_only_for_rent(self, app):
        """Waivers only permitted for RENT obligations (not INSURANCE_PREMIUM)."""
        classroom = initialize("chemistry_p1", app)

        with app.app_context():
            student = classroom.students[0]
            seat_id = student.seat.id
            class_id = classroom.class_id

            # Create INSURANCE_PREMIUM obligation
            assessment = execute_assess_obligation(
                seat_id=seat_id,
                class_id=class_id,
                internal_ref="insurance:monthly",
                correlation_id="insurance-2026-08-monthly",
                obligation_type="INSURANCE_PREMIUM",
            )

            db.session.commit()

            # Attempt waiver on non-RENT should fail
            with pytest.raises(ValueError, match="RENT"):
                execute_satisfy_obligation_waiver(
                    correlation_id=assessment.correlation_id,
                    class_id=class_id,
                    seat_id=seat_id,
                    idempotency_key=f"test:waiver:{assessment.correlation_id}",
                )
