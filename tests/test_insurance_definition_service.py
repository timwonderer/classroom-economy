"""Tests for the POL insurance-definition mechanism + FEAT-POL-001 wiring (Step 2).

Covers ``app.services.insurance_definition_service`` and the FEAT-POL-001 entry
points in ``app.feats.policy_reference_feat`` that target the Step-1
``insurance_policies`` definition family. This step establishes the generic POL
store/retrieve mechanism only — it does NOT rewire the teacher route through
FEAT-CLASS-003, publish StoreProducts, or touch entitlement snapshots.

Proven:
* create inserts an IN_USE definition with a fresh policy_uuid;
* "update" == a new immutable row with a new policy_uuid (no in-place mutation);
* class-scoped retrieval + listing with explicit availability filtering;
* availability-only mutation (retire/hide) never alters economic fields;
* cross-class lookup fails closed (returns None / raises NotFound);
* the mechanism creates NO PolicyVersion(domain="insurance") rows.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats import policy_reference_feat as feat
from app.models import InsurancePolicy, PolicyVersion
from app.services import insurance_definition_service as defs
from tests.helpers.classroom_initializer import initialize


def _transaction_definition(**overrides):
    d = dict(
        insurance_type="TRANSACTION",
        premium=Decimal("10.00"),
        charge_frequency="WEEKLY",
        reimbursement_percentage=Decimal("80.00"),
        payout_multiple=Decimal("3.00"),
        claims_per_week_equivalent=Decimal("1.000"),
        claim_window_days=7,
        title="Basic Transaction Cover",
    )
    d.update(overrides)
    return d


def _create(class_id, **overrides):
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
        return defs.create_insurance_definition(
            class_id=class_id, definition=_transaction_definition(**overrides)
        )


class TestCreate:
    def test_create_starts_in_use_with_fresh_uuid(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _create(classroom.class_id)
            assert row.policy_uuid is not None
            assert row.availability_state == defs.IN_USE
            assert row.class_id == classroom.class_id
            assert row.created_at is not None

    def test_unknown_field_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
                with pytest.raises(defs.UnknownDefinitionField):
                    defs.create_insurance_definition(
                        class_id=classroom.class_id,
                        definition=_transaction_definition(policy_uuid="hax"),
                    )

    def test_create_makes_no_policy_version_row(self, app):
        """The new mechanism must not touch PolicyVersion(domain='insurance')."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            before = PolicyVersion.query.filter_by(
                class_id=classroom.class_id, domain="insurance"
            ).count()
            _create(classroom.class_id)
            after = PolicyVersion.query.filter_by(
                class_id=classroom.class_id, domain="insurance"
            ).count()
            assert before == after == 0


class TestImmutabilityAndReplacement:
    def test_update_is_a_new_row_with_new_uuid(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            first = _create(classroom.class_id, premium=Decimal("10.00"))
            first_uuid = first.policy_uuid
            # "Update" == create a new definition/version.
            second = _create(classroom.class_id, premium=Decimal("15.00"))
            assert second.policy_uuid != first_uuid
            # Prior row is untouched (immutable economic fields).
            reloaded = db.session.get(InsurancePolicy, first_uuid)
            assert reloaded.premium == Decimal("10.00")
            assert db.session.get(InsurancePolicy, second.policy_uuid).premium == Decimal("15.00")


class TestRetrieveAndList:
    def test_get_is_class_scoped_and_fails_closed(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            row = _create(home.class_id)
            # Same uuid under the wrong class returns None.
            assert defs.get_insurance_definition(row.policy_uuid, class_id=other.class_id) is None
            assert defs.get_insurance_definition(row.policy_uuid, class_id=home.class_id) is not None

    def test_list_availability_filter_is_explicit(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            visible = _create(classroom.class_id)
            hidden = _create(classroom.class_id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
                defs.hide_insurance_definition(
                    policy_uuid=hidden.policy_uuid, class_id=classroom.class_id
                )
            all_rows = defs.list_insurance_definitions(class_id=classroom.class_id)
            in_use = defs.list_insurance_definitions(
                class_id=classroom.class_id, availability_states=[defs.IN_USE]
            )
            all_uuids = {r.policy_uuid for r in all_rows}
            in_use_uuids = {r.policy_uuid for r in in_use}
            assert visible.policy_uuid in all_uuids and hidden.policy_uuid in all_uuids
            assert visible.policy_uuid in in_use_uuids
            assert hidden.policy_uuid not in in_use_uuids

    def test_list_is_class_scoped(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            _create(home.class_id)
            other_rows = defs.list_insurance_definitions(class_id=other.class_id)
            assert other_rows == []


class TestAvailabilityOnlyMutation:
    def test_retire_changes_only_availability(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _create(classroom.class_id, premium=Decimal("12.00"))
            uuid_ = row.policy_uuid
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
                retired = defs.retire_insurance_definition(
                    policy_uuid=uuid_, class_id=classroom.class_id
                )
            assert retired.availability_state == defs.RETIRED
            assert retired.retired_at is not None
            # Economic contract untouched; same row (no new uuid).
            assert retired.policy_uuid == uuid_
            assert retired.premium == Decimal("12.00")

    def test_set_availability_cross_class_denied(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            row = _create(home.class_id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
                with pytest.raises(defs.InsuranceDefinitionNotFound):
                    defs.set_availability(
                        policy_uuid=row.policy_uuid,
                        class_id=other.class_id,
                        availability_state=defs.RETIRED,
                    )

    def test_invalid_availability_state_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _create(classroom.class_id)
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"pol:{uuid4().hex}"):
                with pytest.raises(defs.InvalidAvailabilityState):
                    defs.set_availability(
                        policy_uuid=row.policy_uuid,
                        class_id=classroom.class_id,
                        availability_state="ARCHIVED",
                    )


class TestFeatPol001Wiring:
    def test_feat_store_definition_creates_row(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = feat.execute_store_insurance_definition(
                class_id=classroom.class_id,
                definition=_transaction_definition(),
                correlation_id=f"corr_{uuid4().hex}",
                idempotency_key=f"FEAT-POL-001:store:{uuid4().hex}",
            )
            assert isinstance(row, InsurancePolicy)
            assert row.availability_state == defs.IN_USE
            # No economic version-control residue.
            assert PolicyVersion.query.filter_by(
                class_id=classroom.class_id, domain="insurance"
            ).count() == 0

    def test_feat_set_availability_wraps_mechanism(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = feat.execute_store_insurance_definition(
                class_id=classroom.class_id,
                definition=_transaction_definition(),
                correlation_id=f"corr_{uuid4().hex}",
                idempotency_key=f"FEAT-POL-001:store:{uuid4().hex}",
            )
            updated = feat.execute_set_insurance_definition_availability(
                class_id=classroom.class_id,
                policy_uuid=row.policy_uuid,
                availability_state=defs.HIDDEN,
                correlation_id=f"corr_{uuid4().hex}",
                idempotency_key=f"FEAT-POL-001:avail:{uuid4().hex}",
            )
            assert updated.availability_state == defs.HIDDEN
            assert updated.policy_uuid == row.policy_uuid
