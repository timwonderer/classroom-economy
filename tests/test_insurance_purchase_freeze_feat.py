"""Tests for Step 5: purchase/grant-time insurance contract freezing.

When FEAT-STOR-001 purchases an INSURANCE StoreProduct it must:
  1. resolve ``StoreProduct.payload.insurance_policy_uuid``;
  2. resolve that exact InsurancePolicy through the lawful POL retrieval contract
     under the SAME class;
  3. revalidate the definition is available for NEW purchase at purchase time
     (publication alone must not guarantee perpetual purchasability);
  4. build a ``frozen_contract`` from the immutable definition via an explicit,
     type-specific projection (never row.__dict__, generic serialization, or a
     copy of the StoreProduct payload);
  5. persist on the GRANTED event: ``insurance_policy_uuid`` (provenance),
     ``frozen_contract`` (self-sufficient claim-time truth) and
     ``purchase_metadata`` (presentation-only).

Once GRANTED exists, later HIDDEN / RETIRED / deleted source definitions must not
change the purchased entitlement. The premium actually charged (StoreProduct
price) must equal the premium frozen into the contract for that coverage cycle,
so coverage math is never computed from a different economic input than the
student paid.

Uses the canonical test initializer per SPEC-TEST-001. Definitions use
``premium="0.00"`` (and matching StoreProduct ``price="0.00"``) so purchases
succeed without ledger funding; the reconciliation test deliberately mismatches.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import EntitlementEvent, StoreProduct
from app.services import insurance_definition_service as defs
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
)
from app.feats.store_publication_feat import publish_insurance_product
from app.feats.store_purchase_feat import execute_store_purchase
from tests.helpers.classroom_initializer import initialize


# ---------------------------------------------------------------------------
# Contexts.
# ---------------------------------------------------------------------------
def _teacher_ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _student_ctx(classroom, idx=0):
    student = classroom.students[idx]
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


# ---------------------------------------------------------------------------
# Type-specific submissions (premium 0 so purchases need no funding).
# ---------------------------------------------------------------------------
def _transaction_submission(**overrides):
    s = dict(
        insurance_type="TRANSACTION",
        premium="0.00",
        charge_frequency="WEEKLY",
        reimbursement_percentage="80",
        payout_multiple="3",
        claims_per_week_equivalent="1",
        claim_window_days="7",
        tier_level="1",
        tier_name="Bronze",
        title="Basic Transaction Cover",
    )
    s.update(overrides)
    return s


def _productivity_submission(**overrides):
    s = dict(
        insurance_type="PRODUCTIVITY",
        premium="0.00",
        charge_frequency="WEEKLY",
        reimbursement_percentage="50",
        payout_multiple="2",
        claimable_dates_per_week_equivalent="2",
        tier_level="2",
        tier_name="Silver",
        title="Productivity Cover",
    )
    s.update(overrides)
    return s


def _non_monetary_submission(**overrides):
    s = dict(
        insurance_type="NON_MONETARY",
        premium="0.00",
        charge_frequency="MONTHLY",
        claims_per_week_equivalent="1",
        waiting_period_days="14",
        tier_level="3",
        tier_name="Gold",
        title="Non-Monetary Cover",
    )
    s.update(overrides)
    return s


# ---------------------------------------------------------------------------
# Lawful builders (route through the real FEATs).
# ---------------------------------------------------------------------------
def _define(classroom, submission):
    return configure_insurance_definition(
        class_id=classroom.class_id,
        submission=submission,
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
    )


_PRODUCT_SEQ = [5000]


def _next_product_id():
    _PRODUCT_SEQ[0] += 1
    return _PRODUCT_SEQ[0]


def _publish(classroom, policy_uuid, *, price="0.00", product_id=None, name="Cover"):
    if product_id is None:
        product_id = _next_product_id()
    return publish_insurance_product(
        class_id=classroom.class_id,
        insurance_policy_uuid=policy_uuid,
        product_definition={
            "product_id": product_id,
            "is_purchasable": True,
            "supports_direct_grants": False,
            "price": price,
            "name": name,
        },
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-STOR-007:publish:{uuid4().hex}",
    )


def _set_availability(classroom, policy_uuid, state):
    return set_insurance_definition_availability(
        class_id=classroom.class_id,
        policy_uuid=policy_uuid,
        availability_state=state,
        canonical_context=_teacher_ctx(classroom),
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:avail:{uuid4().hex}",
    )


def _create_raw_store_product(classroom, *, insurance_policy_uuid, price="0.00", product_id=None):
    """Create an INSURANCE StoreProduct directly (bypassing the publication FEAT).

    Used to craft references to missing / cross-class / mismatched-price
    definitions that the publication FEAT would otherwise refuse.
    """
    if product_id is None:
        product_id = _next_product_id()
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"raw-store:{uuid4().hex}"):
        product = StorePolicyResolver.create_store_product(
            class_id=classroom.class_id,
            payload={
                "product_id": product_id,
                "is_purchasable": True,
                "supports_direct_grants": False,
                "price": price,
                "entitlement_type": "INSURANCE",
                "insurance_policy_uuid": insurance_policy_uuid,
                "name": "Raw Insurance Cover",
            },
            created_by_seat_id=classroom.teacher_seat_id,
        )
    db.session.commit()
    return product


def _purchase(classroom, store_policy_uuid, *, idx=0, quantity=1):
    return execute_store_purchase(
        canonical_context=_student_ctx(classroom, idx),
        policy_uuid=store_policy_uuid,
        quantity=quantity,
    )


def _granted_events(classroom, *, idx=0, product_id=None):
    q = EntitlementEvent.query.filter_by(
        class_id=classroom.class_id,
        target_seat_id=classroom.students[idx].seat.id,
        event_type="GRANTED",
    )
    if product_id is not None:
        q = q.filter_by(product_id=product_id)
    return q.order_by(EntitlementEvent.timestamp).all()


# Fields that must NEVER leak into frozen_contract (derived/display/provenance).
_FORBIDDEN_IN_FROZEN = (
    "maximum_policy_payout",
    "availability_state",
    "created_at",
    "created_by_seat_id",
    "retired_at",
    "tier_group",
    "description",
    "tier_level",
    "tier_name",
    "title",
    "policy_uuid",
    "class_id",
)


# ===========================================================================
# Exact per-type frozen subsets.
# ===========================================================================
class TestExactFrozenSubsetPerType:
    def test_transaction_freezes_exact_subset(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            result = _purchase(classroom, published.store_policy_uuid)
            assert result.success, result.error_message

            (event,) = _granted_events(classroom)
            frozen = event.payload["frozen_contract"]
            assert set(frozen.keys()) == {
                "insurance_type", "premium", "charge_frequency",
                "reimbursement_percentage", "payout_multiple",
                "claims_per_week_equivalent", "claim_window_days",
            }
            assert frozen["insurance_type"] == "TRANSACTION"
            assert frozen["charge_frequency"] == "WEEKLY"
            assert Decimal(frozen["premium"]) == definition.premium
            assert Decimal(frozen["reimbursement_percentage"]) == definition.reimbursement_percentage
            assert Decimal(frozen["payout_multiple"]) == definition.payout_multiple
            assert Decimal(frozen["claims_per_week_equivalent"]) == definition.claims_per_week_equivalent
            assert int(frozen["claim_window_days"]) == definition.claim_window_days

    def test_productivity_freezes_exact_subset(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _productivity_submission())
            published = _publish(classroom, definition.policy_uuid)
            result = _purchase(classroom, published.store_policy_uuid)
            assert result.success, result.error_message

            (event,) = _granted_events(classroom)
            frozen = event.payload["frozen_contract"]
            assert set(frozen.keys()) == {
                "insurance_type", "premium", "charge_frequency",
                "reimbursement_percentage", "payout_multiple",
                "claimable_dates_per_week_equivalent",
            }
            assert frozen["insurance_type"] == "PRODUCTIVITY"
            assert Decimal(frozen["premium"]) == definition.premium
            assert Decimal(frozen["reimbursement_percentage"]) == definition.reimbursement_percentage
            assert Decimal(frozen["payout_multiple"]) == definition.payout_multiple
            assert Decimal(frozen["claimable_dates_per_week_equivalent"]) == definition.claimable_dates_per_week_equivalent
            # Productivity does NOT carry transaction/non-monetary-only terms.
            assert "claims_per_week_equivalent" not in frozen
            assert "claim_window_days" not in frozen
            assert "waiting_period_days" not in frozen

    def test_non_monetary_freezes_exact_subset(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _non_monetary_submission())
            published = _publish(classroom, definition.policy_uuid)
            result = _purchase(classroom, published.store_policy_uuid)
            assert result.success, result.error_message

            (event,) = _granted_events(classroom)
            frozen = event.payload["frozen_contract"]
            assert set(frozen.keys()) == {
                "insurance_type", "premium", "charge_frequency",
                "claims_per_week_equivalent", "waiting_period_days",
            }
            assert frozen["insurance_type"] == "NON_MONETARY"
            assert frozen["charge_frequency"] == "MONTHLY"
            assert Decimal(frozen["premium"]) == definition.premium
            assert Decimal(frozen["claims_per_week_equivalent"]) == definition.claims_per_week_equivalent
            assert int(frozen["waiting_period_days"]) == definition.waiting_period_days
            # Non-monetary does NOT carry monetary reimbursement terms.
            assert "reimbursement_percentage" not in frozen
            assert "payout_multiple" not in frozen


# ===========================================================================
# No derived / display / provenance leakage.
# ===========================================================================
class TestNoLeakage:
    def test_frozen_contract_excludes_derived_display_provenance(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            assert _purchase(classroom, published.store_policy_uuid).success

            (event,) = _granted_events(classroom)
            frozen = event.payload["frozen_contract"]
            for banned in _FORBIDDEN_IN_FROZEN:
                assert banned not in frozen, f"{banned} leaked into frozen_contract"

    def test_purchase_metadata_is_display_only(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            assert _purchase(classroom, published.store_policy_uuid).success

            (event,) = _granted_events(classroom)
            metadata = event.payload["purchase_metadata"]
            assert set(metadata.keys()) == {"tier_level", "tier_name", "title"}
            assert metadata["tier_name"] == "Bronze"
            assert metadata["title"] == "Basic Transaction Cover"
            # Display metadata must never carry claim-time economic truth.
            for economic in ("premium", "payout_multiple", "reimbursement_percentage"):
                assert economic not in metadata


# ===========================================================================
# Provenance locator preserved.
# ===========================================================================
class TestProvenance:
    def test_insurance_policy_uuid_provenance_preserved(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            assert _purchase(classroom, published.store_policy_uuid).success

            (event,) = _granted_events(classroom)
            assert event.payload["insurance_policy_uuid"] == definition.policy_uuid


# ===========================================================================
# Purchase-time availability + resolution gates.
# ===========================================================================
class TestPurchaseTimeGates:
    def test_missing_definition_fails_purchase(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            product = _create_raw_store_product(
                classroom, insurance_policy_uuid=str(uuid4())
            )
            result = _purchase(classroom, product.policy_uuid)
            assert result.success is False
            assert result.error_code == "INSURANCE_DEFINITION_NOT_FOUND"

    def test_cross_class_definition_fails_purchase(self, app):
        classroom = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            # Define in the OTHER class, reference it from a StoreProduct in THIS class.
            foreign_def = _define(other, _transaction_submission())
            product = _create_raw_store_product(
                classroom, insurance_policy_uuid=foreign_def.policy_uuid
            )
            result = _purchase(classroom, product.policy_uuid)
            assert result.success is False
            # Class-scoped POL retrieval returns None for a foreign definition.
            assert result.error_code == "INSURANCE_DEFINITION_NOT_FOUND"

    def test_hidden_definition_fails_new_purchase(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            _set_availability(classroom, definition.policy_uuid, defs.HIDDEN)
            result = _purchase(classroom, published.store_policy_uuid)
            assert result.success is False
            assert result.error_code == "INSURANCE_NOT_AVAILABLE"

    def test_retired_definition_fails_new_purchase(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            _set_availability(classroom, definition.policy_uuid, defs.RETIRED)
            result = _purchase(classroom, published.store_policy_uuid)
            assert result.success is False
            assert result.error_code == "INSURANCE_NOT_AVAILABLE"


# ===========================================================================
# Premium reconciliation.
# ===========================================================================
class TestPremiumReconciliation:
    def test_price_premium_mismatch_fails_purchase(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            # premium 0.00 but StoreProduct price 5.00 → economic inputs diverge.
            definition = _define(classroom, _transaction_submission(premium="0.00"))
            product = _create_raw_store_product(
                classroom, insurance_policy_uuid=definition.policy_uuid, price="5.00"
            )
            result = _purchase(classroom, product.policy_uuid)
            assert result.success is False
            assert result.error_code == "INSURANCE_PREMIUM_MISMATCH"

    def test_matching_price_premium_succeeds(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission(premium="0.00"))
            product = _create_raw_store_product(
                classroom, insurance_policy_uuid=definition.policy_uuid, price="0.00"
            )
            result = _purchase(classroom, product.policy_uuid)
            assert result.success, result.error_message
            (event,) = _granted_events(classroom)
            # Charged premium == frozen premium.
            assert Decimal(event.payload["price_per_unit"]) == Decimal(
                event.payload["frozen_contract"]["premium"]
            )


# ===========================================================================
# Post-purchase immutability of the frozen entitlement.
# ===========================================================================
class TestPostPurchaseImmutability:
    def test_hiding_source_after_purchase_does_not_change_frozen(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            definition = _define(classroom, _transaction_submission())
            published = _publish(classroom, definition.policy_uuid)
            assert _purchase(classroom, published.store_policy_uuid).success
            (event,) = _granted_events(classroom)
            before = dict(event.payload["frozen_contract"])

            # Retire the source definition AFTER the purchase.
            _set_availability(classroom, definition.policy_uuid, defs.RETIRED)
            db.session.expire_all()

            (event_after,) = _granted_events(classroom)
            assert event_after.payload["frozen_contract"] == before

    def test_new_version_affects_only_subsequent_purchases(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            v1 = _define(classroom, _transaction_submission(payout_multiple="3"))
            pub_v1 = _publish(classroom, v1.policy_uuid)
            assert _purchase(classroom, pub_v1.store_policy_uuid, idx=0).success

            # A NEW definition (new policy_uuid) with different terms.
            v2 = _define(classroom, _transaction_submission(payout_multiple="9"))
            pub_v2 = _publish(classroom, v2.policy_uuid)
            assert _purchase(classroom, pub_v2.store_policy_uuid, idx=1).success

            # Each student purchased exactly once, so seat isolation is sufficient.
            e1 = _granted_events(classroom, idx=0)
            e2 = _granted_events(classroom, idx=1)
            assert len(e1) == 1 and len(e2) == 1
            assert Decimal(e1[0].payload["frozen_contract"]["payout_multiple"]) == Decimal("3")
            assert Decimal(e2[0].payload["frozen_contract"]["payout_multiple"]) == Decimal("9")
            # Provenance points at the respective versions.
            assert e1[0].payload["insurance_policy_uuid"] == v1.policy_uuid
            assert e2[0].payload["insurance_policy_uuid"] == v2.policy_uuid


# ===========================================================================
# Non-insurance purchases are unaffected.
# ===========================================================================
class TestNonInsuranceUnchanged:
    def test_non_insurance_purchase_has_no_frozen_contract(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"noninsurance:{uuid4().hex}"):
                product = StorePolicyResolver.create_store_product(
                    class_id=classroom.class_id,
                    payload={
                        "product_id": _next_product_id(),
                        "is_purchasable": True,
                        "supports_direct_grants": True,
                        "price": "0.00",
                        "entitlement_type": "IMMEDIATE_USE",
                        "name": "Plain Item",
                    },
                    created_by_seat_id=classroom.teacher_seat_id,
                )
            db.session.commit()

            result = _purchase(classroom, product.policy_uuid)
            assert result.success, result.error_message
            (event,) = _granted_events(classroom)
            assert "frozen_contract" not in event.payload
            assert "insurance_policy_uuid" not in event.payload
            assert "purchase_metadata" not in event.payload
