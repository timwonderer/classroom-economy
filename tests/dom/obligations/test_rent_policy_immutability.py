"""Rent policy definitions are immutable and append-only (DOM-POL-001 §VI.0/§VI.1).

Regression coverage for blocker **B1**.

``ObligationAssessment`` has no amount column. The amount a student owes for a
cycle is resolved at read time from the ``rent_settings`` row addressed by the
``policy_uuid`` the assessment froze at creation. That freeze was already wired
end to end — ``reconcile_rent`` stamps ``settings.policy_uuid`` onto every new
``BillCycle`` and every new ``ObligationAssessment``. It was inert, because
``rent_settings`` was a mutable singleton (``class_id`` was UNIQUE and the admin
handler reassigned fields on the fetched row). Rewriting the row rewrote what
every already-assessed historical cycle said the student owed.

These tests fail against the pre-fix commit: there, a rent change from 50 to 200
retroactively reprices cycle 1's closed assessment to 200.

The invariant under test, stated positively: *a rent submission is a new
contract, and the contracts already in force keep their terms.*
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.models import ObligationAssessment, RentSettings
from app.services import obligations_service
from app.services.admin_settings_service import supersede_rent_settings
from app.services.class_configuration_query_service import get_rent_settings
from tests.helpers.class_domain import customize_rent_settings, enable_class_feature
from tests.helpers.classroom_initializer import initialize


_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_INITIAL = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_BEFORE_BOUNDARY = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _setup_rent_class(classroom, rent_amount="50.00"):
    """Enable rent on a deterministic monthly schedule at ``rent_amount``."""
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    return customize_rent_settings(
        classroom.class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE,
        grace_period_days=3,
        rent_amount=Decimal(rent_amount),
        late_penalty_amount=Decimal("0.00"),
    )


def _rent_assessments(class_id):
    return (
        ObligationAssessment.query.filter_by(
            class_id=class_id, obligation_type="RENT", event_type="ASSESSMENT"
        )
        .order_by(ObligationAssessment.id.asc())
        .all()
    )


class TestRentPolicyIsAppendOnly:
    """The repository accumulates versions; it does not overwrite them."""

    def test_supersede_mints_a_new_row_and_retires_the_predecessor(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            original = _setup_rent_class(classroom, rent_amount="50.00")
            original_uuid = original.policy_uuid

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="rent:raise"):
                successor = supersede_rent_settings(
                    class_id=classroom.class_id,
                    updates={"rent_amount": Decimal("200.00")},
                )

            # A new version, not an edit.
            assert successor.policy_uuid != original_uuid
            assert successor.rent_amount == Decimal("200.00")

            # The predecessor is still there, still saying 50.
            db.session.refresh(original)
            assert original.rent_amount == Decimal("50.00")
            assert original.availability_state == "RETIRED"
            assert successor.availability_state == "IN_USE"

            # Exactly one row is selectable for new work, and it is the newest.
            in_use = RentSettings.query.filter_by(
                class_id=classroom.class_id, availability_state="IN_USE"
            ).all()
            assert len(in_use) == 1
            assert in_use[0].policy_uuid == successor.policy_uuid
            assert get_rent_settings(classroom.class_id).policy_uuid == successor.policy_uuid

    def test_unspecified_terms_carry_forward_rather_than_reverting(self, app):
        """A partial submission must not silently reset the rest of the contract.

        The rebalancer submits only ``rent_amount``. If the successor were built
        from column defaults, grace period and penalty terms would quietly change
        for every future cycle.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom, rent_amount="50.00")
            customize_rent_settings(
                classroom.class_id,
                grace_period_days=9,
                late_penalty_amount=Decimal("7.00"),
                allow_incremental_payment=True,
            )

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="rent:raise"):
                successor = supersede_rent_settings(
                    class_id=classroom.class_id,
                    updates={"rent_amount": Decimal("200.00")},
                )

            assert successor.rent_amount == Decimal("200.00")
            assert successor.grace_period_days == 9
            assert successor.late_penalty_amount == Decimal("7.00")
            assert successor.allow_incremental_payment is True
            assert successor.frequency_type == "monthly"
            assert successor.due_day_of_month == 1

    def test_in_place_payload_edit_is_rejected(self, app):
        """The model guard must refuse a write path that skipped the command.

        This failure mode is silent and retroactive, so a missed call site has to
        raise rather than quietly corrupt financial history.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            settings = _setup_rent_class(classroom, rent_amount="50.00")

            with pytest.raises(ValueError, match="immutable"):
                with FEATContext("FEAT-TEST-SETUP", idempotency_key="rent:illegal"):
                    settings.rent_amount = Decimal("200.00")
                    db.session.flush()

            db.session.rollback()

    def test_availability_state_may_still_change_on_an_existing_row(self, app):
        """Availability is a projection over the row, not part of the payload."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            settings = _setup_rent_class(classroom, rent_amount="50.00")

            with FEATContext("FEAT-TEST-SETUP", idempotency_key="rent:hide"):
                settings.availability_state = "HIDDEN"
                db.session.flush()

            db.session.refresh(settings)
            assert settings.availability_state == "HIDDEN"
            # Hidden rows are not selectable for new work.
            assert get_rent_settings(classroom.class_id) is None


class TestHistoricalAssessmentsKeepTheirTerms:
    """The B1 defect proper: raising rent must not reprice a closed cycle."""

    def test_rent_increase_does_not_reprice_an_existing_assessment(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom, rent_amount="50.00")
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

            assessments = _rent_assessments(classroom.class_id)
            assert assessments, "reconcile should have assessed cycle 1 rent"
            assessment = assessments[0]
            frozen_uuid = assessment.policy_uuid
            assert frozen_uuid, "the assessment must freeze its governing policy"
            assert obligations_service.resolve_assessment_amount(assessment) == Decimal("50.00")

            # The teacher quadruples rent AFTER cycle 1 was assessed.
            customize_rent_settings(classroom.class_id, rent_amount=Decimal("200.00"))

            # New work sees 200 ...
            assert get_rent_settings(classroom.class_id).rent_amount == Decimal("200.00")

            # ... and the already-assessed cycle still owes 50.
            db.session.refresh(assessment)
            assert assessment.policy_uuid == frozen_uuid
            assert obligations_service.resolve_assessment_amount(assessment) == Decimal("50.00")

    def test_every_seat_assessment_holds_its_amount(self, app):
        """The leak was class-wide, so assert it across the whole roster."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom, rent_amount="50.00")
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

            assessments = _rent_assessments(classroom.class_id)
            assert len(assessments) >= 2, "expected one assessment per claimed seat"

            customize_rent_settings(classroom.class_id, rent_amount=Decimal("200.00"))

            for assessment in assessments:
                db.session.refresh(assessment)
                assert obligations_service.resolve_assessment_amount(assessment) == Decimal(
                    "50.00"
                ), f"assessment {assessment.correlation_id} was repriced"

    def test_late_fee_amount_is_also_frozen(self, app):
        """LATE_FEE resolves its penalty through the same rent policy row."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            enable_class_feature(class_id=classroom.class_id, feature="rent")
            customize_rent_settings(
                classroom.class_id,
                frequency_type="monthly",
                due_day_of_month=1,
                first_rent_due_date=_FIRST_DUE,
                grace_period_days=3,
                rent_amount=Decimal("50.00"),
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            assessment = _rent_assessments(classroom.class_id)[0]

            # Borrow the frozen uuid to price a LATE_FEE the same way the
            # obligations service does, then move the penalty afterwards.
            frozen_uuid = assessment.policy_uuid
            customize_rent_settings(
                classroom.class_id, late_penalty_amount=Decimal("99.00")
            )

            frozen_policy = RentSettings.query.filter_by(policy_uuid=frozen_uuid).first()
            assert frozen_policy is not None, "a superseded policy stays readable"
            assert frozen_policy.late_penalty_amount == Decimal("10.00")
            assert get_rent_settings(classroom.class_id).late_penalty_amount == Decimal(
                "99.00"
            )

    def test_reconcile_reruns_do_not_adopt_the_new_policy_for_an_open_cycle(self, app):
        """A NOOP reconcile must not restamp cycle 1 with the successor policy."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom, rent_amount="50.00")
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            assessment = _rent_assessments(classroom.class_id)[0]
            frozen_uuid = assessment.policy_uuid

            customize_rent_settings(classroom.class_id, rent_amount=Decimal("200.00"))

            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )
            assert result.reason == "NOOP"

            db.session.refresh(assessment)
            assert assessment.policy_uuid == frozen_uuid
            assert obligations_service.resolve_assessment_amount(assessment) == Decimal("50.00")
