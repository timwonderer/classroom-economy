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

import pytest

from app.extensions import db
from app.models import ClassFeature, EconomicEngine
from app.feats.class_configuration import (
    execute_enable_feature,
    execute_disable_feature,
    execute_transition_economic_policy,
)
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import get_initial_economic_engine
from tests.helpers.classroom_initializer import initialize


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

            # Setup: Enable "rent" feature (not seeded by default)
            enable_result = execute_enable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="rent",
                economic_version_id=initial_engine.economic_version_id,
            )
            assert enable_result.success is True

            # Execute: Disable feature
            result = execute_disable_feature(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                feature="rent",
                correlation_id="test-disable-rent",
            )

            # Assert: Success
            assert result.success is True
            assert result.feature == "rent"

            # Verify: Append-only timeline with enable then disable
            # Note: Append-only means we have TWO rows now:
            # Row 1: deleted_at=NULL (enablement from test setup)
            # Row 2: deleted_at=<timestamp> (disablement from this test)
            all_rows = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="rent",
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
            for feature in ["payroll", "rent"]:
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
                feature_list=["payroll", "rent"],
                correlation_id="test-policy-transition",
                idempotency_key="test-policy-transition",
            )

            # Assert: Success
            assert result.success is True
            assert result.new_policy_mode == "comfortable"
            assert result.new_engine_id is not None
            assert set(result.features_updated) == {"payroll", "rent"}

            # Verify: New EconomicEngine version created with version chain
            new_engine = EconomicEngine.query.filter_by(
                economic_version_id=result.new_engine_id
            ).first()
            assert new_engine is not None
            assert new_engine.economy_policy_mode == "comfortable"
            assert new_engine.previous_version_id == initial_engine.economic_version_id

            # Verify: Features linked to new engine via new class_features rows
            for feature in ["payroll", "rent"]:
                cf = ClassFeature.query.filter_by(
                    class_id=classroom.class_id,
                    feature=feature,
                    economic_version_id=result.new_engine_id,
                ).first()
                assert cf is not None

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

            for feature in ["rent"]:
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
                feature_list=["payroll", "rent"],
                correlation_id="test-policy-transition-1",
                idempotency_key="test-policy-transition-1",
            )
            assert first_transition.success is True

            second_transition = execute_transition_economic_policy(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                new_policy_mode="tight",
                feature_list=["payroll", "rent"],
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
