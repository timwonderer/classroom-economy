"""Regression tests: the insurance claim path consumes ONLY the frozen snapshot.

Step 6 invariant (absolute): once an insurance entitlement is GRANTED, claim
eligibility and economics are computed from the ``frozen_contract`` captured at
purchase time — NEVER by re-reading the current ``InsurancePolicy``. These tests
deliberately mutate (new version) and retire the source definition *after* the
snapshot is taken, and prove the claim resolves against the frozen terms anyway.

They also unit-test the narrow typed read contract
(``get_frozen_insurance_contract`` / ``parse_frozen_contract``) so that raw
payload parsing never leaks into FEAT-STOR-003.

Uses canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, InsuranceClaim
from app.services.context_resolver import CanonicalContext
from app.services import insurance_definition_service as insurance_defs
from app.services.insurance_contract_freeze import (
    build_frozen_contract,
    build_purchase_metadata,
)
from app.services.frozen_insurance_contract import (
    FrozenContractError,
    get_frozen_insurance_contract,
    parse_frozen_contract,
    FrozenInsuranceContract,
)
from app.feats.insurance_claim_feat import (
    submit_insurance_claim,
    resolve_insurance_claim,
)
from tests.helpers.ledger import create_ledger_idempotent_transaction
from tests.helpers.classroom_initializer import initialize


def _transaction_definition(reimbursement_percentage: str) -> dict:
    """A lawful TRANSACTION definition payload for the POL create path."""
    return {
        "insurance_type": "TRANSACTION",
        "tier_level": 1,
        # Non-zero period premium so the payout ceiling (premium × payout_multiple
        # = 100.00) comfortably covers these small frozen-percentage reimbursements;
        # the point of these tests is the frozen *percentage*, not the ceiling.
        "premium": Decimal("100.00"),
        "charge_frequency": "WEEKLY",
        "reimbursement_percentage": Decimal(reimbursement_percentage),
        "payout_multiple": Decimal("1"),
        "claims_per_week_equivalent": Decimal("1"),
        "claim_window_days": 7,
        "title": "Transaction Insurance",
        "tier_name": "Basic",
    }


def _seed_granted_from_definition(app, classroom, student, *, reimbursement_percentage):
    """Create a real POL definition, freeze it, and hand-build the GRANTED event.

    Returns (entitlement_id, policy_uuid) after committing. The frozen snapshot
    on the GRANTED event is produced exactly as the purchase path would produce
    it (build_frozen_contract), so the subsequent mutate/retire is a faithful
    'after purchase' scenario.
    """
    entitlement_id = str(uuid4())
    with app.app_context():
        with FEATContext(
            "FEAT-TEST-SETUP",
            idempotency_key=f"freeze-read-seed:{entitlement_id}",
        ):
            definition = insurance_defs.create_insurance_definition(
                class_id=classroom.class_id,
                definition=_transaction_definition(reimbursement_percentage),
                actor_seat_id=classroom.teacher_seat.id,
            )
            policy_uuid = definition.policy_uuid
            frozen = build_frozen_contract(definition)
            metadata = build_purchase_metadata(definition)

            granted_event = EntitlementEvent(
                event_id=str(uuid4()),
                class_id=classroom.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=student.seat.id,
                actor_seat_id=student.seat.id,
                product_id=1,
                entitlement_type="INSURANCE",
                acquisition_type="PURCHASE",
                event_type="GRANTED",
                payload={
                    "insurance_policy_uuid": policy_uuid,
                    "frozen_contract": frozen,
                    "purchase_metadata": metadata,
                },
            )
            db.session.add(granted_event)
            db.session.flush()
        db.session.commit()
    return entitlement_id, policy_uuid


def _run_claim(app, classroom, student, entitlement_id, *, loss):
    """Submit + approve a claim against a source loss; return the result."""
    with app.app_context():
        with FEATContext(
            "FEAT-TEST-SETUP",
            idempotency_key=f"freeze-read-source:{entitlement_id}",
        ):
            source_transaction, created = create_ledger_idempotent_transaction(
                idempotency_key=f"freeze-read-loss:{entitlement_id}",
                seat_id=student.seat.id,
                class_id=classroom.class_id,
                user_id=student.user.id,
                # Losses are negative from the covered seat's perspective, as the
                # system-law eligibility contract requires.
                amount=-loss,
                account_type="checking",
                type="purchase",
                description="Insured loss",
                actor_seat_id=student.seat.id,
            )
            assert created is True
        db.session.commit()

        student_context = CanonicalContext(
            user_id=student.user.id,
            class_id=classroom.class_id,
            seat_id=student.seat.id,
            actor_role="student",
        )
        submission = submit_insurance_claim(
            canonical_context=student_context,
            entitlement_id=entitlement_id,
            claim_subject={"transaction_id": source_transaction.id},
        )
        assert submission.success is True, submission.error_message

        teacher_context = CanonicalContext(
            user_id=classroom.teacher_seat.user_id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat.id,
            actor_role="teacher",
        )
        return resolve_insurance_claim(
            canonical_context=teacher_context,
            claim_id=submission.claim_id,
            approved=True,
        )


class TestFrozenSnapshotSurvivesSourceMutation:
    """Post-purchase edits/retirement of the source definition never change a claim."""

    def test_claim_uses_frozen_percentage_after_new_version_and_retire(self, app):
        """Freeze at 40%; then publish a 100% new version AND retire the original.

        The approved reimbursement must be 40% of the loss (frozen), not 100%.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[0]

        entitlement_id, policy_uuid = _seed_granted_from_definition(
            app, classroom, student, reimbursement_percentage="40"
        )

        # Mutate the source AFTER purchase: a new immutable version at 100% and
        # retirement of the originally-purchased definition.
        with app.app_context():
            with FEATContext(
                "FEAT-TEST-SETUP",
                idempotency_key=f"freeze-read-mutate:{entitlement_id}",
            ):
                insurance_defs.create_insurance_definition(
                    class_id=classroom.class_id,
                    definition=_transaction_definition("100"),
                    actor_seat_id=classroom.teacher_seat.id,
                )
                insurance_defs.retire_insurance_definition(
                    policy_uuid=policy_uuid, class_id=classroom.class_id
                )
            db.session.commit()

        result = _run_claim(app, classroom, student, entitlement_id, loss=Decimal("100.00"))

        assert result.success is True, result.error_message
        assert result.decision == "APPROVED"
        # 40% of 100.00 from the frozen snapshot — NOT 100% from the live version.
        assert result.reimbursement_amount == Decimal("40.00")

        with app.app_context():
            # The claim lifecycle lives on InsuranceClaim, not a CONSUMED event.
            claim = (
                db.session.query(InsuranceClaim)
                .filter_by(claim_id=result.claim_id, class_id=classroom.class_id)
                .first()
            )
            assert claim is not None
            assert claim.status == "APPROVED"
            assert claim.result_amount == Decimal("40.00")

            # The insurance entitlement is NEVER consumed by a claim decision.
            consumed = (
                db.session.query(EntitlementEvent)
                .filter(
                    EntitlementEvent.entitlement_id == entitlement_id,
                    EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
                )
                .first()
            )
            assert consumed is None

    def test_claim_resolves_even_when_source_definition_retired(self, app):
        """Retire the ONLY definition after purchase; the claim still resolves.

        Under the old current-policy read this would fail (POLICY_DELETED-style);
        the frozen snapshot makes retirement irrelevant to a purchased contract.
        """
        classroom = initialize("chemistry_p1", app)
        student = classroom.students[1]

        entitlement_id, policy_uuid = _seed_granted_from_definition(
            app, classroom, student, reimbursement_percentage="50"
        )

        with app.app_context():
            with FEATContext(
                "FEAT-TEST-SETUP",
                idempotency_key=f"freeze-read-retire:{entitlement_id}",
            ):
                insurance_defs.retire_insurance_definition(
                    policy_uuid=policy_uuid, class_id=classroom.class_id
                )
            db.session.commit()

        result = _run_claim(app, classroom, student, entitlement_id, loss=Decimal("30.00"))

        assert result.success is True, result.error_message
        # 50% of 30.00 = 15.00 from the frozen snapshot.
        assert result.reimbursement_amount == Decimal("15.00")


class TestFrozenContractReadContract:
    """Unit tests for the narrow typed read contract."""

    def test_parse_valid_transaction_contract(self):
        raw = {
            "insurance_type": "TRANSACTION",
            "premium": "0.00",
            "charge_frequency": "WEEKLY",
            "reimbursement_percentage": "40.00",
            "payout_multiple": "1.00",
            "claims_per_week_equivalent": "1.000",
            "claim_window_days": 7,
        }
        contract = parse_frozen_contract(
            raw, insurance_policy_uuid="pol-xyz", purchase_metadata={"title": "T"}
        )
        assert isinstance(contract, FrozenInsuranceContract)
        assert contract.insurance_type == "TRANSACTION"
        assert contract.reimbursement_percentage == Decimal("40.00")
        assert contract.claim_window_days == 7
        assert contract.is_monetary is True
        assert contract.insurance_policy_uuid == "pol-xyz"  # provenance only
        # Non-lawful fields for this type stay None.
        assert contract.claimable_dates_per_week_equivalent is None
        assert contract.waiting_period_days is None

    def test_parse_rejects_unlawful_shape_extra_key(self):
        raw = {
            "insurance_type": "TRANSACTION",
            "premium": "0.00",
            "charge_frequency": "WEEKLY",
            "reimbursement_percentage": "40.00",
            "payout_multiple": "1.00",
            "claims_per_week_equivalent": "1.000",
            "claim_window_days": 7,
            "maximum_policy_payout": "999.00",  # not lawful in the frozen subset
        }
        with pytest.raises(FrozenContractError):
            parse_frozen_contract(raw)

    def test_parse_rejects_missing_key(self):
        raw = {
            "insurance_type": "TRANSACTION",
            "premium": "0.00",
            "charge_frequency": "WEEKLY",
            "reimbursement_percentage": "40.00",
            "payout_multiple": "1.00",
            "claims_per_week_equivalent": "1.000",
            # claim_window_days missing
        }
        with pytest.raises(FrozenContractError):
            parse_frozen_contract(raw)

    def test_parse_rejects_unknown_type(self):
        with pytest.raises(FrozenContractError):
            parse_frozen_contract({"insurance_type": "MYSTERY"})

    def test_get_frozen_contract_missing_snapshot_fails(self, app):
        """A GRANTED insurance event with no frozen_contract fails closed."""
        classroom = initialize("ap_csp_p3", app)
        student = classroom.students[0]
        entitlement_id = str(uuid4())

        with app.app_context():
            with FEATContext(
                "FEAT-TEST-SETUP", idempotency_key=f"no-frozen:{entitlement_id}"
            ):
                db.session.add(
                    EntitlementEvent(
                        event_id=str(uuid4()),
                        class_id=classroom.class_id,
                        entitlement_id=entitlement_id,
                        target_seat_id=student.seat.id,
                        actor_seat_id=student.seat.id,
                        product_id=1,
                        entitlement_type="INSURANCE",
                        acquisition_type="PURCHASE",
                        event_type="GRANTED",
                        payload={"insurance_policy_uuid": "pol-abc"},  # no frozen_contract
                    )
                )
                db.session.flush()
            db.session.commit()

            with pytest.raises(FrozenContractError):
                get_frozen_insurance_contract(
                    entitlement_id,
                    class_id=classroom.class_id,
                    seat_id=student.seat.id,
                )
