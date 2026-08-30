"""
Tests for CLASS domain FEATs: FEAT-CLASS-004, FEAT-CLASS-005

Authority: DOM-CLASS-001, DOM-CLASS-002, FEAT-CLASS-004/005
Test Spec: SPEC-TEST-001 (canonical test initializer patterns)
Test Identities: SPEC-TEST-002 (canonical scenarios)

Tests follow SPEC-TEST-001 patterns:
- Use initialize() for service/model tests (no session)
- Use ProvisionedClassroom from canonical initializer
- Query service functions within app context
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.extensions import db
from app.models import ClassFeature, EconomicEngine
from app.feats.base import FEATContext
from app.feats.class_configuration import (
    execute_enable_feature,
    execute_disable_feature,
    execute_transition_economic_policy,
)
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import (
    get_effective_economic_engine,
    get_initial_economic_engine,
)
from tests.helpers.classroom_initializer import initialize


_ENGINE_CARRY_FORWARD_FIELDS = (
    "economy_policy_mode",
    "expected_weekly_hours",
    "interest_rate",
    "interest_calculation_type",
    "compound_frequency",
    "interest_accrual_frequency",
    "interest_payout_frequency",
    "flat_overdraft_fee",
    "progressive_overdraft_fee",
    "overdraft_protection_enabled",
)


def _make_economic_engine_ready(class_id: str, *, expected_weekly_hours: str = "40") -> None:
    """Bring the effective payroll engine to READY so CWI-dependent features may enable.

    The default provisioned classroom leaves ``expected_weekly_hours`` NULL, which keeps
    the Economic Engine NOT_READY. A CWI-dependent feature (e.g. ``insurance``) cannot be
    enabled against a NOT_READY base — that is the lawful precondition FEAT-CLASS-004
    enforces. EconomicEngine versions are immutable, so mint a new version carrying every
    field forward with ``expected_weekly_hours`` set, then link the payroll feature to it
    via a later-effective ClassFeature row (INSERT-only, matches canonical evolution).

    Mirrors the sanctioned helper in ``tests/test_insurance_claim_feat.py``. Caller must
    already be inside a FEAT context.
    """
    current = get_effective_economic_engine(class_id, "payroll")
    if current is not None and current.expected_weekly_hours is not None:
        return

    carried = {name: getattr(current, name) for name in _ENGINE_CARRY_FORWARD_FIELDS}
    carried["expected_weekly_hours"] = float(Decimal(str(expected_weekly_hours)))

    new_engine_id = str(uuid4())
    db.session.add(
        EconomicEngine(
            economic_version_id=new_engine_id,
            class_id=class_id,
            previous_version_id=current.economic_version_id,
            **carried,
        )
    )
    db.session.flush()

    existing_payroll_feature = (
        ClassFeature.query.filter(
            ClassFeature.class_id == class_id,
            ClassFeature.feature == "payroll",
            ClassFeature.economic_version_id.isnot(None),
        )
        .order_by(ClassFeature.effective_at.desc())
        .first()
    )
    db.session.add(
        ClassFeature(
            class_id=class_id,
            feature="payroll",
            effective_at=existing_payroll_feature.effective_at + timedelta(microseconds=1),
            economic_version_id=new_engine_id,
        )
    )
    db.session.flush()


class TestFEATCLASS004FeatureEnablement:
    """Test FEAT-CLASS-004: Feature Enablement/Disablement

    Per SPEC-TEST-001, initialize() provisions a complete classroom DB state
    through production code (FEAT-IDEN-001). The returned ProvisionedClassroom
    contains verified identity and scope artifacts ready for testing.
    """

    def test_enable_feature_success(self, app):
        """Test successful feature enablement via FEAT-CLASS-004.

        Setup: initialize("chemistry_p1") creates:
        - Teacher User + Seat
        - ClassEconomy with initial EconomicEngine
        - Multiple students with seats and identity profiles

        This test verifies that execute_enable_feature() creates a canonical
        class_features row with correct engine linkage and effective_at timestamp.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            # Get initial economic engine (created at class provision time)
            initial_engine = get_initial_economic_engine(classroom.class_id)
            assert initial_engine is not None, "Initial engine should exist"

            # `insurance` is a CWI-dependent feature: FEAT-CLASS-004 refuses to enable it
            # unless the Economic Engine base is READY. The default provisioned classroom
            # leaves expected_weekly_hours NULL (NOT_READY), so bring it to READY first —
            # this is the lawful precondition, not a workaround.
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="class004:enable-success-ready"):
                _make_economic_engine_ready(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Execute: Enable feature
            result = execute_enable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="insurance",
                economic_version_id=initial_engine.economic_version_id,
                correlation_id="test-enable-insurance",
            )

            # Assert: Success
            assert result.success is True
            assert result.feature == "insurance"
            assert result.class_id == classroom.class_id
            assert result.effective_at is not None

            # Verify: class_features row created with correct engine linkage
            cf = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="insurance",
            ).first()
            assert cf is not None
            assert cf.deleted_at is None
            assert cf.economic_version_id == initial_engine.economic_version_id

    def test_enable_feature_idempotency(self, app):
        """Test enabling a feature creates exactly one record (idempotency via PK).

        The (class_id, feature, effective_at) composite primary key on class_features
        provides natural idempotency: multiple attempts to enable the same feature
        at the same time result in a single database row.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            initial_engine = get_initial_economic_engine(classroom.class_id)

            # `insurance` is CWI-dependent; bring the Economic Engine base to READY so the
            # FEAT-CLASS-004 enablement gate is satisfied (lawful precondition).
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="class004:enable-idempotency-ready"):
                _make_economic_engine_ready(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Execute: Enable "insurance" feature (not seeded by default)
            result = execute_enable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="insurance",  # Use feature not in default set
                economic_version_id=initial_engine.economic_version_id,
                correlation_id="test-enable-insurance",
            )
            assert result.success is True
            assert result.feature == "insurance"
            assert result.effective_at is not None

            # Verify exactly one "insurance" row exists with correct properties
            insurance_rows = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="insurance",
                deleted_at=None,
            ).all()
            assert len(insurance_rows) == 1, \
                f"Expected 1 insurance row, got {len(insurance_rows)}"

            row = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="insurance",
                effective_at=datetime.fromisoformat(result.effective_at),
                deleted_at=None,
            ).one_or_none()
            assert row is not None
            assert row.economic_version_id == initial_engine.economic_version_id
            assert row.deleted_at is None

    def test_disable_feature_success(self, app):
        """Test successful feature disablement via FEAT-CLASS-004.

        Disablement is a soft deletion: appends new class_features row
        with deleted_at timestamp per INV-ARC-016 append-only constraints.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            initial_engine = get_initial_economic_engine(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Setup: Enable "hall_pass" feature (not seeded by default)
            enable_result = execute_enable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="hall_pass",
                economic_version_id=initial_engine.economic_version_id,
            )
            assert enable_result.success is True

            # Execute: Disable feature
            result = execute_disable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="hall_pass",
                correlation_id="test-disable-hall_pass",
            )

            # Assert: Success
            assert result.success is True
            assert result.feature == "hall_pass"

            # Verify: Append-only timeline with enable then disable
            # Note: Append-only means we have TWO rows now:
            # Row 1: deleted_at=NULL (enablement from test setup)
            # Row 2: deleted_at=<timestamp> (disablement from this test)
            all_rows = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="hall_pass",
            ).order_by(ClassFeature.effective_at).all()
            assert len(all_rows) == 2
            assert all_rows[0].deleted_at is None  # Enable row
            assert all_rows[1].deleted_at is not None  # Disable row (soft delete)

    def test_disable_feature_not_enabled(self, app):
        """Test disabling a non-enabled feature fails with appropriate error.

        FEAT-CLASS-004 validates that the feature is currently enabled
        before creating a disablement row.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Execute: Disable non-existent feature
            result = execute_disable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="insurance",
            )

            # Assert: Failure with expected error code
            assert result.success is False
            assert result.error_code == "FEATURE_NOT_ENABLED"


class TestFEATCLASS005EconomicEngineEvolution:
    """Test FEAT-CLASS-005: Economic Engine Evolution

    Policy transitions create new immutable EconomicEngine versions with
    version chain linkage (previous_version_id). All affected features are
    re-linked to new version via new class_features rows.
    """

    def test_transition_policy_success(self, app):
        """Test successful economic policy transition with multiple features.

        Verifies:
        - New EconomicEngine version created with new policy_mode
        - Version chain preserved via previous_version_id
        - All affected features linked to new engine
        - Append-only class_features rows for each feature
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            initial_engine = get_initial_economic_engine(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Setup: Enable some features
            for feature in ["payroll", "hall_pass"]:
                execute_enable_feature(
                    canonical_context=canonical_context,
                    class_id=classroom.class_id,
                    feature=feature,
                    economic_version_id=initial_engine.economic_version_id,
                )

            # Execute: Transition policy
            result = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="comfortable",
                feature_list=["payroll", "hall_pass"],
                correlation_id="test-policy-transition",
                idempotency_key="test-policy-transition",
            )

            # Assert: Success
            assert result.success is True
            assert result.new_policy_mode == "comfortable"
            assert result.new_engine_id is not None
            assert set(result.features_updated) == {"payroll", "hall_pass"}

            # Verify: New EconomicEngine version created with version chain
            new_engine = EconomicEngine.query.filter_by(
                economic_version_id=result.new_engine_id
            ).first()
            assert new_engine is not None
            assert new_engine.economy_policy_mode == "comfortable"
            assert new_engine.previous_version_id == initial_engine.economic_version_id

            # Verify: Features linked to new engine via new class_features rows
            for feature in ["payroll", "hall_pass"]:
                cf = ClassFeature.query.filter_by(
                    class_id=classroom.class_id,
                    feature=feature,
                    economic_version_id=result.new_engine_id,
                ).first()
                assert cf is not None

    def test_new_class_has_exactly_one_root_economic_engine(self, app):
        """Regression: a newly provisioned class must have exactly ONE root
        EconomicEngine (previous_version_id IS NULL).

        Two independent producers previously seeded competing roots per class
        (the ClassEconomy after_insert listener AND, separately, FEAT-CLASS-001
        / the test harness). That broke version-chain resolution because
        history/current queries returned an orphan root. The listener is now the
        single canonical root creator.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            roots = EconomicEngine.query.filter_by(
                class_id=classroom.class_id,
                previous_version_id=None,
            ).all()
            assert len(roots) == 1

            # The single root must be the feature-linked initial engine, and it
            # must be a genuine root (no predecessor).
            initial_engine = get_initial_economic_engine(classroom.class_id)
            assert initial_engine is not None
            assert initial_engine.previous_version_id is None
            assert roots[0].economic_version_id == initial_engine.economic_version_id

    def test_transition_policy_invalid_mode(self, app):
        """Test policy transition rejects invalid policy mode."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Execute: Invalid policy mode
            result = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="invalid_mode",
                feature_list=["payroll"],
                idempotency_key="test-policy-transition-invalid",
            )

            # Assert: Failure
            assert result.success is False
            assert result.error_code == "INVALID_POLICY_MODE"

    def test_transition_policy_consecutive_versions(self, app):
        """Back-to-back transitions preserve the economic-engine version chain."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            initial_engine = get_initial_economic_engine(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            for feature in ["hall_pass"]:
                result = execute_enable_feature(
                    canonical_context=canonical_context,
                    class_id=classroom.class_id,
                    feature=feature,
                    economic_version_id=initial_engine.economic_version_id,
                )
                assert result.success is True

            first_transition = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="comfortable",
                feature_list=["payroll", "hall_pass"],
                correlation_id="test-policy-transition-1",
                idempotency_key="test-policy-transition-1",
            )
            assert first_transition.success is True

            second_transition = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="tight",
                feature_list=["payroll", "hall_pass"],
                correlation_id="test-policy-transition-2",
                idempotency_key="test-policy-transition-2",
            )
            assert second_transition.success is True
            assert second_transition.new_engine_id != first_transition.new_engine_id

            latest_engine = EconomicEngine.query.filter_by(
                economic_version_id=second_transition.new_engine_id
            ).first()
            assert latest_engine is not None
            assert latest_engine.previous_version_id == first_transition.new_engine_id

    def test_transition_policy_future_effective_at(self, app):
        """Future-dated transitions persist the requested effective_at timestamp."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            initial_engine = get_initial_economic_engine(classroom.class_id)

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            effective_at = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
            result = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="comfortable",
                feature_list=["payroll"],
                effective_at=effective_at.isoformat(),
                correlation_id="test-policy-transition-future",
                idempotency_key="test-policy-transition-future",
            )

            assert result.success is True
            assert result.effective_at == effective_at.isoformat()

            feature_row = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="payroll",
                economic_version_id=result.new_engine_id,
                effective_at=effective_at,
            ).one_or_none()
            assert feature_row is not None

    def test_transition_policy_feature_not_enabled(self, app):
        """Test policy transition requires all features to be enabled.

        FEAT-CLASS-005 validates that all features in feature_list are
        currently enabled before creating a transition.
        """
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Execute: Transition with feature that was never enabled
            # ("rent" is not in the default features seeded at class creation)
            result = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="comfortable",
                feature_list=["rent"],  # Never enabled
                idempotency_key="test-policy-transition-feature-not-enabled",
            )

            # Assert: Failure - feature must be enabled before policy transition
            assert result.success is False
            assert result.error_code == "FEATURE_NOT_ENABLED"
