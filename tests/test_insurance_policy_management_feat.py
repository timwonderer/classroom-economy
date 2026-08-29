"""Tests for FEAT-CLASS-003 insurance policy management (Step 3).

Covers ``app.feats.class_configuration.feat_class_003_insurance_policy_management``
— the orchestration boundary that validates HARD contract legality AND the
lawful teacher/class scope, then delegates the immutable definition write to
FEAT-POL-001, which persists to the typed ``insurance_policies`` table.

The 8 Step-3 proof points:
 1. creating/editing produces a fresh ``InsurancePolicy.policy_uuid``;
 2. no insurance config writes ``PolicyVersion(domain="insurance")``;
 3. FEAT-CLASS-003 delegates through FEAT-POL-001 (no direct PolicyVersion path);
 4. a lawful submission stores an immutable definition row;
 5. editing never mutates the previous definition (new uuid, old row intact);
 6. recommendation-range overrides remain allowed (advisory, not enforced);
 7. hard/type-structure violations fail (InsuranceContractViolation) BEFORE the
    POL write — no row is created;
 8. cross-class teacher context fails closed.

Canonical context is MANDATORY on every management action: FEAT-CLASS-003
independently establishes anchors, class match, teacher role, and lawful seat —
it never trusts an upstream route. See ``TestMandatoryCanonicalContext``.

Uses the canonical test initializer per SPEC-TEST-001.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.models import InsurancePolicy, PolicyVersion
from app.services import insurance_definition_service as defs
from app.services.context_resolver import CanonicalContext
from app.feats.class_configuration import (
    configure_insurance_definition,
    set_insurance_definition_availability,
    recommend_insurance_terms,
    InsuranceContractViolation,
)
from tests.helpers.classroom_initializer import initialize


# ---------------------------------------------------------------------------
# Submission builders (raw teacher form-shaped dicts, not typed columns).
# ---------------------------------------------------------------------------
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


def _productivity_submission(**overrides):
    s = dict(
        insurance_type="PRODUCTIVITY",
        premium="5.00",
        charge_frequency="WEEKLY",
        reimbursement_percentage="50",
        payout_multiple="2",
        claimable_dates_per_week_equivalent="2",
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
        waiting_period_days="3",
        title="Non-Monetary Cover",
    )
    s.update(overrides)
    return s


def _teacher_context(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _configure(classroom, submission, *, class_id=None, canonical_context="__default__", **kwargs):
    """Call the FEAT with a lawful teacher context by default.

    ``class_id`` defaults to the classroom's; ``canonical_context`` defaults to
    the classroom's teacher context. Either may be overridden to exercise
    mismatch / missing-context paths. The ``@requires_feat_context`` decorator
    opens the FEAT context from the correlation/idempotency kwargs.
    """
    if class_id is None:
        class_id = classroom.class_id
    if canonical_context == "__default__":
        canonical_context = _teacher_context(classroom)
    return configure_insurance_definition(
        class_id=class_id,
        submission=submission,
        canonical_context=canonical_context,
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:configure:{uuid4().hex}",
        **kwargs,
    )


def _set_availability(classroom, policy_uuid, state, *, class_id=None, canonical_context="__default__"):
    if class_id is None:
        class_id = classroom.class_id
    if canonical_context == "__default__":
        canonical_context = _teacher_context(classroom)
    return set_insurance_definition_availability(
        class_id=class_id,
        policy_uuid=policy_uuid,
        availability_state=state,
        canonical_context=canonical_context,
        correlation_id=f"corr_{uuid4().hex}",
        idempotency_key=f"FEAT-CLASS-003:avail:{uuid4().hex}",
    )


def _pv_count(class_id):
    return PolicyVersion.query.filter_by(class_id=class_id, domain="insurance").count()


# ---------------------------------------------------------------------------
# Proof points 1, 3, 4: lawful create → fresh policy_uuid via FEAT-POL-001.
# ---------------------------------------------------------------------------
class TestLawfulCreate:
    def test_create_produces_fresh_uuid_and_in_use_row(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _configure(classroom, _transaction_submission())
            assert isinstance(row, InsurancePolicy)
            assert row.policy_uuid is not None
            assert row.availability_state == defs.IN_USE
            assert row.class_id == classroom.class_id
            assert row.insurance_type == "TRANSACTION"
            assert row.premium == Decimal("10.00")
            # actor_seat_id defaults from the context seat.
            assert row.created_by_seat_id == classroom.teacher_seat.id
            fetched = defs.get_insurance_definition(
                row.policy_uuid, class_id=classroom.class_id
            )
            assert fetched is not None

    def test_all_three_types_are_lawful(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            t = _configure(classroom, _transaction_submission())
            p = _configure(classroom, _productivity_submission())
            n = _configure(classroom, _non_monetary_submission())
            assert t.insurance_type == "TRANSACTION"
            assert p.insurance_type == "PRODUCTIVITY"
            assert n.insurance_type == "NON_MONETARY"
            assert len({t.policy_uuid, p.policy_uuid, n.policy_uuid}) == 3


# ---------------------------------------------------------------------------
# Proof point 2: no PolicyVersion(domain="insurance") writes.
# ---------------------------------------------------------------------------
class TestNoPolicyVersionResidue:
    def test_configure_writes_no_policy_version(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            before = _pv_count(classroom.class_id)
            _configure(classroom, _transaction_submission())
            _configure(classroom, _productivity_submission())
            after = _pv_count(classroom.class_id)
            assert before == after == 0


# ---------------------------------------------------------------------------
# Proof points 1 & 5: edit == new immutable version; prior row untouched.
# ---------------------------------------------------------------------------
class TestEditImmutability:
    def test_edit_creates_new_row_and_leaves_prior_intact(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            first = _configure(classroom, _transaction_submission(premium="10.00"))
            first_uuid = first.policy_uuid

            # "Edit" — re-submit with a changed premium.
            second = _configure(classroom, _transaction_submission(premium="15.00"))
            assert second.policy_uuid != first_uuid

            # Prior definition is immutable.
            reloaded = db.session.get(InsurancePolicy, first_uuid)
            assert reloaded.premium == Decimal("10.00")
            assert db.session.get(
                InsurancePolicy, second.policy_uuid
            ).premium == Decimal("15.00")


# ---------------------------------------------------------------------------
# Proof point 6: recommendation-range overrides remain allowed.
# ---------------------------------------------------------------------------
class TestRecommendationOverrideAllowed:
    def test_value_outside_recommended_range_is_lawful(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _configure(
                classroom,
                _transaction_submission(
                    reimbursement_percentage="100",
                    payout_multiple="999",
                    premium="0.00",
                ),
            )
            assert row.reimbursement_percentage == Decimal("100")
            assert row.payout_multiple == Decimal("999")

    def test_recommendation_metadata_is_advisory_only(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            resolution = recommend_insurance_terms(
                class_id=classroom.class_id, insurance_type="TRANSACTION"
            )
            assert hasattr(resolution, "recommended_ranges")


# ---------------------------------------------------------------------------
# Proof point 7: hard/structural violations fail BEFORE the POL write.
# ---------------------------------------------------------------------------
class TestHardViolationsFailClosed:
    def _assert_no_row_created(self, classroom, submission):
        before = defs.list_insurance_definitions(class_id=classroom.class_id)
        with pytest.raises(InsuranceContractViolation):
            _configure(classroom, submission)
        after = defs.list_insurance_definitions(class_id=classroom.class_id)
        assert len(after) == len(before)

    def test_reimbursement_over_100_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            self._assert_no_row_created(
                classroom, _transaction_submission(reimbursement_percentage="150")
            )

    def test_negative_premium_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            self._assert_no_row_created(
                classroom, _transaction_submission(premium="-1.00")
            )

    def test_unlawful_charge_frequency_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            self._assert_no_row_created(
                classroom, _transaction_submission(charge_frequency="BIWEEKLY")
            )

    def test_unknown_insurance_type_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            self._assert_no_row_created(
                classroom, _transaction_submission(insurance_type="LIFE")
            )

    def test_forbidden_field_for_type_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            self._assert_no_row_created(
                classroom, _non_monetary_submission(reimbursement_percentage="50")
            )

    def test_missing_required_field_for_type_rejected(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            sub = _transaction_submission()
            sub.pop("claim_window_days")
            self._assert_no_row_created(classroom, sub)


# ---------------------------------------------------------------------------
# Proof point 8 + mandatory canonical context: scope is established
# independently and fails closed.
# ---------------------------------------------------------------------------
class TestMandatoryCanonicalContext:
    def test_missing_context_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            before = defs.list_insurance_definitions(class_id=classroom.class_id)
            with pytest.raises(InsuranceContractViolation):
                _configure(
                    classroom, _transaction_submission(), canonical_context=None
                )
            after = defs.list_insurance_definitions(class_id=classroom.class_id)
            assert len(after) == len(before)

    def test_incomplete_context_missing_seat_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            ctx = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=0,  # missing/invalid seat anchor
                actor_role="teacher",
            )
            with pytest.raises(InsuranceContractViolation):
                _configure(classroom, _transaction_submission(), canonical_context=ctx)

    def test_context_seat_not_found_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            ctx = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=99_999_999,  # no such seat
                actor_role="teacher",
            )
            with pytest.raises(InsuranceContractViolation):
                _configure(classroom, _transaction_submission(), canonical_context=ctx)

    def test_context_seat_belongs_to_other_class_fails_closed(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            # Context claims home.class_id but points at the other class's teacher seat.
            ctx = CanonicalContext(
                user_id=home.teacher_user.id,
                class_id=home.class_id,
                seat_id=other.teacher_seat.id,
                actor_role="teacher",
            )
            with pytest.raises(InsuranceContractViolation):
                _configure(home, _transaction_submission(), canonical_context=ctx)

    def test_seat_not_owned_by_context_user_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            # Right teacher seat/class, but the user_id anchor does not own it.
            ctx = CanonicalContext(
                user_id=classroom.students[0].user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )
            with pytest.raises(InsuranceContractViolation):
                _configure(classroom, _transaction_submission(), canonical_context=ctx)

    def test_class_mismatch_denied(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            # A teacher whose context is bound to `home` may not write to `other`.
            ctx = _teacher_context(home)
            with pytest.raises(InsuranceContractViolation):
                _configure(
                    other, _transaction_submission(),
                    class_id=other.class_id, canonical_context=ctx,
                )
            assert defs.list_insurance_definitions(class_id=other.class_id) == []

    def test_non_teacher_role_denied(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            student_ctx = CanonicalContext(
                user_id=classroom.students[0].user.id,
                class_id=classroom.class_id,
                seat_id=classroom.students[0].seat.id,
                actor_role="student",
            )
            with pytest.raises(InsuranceContractViolation):
                _configure(
                    classroom, _transaction_submission(),
                    canonical_context=student_ctx,
                )

    def test_valid_teacher_context_permitted(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _configure(
                classroom, _transaction_submission(),
                canonical_context=_teacher_context(classroom),
            )
            assert row.class_id == classroom.class_id
            assert row.created_by_seat_id == classroom.teacher_seat.id


# ---------------------------------------------------------------------------
# Availability projection through the orchestrator (hide / retire).
# ---------------------------------------------------------------------------
class TestAvailabilityProjection:
    def test_hide_then_retire_changes_only_availability(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _configure(classroom, _transaction_submission(premium="12.00"))
            uuid_ = row.policy_uuid

            hidden = _set_availability(classroom, uuid_, defs.HIDDEN)
            assert hidden.availability_state == defs.HIDDEN
            assert hidden.policy_uuid == uuid_
            assert hidden.premium == Decimal("12.00")

            retired = _set_availability(classroom, uuid_, defs.RETIRED)
            assert retired.availability_state == defs.RETIRED
            assert retired.retired_at is not None
            assert retired.policy_uuid == uuid_

    def test_availability_missing_context_fails_closed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            row = _configure(classroom, _transaction_submission())
            with pytest.raises(InsuranceContractViolation):
                _set_availability(
                    classroom, row.policy_uuid, defs.RETIRED, canonical_context=None
                )

    def test_availability_cross_class_denied(self, app):
        home = initialize("chemistry_p1", app)
        other = initialize("ap_csp_p3", app)
        with app.app_context():
            row = _configure(home, _transaction_submission())
            ctx = _teacher_context(other)
            with pytest.raises(InsuranceContractViolation):
                _set_availability(
                    home, row.policy_uuid, defs.RETIRED, canonical_context=ctx
                )
