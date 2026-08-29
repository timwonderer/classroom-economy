"""Tests for FEAT-STOR-007 insurance-product publication (Step 4).

Covers ``app.feats.store_publication_feat`` — the "publish" boundary that turns
a POL-owned insurance definition (``InsurancePolicy.policy_uuid``, IN_USE) into a
purchasable ``StoreProduct`` in the SAME class, plus the parser rule that makes
``insurance_policy_uuid`` required iff entitlement_type == INSURANCE and
forbidden for every other entitlement type.

Proof points:
 - publishing an IN_USE definition creates a StoreProduct carrying the
   insurance_policy_uuid locator and entitlement_type INSURANCE;
 - defining an insurance policy does NOT auto-publish it (no StoreProduct);
 - HIDDEN / RETIRED definitions cannot be published (fail closed);
 - a definition from another class cannot be published (fail closed);
 - missing / non-teacher / mismatched canonical context fails closed;
 - publication never mutates the underlying definition;
 - no insurance economic terms are duplicated into the StoreProduct payload;
 - parser: locator required for INSURANCE, rejected for every non-INSURANCE
   entitlement type.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import InsurancePolicy, StoreProduct
from app.services import insurance_definition_service as defs
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import (
    StorePolicyConfigParser,
    PolicyValidationError,
)
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
)
from app.feats.store_publication_feat import (
    publish_insurance_product,
    InsurancePublicationError,
)
from tests.helpers.classroom_initializer import initialize


# ---------------------------------------------------------------------------
# Builders.
# ---------------------------------------------------------------------------
def _teacher_context(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _transaction_submission(**overrides):
    s = dict(
        insurance_type="TRANSACTION",
        premium="10.00",
        charge_frequency="WEEKLY",
        reimbursement_percentage="80",
        payout_multiple="3",
        claims_per_week_equivalent="1",
        claim_window_days="7",
        title="Basic Transaction Cover",
    )
    s.update(overrides)
    return s


def _define(classroom, submission=None, *, canonical_context="__default__"):
    """Create an insurance definition via FEAT-CLASS-003 (no publication)."""
    if submission is None:
        submission = _transaction_submission()
    if canonical_context == "__default__":
        canonical_context = _teacher_context(classroom)
    return configure_insurance_definition(
        class_id=classroom.class_id,
        submission=submission,
        canonical_context=canonical_context,
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
    )


def _set_availability(classroom, policy_uuid, state):
    """Change availability through FEAT-CLASS-003 (its own FEAT context)."""
    return set_insurance_definition_availability(
        class_id=classroom.class_id,
        policy_uuid=policy_uuid,
        availability_state=state,
        canonical_context=_teacher_context(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:avail:{uuid4().hex}",
    )


def _catalog_payload(**overrides):
    """Minimal catalog-level StoreProduct fields (no insurance economics)."""
    p = dict(
        product_id=1001,
        is_purchasable=True,
        supports_direct_grants=False,
        price="10.00",
        name="Transaction Cover",
    )
    p.update(overrides)
    return p


def _publish(classroom, insurance_policy_uuid, *, product_definition=None,
             class_id=None, canonical_context="__default__"):
    if class_id is None:
        class_id = classroom.class_id
    if canonical_context == "__default__":
        canonical_context = _teacher_context(classroom)
    if product_definition is None:
        product_definition = _catalog_payload()
    return publish_insurance_product(
        class_id=class_id,
        insurance_policy_uuid=insurance_policy_uuid,
        product_definition=product_definition,
        canonical_context=canonical_context,
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-STOR-007:publish:{uuid4().hex}",
    )


def _product_count(class_id):
    return StoreProduct.query.filter_by(class_id=class_id).count()


# ---------------------------------------------------------------------------
# Happy path: publish an IN_USE definition.
# ---------------------------------------------------------------------------
class TestLawfulPublication:
    def test_publish_creates_store_product_with_locator(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            result = _publish(classroom, definition.policy_uuid)

            product = StoreProduct.query.get(result.store_product_id)
            assert product is not None
            assert product.class_id == classroom.class_id
            assert product.payload["entitlement_type"] == "INSURANCE"
            assert product.payload["insurance_policy_uuid"] == definition.policy_uuid
            assert product.created_by_seat_id == classroom.teacher_seat.id
            # The parser accepts this published product.
            config = StorePolicyConfigParser.parse(
                payload=product.payload, class_id=classroom.class_id
            )
            assert config.entitlement_type == "INSURANCE"
            assert config.insurance_policy_uuid == definition.policy_uuid

    def test_no_insurance_economics_duplicated(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            result = _publish(classroom, definition.policy_uuid)
            product = StoreProduct.query.get(result.store_product_id)
            # Only the locator links to insurance; economic terms stay in POL.
            for economic_field in (
                "premium", "reimbursement_percentage", "payout_multiple",
                "charge_frequency", "claim_window_days", "claims_per_week_equivalent",
            ):
                assert economic_field not in product.payload


# ---------------------------------------------------------------------------
# Define ≠ publish.
# ---------------------------------------------------------------------------
class TestDefineDoesNotPublish:
    def test_defining_creates_no_store_product(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            before = _product_count(classroom.class_id)
            _define(classroom)
            assert _product_count(classroom.class_id) == before


# ---------------------------------------------------------------------------
# Availability gate: only IN_USE definitions may be published.
# ---------------------------------------------------------------------------
class TestAvailabilityGate:
    def test_hidden_definition_cannot_be_published(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            _set_availability(classroom, definition.policy_uuid, defs.HIDDEN)
            before = _product_count(classroom.class_id)
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, definition.policy_uuid)
            assert _product_count(classroom.class_id) == before

    def test_retired_definition_cannot_be_published(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            _set_availability(classroom, definition.policy_uuid, defs.RETIRED)
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, definition.policy_uuid)


# ---------------------------------------------------------------------------
# Class scope: fail closed on cross-class definition references.
# ---------------------------------------------------------------------------
class TestClassScope:
    def test_definition_from_other_class_cannot_be_published(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            foreign_def = _define(other)
            before = _product_count(home.class_id)
            # home teacher tries to publish other's definition under home.
            with pytest.raises(InsurancePublicationError):
                _publish(home, foreign_def.policy_uuid)
            assert _product_count(home.class_id) == before

    def test_nonexistent_definition_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, uuid4().hex)


# ---------------------------------------------------------------------------
# Mandatory canonical teacher context.
# ---------------------------------------------------------------------------
class TestMandatoryContext:
    def test_missing_context_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            before = _product_count(classroom.class_id)
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, definition.policy_uuid, canonical_context=None)
            assert _product_count(classroom.class_id) == before

    def test_non_teacher_role_denied(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            student_ctx = CanonicalContext(
                user_id=classroom.students[0].user.id,
                class_id=classroom.class_id,
                seat_id=classroom.students[0].seat.id,
                actor_role="student",
            )
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, definition.policy_uuid,
                         canonical_context=student_ctx)

    def test_class_mismatch_denied(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            definition = _define(other)
            # Context bound to home may not publish under other.
            with pytest.raises(InsurancePublicationError):
                _publish(
                    other, definition.policy_uuid,
                    class_id=other.class_id,
                    canonical_context=_teacher_context(home),
                )

    def test_seat_not_owned_by_user_denied(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            ctx = CanonicalContext(
                user_id=classroom.students[0].user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )
            with pytest.raises(InsurancePublicationError):
                _publish(classroom, definition.policy_uuid, canonical_context=ctx)


# ---------------------------------------------------------------------------
# Publication does not mutate the underlying POL definition.
# ---------------------------------------------------------------------------
class TestDefinitionUntouched:
    def test_definition_unchanged_after_publish(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            uuid_ = definition.policy_uuid
            premium_before = definition.premium
            state_before = definition.availability_state

            _publish(classroom, uuid_)

            after = defs.get_insurance_definition(uuid_, class_id=classroom.class_id)
            assert after.policy_uuid == uuid_
            assert after.premium == premium_before
            assert after.availability_state == state_before == defs.IN_USE
            # Exactly one definition row still exists for this uuid.
            assert (
                InsurancePolicy.query.filter_by(
                    policy_uuid=uuid_, class_id=classroom.class_id
                ).count()
                == 1
            )


# ---------------------------------------------------------------------------
# Publishing does not smuggle a conflicting entitlement_type / locator.
# ---------------------------------------------------------------------------
class TestPayloadStamping:
    def test_conflicting_entitlement_type_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            with pytest.raises(InsurancePublicationError):
                _publish(
                    classroom, definition.policy_uuid,
                    product_definition=_catalog_payload(entitlement_type="PRIVILEGE"),
                )

    def test_conflicting_locator_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom)
            with pytest.raises(InsurancePublicationError):
                _publish(
                    classroom, definition.policy_uuid,
                    product_definition=_catalog_payload(
                        insurance_policy_uuid="some-other-uuid"
                    ),
                )


# ---------------------------------------------------------------------------
# Parser locator rule (no DB): required iff INSURANCE, forbidden otherwise.
# ---------------------------------------------------------------------------
class TestParserLocatorRule:
    def _base(self, entitlement_type, **overrides):
        p = dict(
            product_id=1,
            is_purchasable=True,
            supports_direct_grants=True,  # satisfies HALL_PASS/PRIVILEGE rules
            price="1.00",
            entitlement_type=entitlement_type,
        )
        p.update(overrides)
        return p

    def test_insurance_requires_locator(self):
        payload = self._base("INSURANCE")  # no insurance_policy_uuid
        with pytest.raises(PolicyValidationError):
            StorePolicyConfigParser.parse(payload=payload, class_id="c1")

    def test_insurance_with_locator_ok(self):
        payload = self._base("INSURANCE", insurance_policy_uuid="pol-123")
        config = StorePolicyConfigParser.parse(payload=payload, class_id="c1")
        assert config.entitlement_type == "INSURANCE"
        assert config.insurance_policy_uuid == "pol-123"

    @pytest.mark.parametrize(
        "entitlement_type",
        ["IMMEDIATE_USE", "DELAYED_USE", "HALL_PASS", "PRIVILEGE", "COLLECTIVE_GOAL"],
    )
    def test_locator_rejected_for_non_insurance(self, entitlement_type):
        payload = self._base(entitlement_type, insurance_policy_uuid="pol-123")
        with pytest.raises(PolicyValidationError):
            StorePolicyConfigParser.parse(payload=payload, class_id="c1")
