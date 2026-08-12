"""
Tests for class_configuration_query_service — Phase 3 Primitives

Per SPEC-TEST-001: All tests use canonical initializer (initialize, initialize_as_teacher, initialize_as_student)
Per SPEC-TIME-001: All temporal queries use canonical_temporal_resolver with reference_time_utc injection

Test Structure: 3 tests per function (51+ total)
- Happy path: Function returns expected data
- Empty state: Function handles missing data gracefully
- Multi-tenancy: Query respects class_id scope
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.services.class_configuration_query_service import (
    get_class_economy,
    get_effective_economic_engine,
    get_initial_economic_engine,
    get_economic_engine_history,
    get_class_features,
    get_class_feature,
    get_class_feature_history,
    get_payroll_settings,
    get_rent_settings,
    get_banking_settings,
    get_hall_pass_settings,
    calculate_cwi,
    get_policy_mode,
    is_feature_enabled,
    get_all_classes_by_teacher,
    suggest_economic_mode,
    validate_payroll_rate,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


class TestClassEntityQueries:
    """Test class entity query functions (get_class_economy)."""

    # ========== get_class_economy Tests ==========

    def test_get_class_economy_returns_class_scoped_data(self, app):
        """Happy path: get_class_economy returns correct data."""
        classroom = initialize("chemistry_p1", app)

        economy = get_class_economy(classroom.class_id)

        assert economy is not None
        assert economy.class_id == classroom.class_id
        assert economy.join_code == classroom.join_code

    def test_get_class_economy_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        economy = get_class_economy("nonexistent-class-id")
        assert economy is None

    def test_get_class_economy_multi_tenancy(self, app):
        """Multi-tenancy: queries isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        econ1 = get_class_economy(classroom1.class_id)
        econ2 = get_class_economy(classroom2.class_id)

        assert econ1 is not None
        assert econ2 is not None
        assert econ1.class_id != econ2.class_id
        assert econ1.join_code != econ2.join_code


class TestEconomicEngineQueries:
    """Test economic engine query functions."""

    # ========== get_effective_economic_engine Tests ==========

    def test_get_effective_economic_engine_returns_current_engine(self, app):
        """Happy path: returns effective engine for feature at now."""
        classroom = initialize("chemistry_p1", app)

        engine = get_effective_economic_engine(classroom.class_id, "payroll")

        assert engine is not None
        assert engine.economy_policy_mode in ["tight", "default", "comfortable"]

    def test_get_effective_economic_engine_returns_none_for_missing_feature(self, app):
        """Empty state: missing feature returns None."""
        classroom = initialize("chemistry_p1", app)

        engine = get_effective_economic_engine(classroom.class_id, "nonexistent_feature")

        assert engine is None

    def test_get_effective_economic_engine_respects_feature_scope(self, app):
        """Feature scope: returns None for features that don't have ClassFeature records."""
        classroom = initialize("chemistry_p1", app)

        # Payroll should have an engine (seeded by default)
        payroll_engine = get_effective_economic_engine(classroom.class_id, "payroll")
        assert payroll_engine is not None

        # Store should not have an engine (not seeded by default)
        store_engine = get_effective_economic_engine(classroom.class_id, "store")
        assert store_engine is None

    def test_get_effective_economic_engine_with_temporal_query(self, app):
        """Temporal: can query engine state at specific times."""
        classroom = initialize("chemistry_p1", app)

        # Use a far-future reference time to ensure it's after class creation (SPEC-TIME-001)
        reference_time = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        engine_now = get_effective_economic_engine(classroom.class_id, "payroll", effective_at=reference_time)
        assert engine_now is not None

        # Query with a later timestamp should return the same engine
        # (since we only have one engine version)
        future_time = reference_time + timedelta(days=10)
        engine_future = get_effective_economic_engine(classroom.class_id, "payroll", effective_at=future_time)
        assert engine_future is not None
        assert engine_future.economic_version_id == engine_now.economic_version_id

    # ========== get_initial_economic_engine Tests ==========

    def test_get_initial_economic_engine_returns_original_engine(self, app):
        """Happy path: returns the original/first engine."""
        classroom = initialize("chemistry_p1", app)

        engine = get_initial_economic_engine(classroom.class_id)

        assert engine is not None
        # Should be the earliest created engine
        all_engines = get_economic_engine_history(classroom.class_id)
        assert engine.economic_version_id == all_engines[-1].economic_version_id  # Last in DESC order = first created

    def test_get_initial_economic_engine_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        engine = get_initial_economic_engine("nonexistent-class-id")
        assert engine is None

    def test_get_initial_economic_engine_multi_tenancy(self, app):
        """Multi-tenancy: each class has its own initial engine."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        engine1 = get_initial_economic_engine(classroom1.class_id)
        engine2 = get_initial_economic_engine(classroom2.class_id)

        assert engine1 is not None
        assert engine2 is not None
        # Different classes have different engines
        assert engine1.economic_version_id != engine2.economic_version_id

    # ========== get_economic_engine_history Tests ==========

    def test_get_economic_engine_history_returns_all_versions(self, app):
        """Happy path: returns all engine versions in chronological order."""
        classroom = initialize("chemistry_p1", app)

        history = get_economic_engine_history(classroom.class_id)

        # Should have at least one engine (the initial one)
        assert len(history) >= 1
        # Should be ordered by created_at DESC (most recent first)
        for i in range(len(history) - 1):
            assert history[i].created_at >= history[i + 1].created_at

    def test_get_economic_engine_history_returns_empty_for_missing_class(self, app):
        """Empty state: non-existent class returns empty list."""
        history = get_economic_engine_history("nonexistent-class-id")
        assert history == []

    def test_get_economic_engine_history_multi_tenancy(self, app):
        """Multi-tenancy: each class has separate engine history."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        history1 = get_economic_engine_history(classroom1.class_id)
        history2 = get_economic_engine_history(classroom2.class_id)

        assert len(history1) > 0
        assert len(history2) > 0
        # Should have different engines
        engine_ids_1 = {e.economic_version_id for e in history1}
        engine_ids_2 = {e.economic_version_id for e in history2}
        assert len(engine_ids_1 & engine_ids_2) == 0  # No intersection


class TestClassFeatureQueries:
    """Test class feature query functions."""

    # ========== get_class_features Tests ==========

    def test_get_class_features_returns_all_features(self, app):
        """Happy path: returns all active features."""
        classroom = initialize("chemistry_p1", app)

        features = get_class_features(classroom.class_id)

        # Should have at least some features
        assert len(features) > 0
        assert isinstance(features, dict)

    def test_get_class_features_returns_empty_dict_for_missing_class(self, app):
        """Empty state: non-existent class returns empty dict."""
        features = get_class_features("nonexistent-class-id")
        assert features == {}

    def test_get_class_features_multi_tenancy(self, app):
        """Multi-tenancy: features isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        features1 = get_class_features(classroom1.class_id)
        features2 = get_class_features(classroom2.class_id)

        # Both should have features
        assert len(features1) > 0
        assert len(features2) > 0
        # Each returned feature must belong to its respective class
        for cf in features1.values():
            assert cf.class_id == classroom1.class_id
        for cf in features2.values():
            assert cf.class_id == classroom2.class_id

    def test_get_class_features_with_historical_query(self, app):
        """Temporal: features created today should not appear in historical query before creation."""
        classroom = initialize("chemistry_p1", app)

        # Query at a time well before class creation — no features should exist yet
        past_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        features = get_class_features(classroom.class_id, effective_at=past_time)

        # Features were created "now", so querying 6+ years ago should return nothing
        assert isinstance(features, dict)
        assert len(features) == 0

    # ========== get_class_feature Tests ==========

    def test_get_class_feature_returns_specific_feature(self, app):
        """Happy path: returns specific feature by name."""
        classroom = initialize("chemistry_p1", app)

        feature = get_class_feature(classroom.class_id, "payroll")

        assert feature is not None
        assert feature.feature == "payroll"

    def test_get_class_feature_returns_none_for_missing_feature(self, app):
        """Empty state: missing feature returns None."""
        classroom = initialize("chemistry_p1", app)

        feature = get_class_feature(classroom.class_id, "nonexistent_feature")

        assert feature is None

    def test_get_class_feature_multi_tenancy(self, app):
        """Multi-tenancy: features isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        feature1 = get_class_feature(classroom1.class_id, "payroll")
        feature2 = get_class_feature(classroom2.class_id, "payroll")

        assert feature1 is not None
        assert feature2 is not None
        # Different classes have different feature records
        assert feature1.class_id != feature2.class_id

    # ========== get_class_feature_history Tests ==========

    def test_get_class_feature_history_returns_all_versions(self, app):
        """Happy path: returns all feature versions."""
        classroom = initialize("chemistry_p1", app)

        history = get_class_feature_history(classroom.class_id, "payroll")

        # Should have at least one version
        assert len(history) >= 1
        # All should be for payroll feature
        assert all(cf.feature == "payroll" for cf in history)

    def test_get_class_feature_history_returns_empty_for_missing_feature(self, app):
        """Empty state: missing feature returns empty list."""
        classroom = initialize("chemistry_p1", app)

        history = get_class_feature_history(classroom.class_id, "nonexistent_feature")

        assert history == []

    def test_get_class_feature_history_multi_tenancy(self, app):
        """Multi-tenancy: feature history isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        history1 = get_class_feature_history(classroom1.class_id, "payroll")
        history2 = get_class_feature_history(classroom2.class_id, "payroll")

        # All should be unique to their class
        assert all(cf.class_id == classroom1.class_id for cf in history1)
        assert all(cf.class_id == classroom2.class_id for cf in history2)


class TestSettingsQueries:
    """Test settings query functions (payroll, rent, banking, hall_pass)."""

    # ========== get_payroll_settings Tests ==========

    def test_get_payroll_settings_returns_payroll_data(self, app):
        """Happy path: returns payroll settings."""
        classroom = initialize("chemistry_p1", app)

        payroll = get_payroll_settings(classroom.class_id)

        assert payroll is not None
        assert payroll.class_id == classroom.class_id
        assert payroll.pay_rate is not None
        assert payroll.payroll_frequency_days is not None

    def test_get_payroll_settings_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        payroll = get_payroll_settings("nonexistent-class-id")
        assert payroll is None

    def test_get_payroll_settings_multi_tenancy(self, app):
        """Multi-tenancy: payroll settings isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        payroll1 = get_payroll_settings(classroom1.class_id)
        payroll2 = get_payroll_settings(classroom2.class_id)

        assert payroll1 is not None
        assert payroll2 is not None
        assert payroll1.class_id != payroll2.class_id

    # ========== get_rent_settings Tests ==========

    def test_get_rent_settings_returns_rent_data(self, app):
        """Happy path: returns rent settings."""
        classroom = initialize("chemistry_p1", app)

        rent = get_rent_settings(classroom.class_id)

        assert rent is not None
        assert rent.class_id == classroom.class_id
        assert rent.rent_amount is not None

    def test_get_rent_settings_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        rent = get_rent_settings("nonexistent-class-id")
        assert rent is None

    def test_get_rent_settings_multi_tenancy(self, app):
        """Multi-tenancy: rent settings isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        rent1 = get_rent_settings(classroom1.class_id)
        rent2 = get_rent_settings(classroom2.class_id)

        assert rent1 is not None
        assert rent2 is not None
        assert rent1.class_id != rent2.class_id

    # ========== get_banking_settings Tests ==========

    def test_get_banking_settings_returns_banking_data(self, app):
        """Happy path: returns banking settings."""
        classroom = initialize("chemistry_p1", app)

        banking = get_banking_settings(classroom.class_id)

        assert banking is not None
        assert banking.class_id == classroom.class_id

    def test_get_banking_settings_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        banking = get_banking_settings("nonexistent-class-id")
        assert banking is None

    def test_get_banking_settings_multi_tenancy(self, app):
        """Multi-tenancy: banking settings isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        banking1 = get_banking_settings(classroom1.class_id)
        banking2 = get_banking_settings(classroom2.class_id)

        assert banking1 is not None
        assert banking2 is not None
        assert banking1.class_id != banking2.class_id

    # ========== get_hall_pass_settings Tests ==========

    def test_get_hall_pass_settings_returns_hall_pass_data(self, app):
        """Happy path: returns hall pass settings."""
        classroom = initialize("chemistry_p1", app)

        hp = get_hall_pass_settings(classroom.class_id)

        assert hp is not None
        assert hp.class_id == classroom.class_id

    def test_get_hall_pass_settings_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        hp = get_hall_pass_settings("nonexistent-class-id")
        assert hp is None

    def test_get_hall_pass_settings_multi_tenancy(self, app):
        """Multi-tenancy: hall pass settings isolated by class_id."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        hp1 = get_hall_pass_settings(classroom1.class_id)
        hp2 = get_hall_pass_settings(classroom2.class_id)

        assert hp1 is not None
        assert hp2 is not None
        assert hp1.class_id != hp2.class_id


class TestDerivedValueQueries:
    """Test derived value calculation functions (CWI, policy_mode)."""

    # ========== calculate_cwi Tests ==========

    def test_calculate_cwi_returns_correct_calculation(self, app):
        """Happy path: CWI = (pay_rate * 60) * expected_weekly_hours."""
        classroom = initialize("chemistry_p1", app)

        cwi = calculate_cwi(classroom.class_id)

        # Canonical fixture: pay_rate=$0.50/min, expected_weekly_hours=5.0
        # CWI = ($0.50 × 60) × 5.0 = $30.00 × 5.0 = $150.00/week
        assert cwi == 150.0

    def test_calculate_cwi_returns_none_for_missing_payroll(self, app):
        """Empty state: missing payroll settings returns None."""
        cwi = calculate_cwi("nonexistent-class-id")
        assert cwi is None

    def test_calculate_cwi_multi_tenancy(self, app):
        """Multi-tenancy: CWI calculated per class."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        cwi1 = calculate_cwi(classroom1.class_id)
        cwi2 = calculate_cwi(classroom2.class_id)

        assert cwi1 is not None
        assert cwi2 is not None

    # ========== get_policy_mode Tests ==========

    def test_get_policy_mode_returns_current_mode(self, app):
        """Happy path: returns current policy mode."""
        classroom = initialize("chemistry_p1", app)

        mode = get_policy_mode(classroom.class_id)

        assert mode in ["tight", "default", "comfortable"]

    def test_get_policy_mode_returns_none_for_missing_class(self, app):
        """Empty state: missing class returns None."""
        mode = get_policy_mode("nonexistent-class-id")
        assert mode is None

    def test_get_policy_mode_multi_tenancy(self, app):
        """Multi-tenancy: policy mode per class."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        mode1 = get_policy_mode(classroom1.class_id)
        mode2 = get_policy_mode(classroom2.class_id)

        assert mode1 in ["tight", "default", "comfortable"]
        assert mode2 in ["tight", "default", "comfortable"]


class TestConfigurationStateQueries:
    """Test configuration state query functions."""

    # ========== is_feature_enabled Tests ==========

    def test_is_feature_enabled_returns_true_for_enabled_feature(self, app):
        """Happy path: returns True for enabled feature."""
        classroom = initialize("chemistry_p1", app)

        enabled = is_feature_enabled(classroom.class_id, "payroll")

        assert enabled is True

    def test_is_feature_enabled_returns_false_for_missing_feature(self, app):
        """Empty state: returns False for missing feature."""
        classroom = initialize("chemistry_p1", app)

        enabled = is_feature_enabled(classroom.class_id, "nonexistent_feature")

        assert enabled is False

    def test_is_feature_enabled_multi_tenancy(self, app):
        """Multi-tenancy: feature enablement per class."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_block_a", app)

        enabled1 = is_feature_enabled(classroom1.class_id, "payroll")
        enabled2 = is_feature_enabled(classroom2.class_id, "payroll")

        assert enabled1 is True
        assert enabled2 is True

    # ========== get_all_classes_by_teacher Tests ==========

    def test_get_all_classes_by_teacher_returns_all_classes(self, client, app):
        """Happy path: returns all classes for teacher."""
        classroom = initialize_as_teacher("chemistry_p1", client, app)

        classes = get_all_classes_by_teacher(classroom.teacher_user.id)

        assert len(classes) > 0
        assert any(cls.class_id == classroom.class_id for cls in classes)

    def test_get_all_classes_by_teacher_returns_empty_for_new_teacher(self, app):
        """Empty state: returns empty list for teacher with no classes."""
        classes = get_all_classes_by_teacher(9999)  # Non-existent teacher ID
        assert classes == []

    def test_get_all_classes_by_teacher_ordered_by_creation(self, client, app):
        """Ordering: returns classes ordered by created_at DESC."""
        # Both classrooms share teacher_alice, so get_all_classes_by_teacher returns both
        classroom1 = initialize_as_teacher("chemistry_p1", client, app)
        classroom2 = initialize_as_teacher("ap_csp_p3", client, app)

        classes = get_all_classes_by_teacher(classroom1.teacher_user.id)

        # Must have at least 2 classes to verify ordering
        assert len(classes) >= 2
        for i in range(len(classes) - 1):
            assert classes[i].created_at >= classes[i + 1].created_at


class TestGuidanceFunctions:
    """Test teacher-facing guidance functions."""

    # ========== suggest_economic_mode Tests ==========

    def test_suggest_economic_mode_small_class_small_hours(self):
        """Happy path: small class with limited hours → tight."""
        mode = suggest_economic_mode(class_size=5, weekly_hours=10)
        assert mode == "tight"

    def test_suggest_economic_mode_medium_class(self):
        """Happy path: medium class → default."""
        mode = suggest_economic_mode(class_size=20, weekly_hours=50)
        assert mode == "default"

    def test_suggest_economic_mode_large_class_many_hours(self):
        """Happy path: large class with many hours → comfortable."""
        mode = suggest_economic_mode(class_size=30, weekly_hours=100)
        assert mode == "comfortable"

    # ========== validate_payroll_rate Tests ==========

    def test_validate_payroll_rate_accepts_valid_rate(self):
        """Happy path: valid rate is accepted with no warning."""
        is_valid, warning = validate_payroll_rate(10.0, "default")
        assert is_valid is True
        assert warning is None

    def test_validate_payroll_rate_rejects_negative_rate(self):
        """Error handling: rejects negative rate."""
        is_valid, warning = validate_payroll_rate(-5.0, "default")
        assert is_valid is False
        assert "positive" in warning.lower()

    def test_validate_payroll_rate_rejects_excessive_rate(self):
        """Error handling: rejects rate > $100/hr."""
        is_valid, warning = validate_payroll_rate(150.0, "default")
        assert is_valid is False
        assert "$100" in warning

    def test_validate_payroll_rate_warns_tight_mode_high_rate(self):
        """Advisory: warns if tight mode with high rate."""
        is_valid, warning = validate_payroll_rate(15.0, "tight")
        assert is_valid is True
        assert warning is not None
        assert "tight" in warning.lower() or "imbalance" in warning.lower()

    def test_validate_payroll_rate_warns_comfortable_mode_low_rate(self):
        """Advisory: warns if comfortable mode with low rate."""
        is_valid, warning = validate_payroll_rate(3.0, "comfortable")
        assert is_valid is True
        assert warning is not None
        assert "comfortable" in warning.lower() or "restrictive" in warning.lower()
