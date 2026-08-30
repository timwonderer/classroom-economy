"""Tests for Phase 5 Class Configuration domain view models."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import PayrollSettings
from app.services.class_configuration_view_models import (
    ClassSummaryView,
    ClassConfigurationView,
    FeatureConfigurationView,
    FeatureDefinitionView,
    FeatureSettingsPageView,
    FeatureStateView,
    FeatureToggleView,
    FEATURE_DEFINITIONS,
    build_class_summary_view,
    build_class_configuration_view,
    build_feature_configuration_view,
    build_feature_settings_page_view,
)
from app.services.class_configuration_economic_service import (
    EconomicView,
    build_economic_view,
)
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def classroom(app):
    with app.app_context():
        cr = provision_classroom("chemistry_p1")
        db.session.commit()
        yield cr


# ---------------------------------------------------------------------------
# ClassSummaryView
# ---------------------------------------------------------------------------


class TestClassSummaryView:

    def test_build_returns_frozen_dataclass(self, app, classroom):
        with app.app_context():
            view = build_class_summary_view(classroom.class_id)
            assert view is not None
            assert isinstance(view, ClassSummaryView)
            assert view.class_id == classroom.class_id
            assert view.join_code == classroom.join_code
            assert view.timezone == classroom.economy.class_timezone
            with pytest.raises(AttributeError):
                view.class_id = "mutated"

    def test_build_returns_none_for_missing_class(self, app):
        with app.app_context():
            assert build_class_summary_view("nonexistent") is None

    def test_label_prefers_display_name(self, app, classroom):
        with app.app_context():
            view = build_class_summary_view(classroom.class_id)
            assert view is not None
            if view.display_name:
                assert view.label == view.display_name
            elif view.section:
                assert view.label == view.section
            else:
                assert view.label == view.join_code


# ---------------------------------------------------------------------------
# ClassConfigurationView
# ---------------------------------------------------------------------------


class TestClassConfigurationView:

    def test_build_returns_full_config(self, app, classroom):
        with app.app_context():
            view = build_class_configuration_view(classroom.class_id)
            assert view is not None
            assert isinstance(view, ClassConfigurationView)
            assert view.class_id == classroom.class_id
            assert view.teacher_user_id == classroom.teacher_user_id
            assert isinstance(view.features_enabled, tuple)

    def test_returns_none_for_missing_class(self, app):
        with app.app_context():
            assert build_class_configuration_view("nonexistent") is None

    def test_frozen(self, app, classroom):
        with app.app_context():
            view = build_class_configuration_view(classroom.class_id)
            with pytest.raises(AttributeError):
                view.policy_mode = "tight"


# ---------------------------------------------------------------------------
# FeatureConfigurationView
# ---------------------------------------------------------------------------


class TestFeatureConfigurationView:

    def test_build_returns_all_known_features(self, app, classroom):
        with app.app_context():
            view = build_feature_configuration_view(classroom.class_id)
            assert isinstance(view, FeatureConfigurationView)
            feature_names = [f.feature for f in view.features]
            assert "payroll" in feature_names
            assert "rent" in feature_names
            assert "banking" in feature_names

    def test_is_enabled_helper(self, app, classroom):
        with app.app_context():
            view = build_feature_configuration_view(classroom.class_id)
            # Verify is_enabled returns True for enabled features and False for others
            for f in view.features:
                assert view.is_enabled(f.feature) == f.enabled
            # Unknown feature should return False
            assert view.is_enabled("nonexistent_feature") is False

    def test_feature_state_frozen(self, app, classroom):
        with app.app_context():
            view = build_feature_configuration_view(classroom.class_id)
            with pytest.raises(AttributeError):
                view.features[0].enabled = False

    def test_features_collection_immutable(self, app, classroom):
        with app.app_context():
            view = build_feature_configuration_view(classroom.class_id)
            assert isinstance(view.features, tuple)
            with pytest.raises(AttributeError):
                view.features.append(None)


# ---------------------------------------------------------------------------
# EconomicView (real wiring)
# ---------------------------------------------------------------------------


class TestEconomicView:

    def test_build_returns_economic_view(self, app, classroom):
        with app.app_context():
            view = build_economic_view(classroom.class_id)
            assert isinstance(view, EconomicView)
            assert "low" in view.suggested_pricing_range
            assert "medium" in view.suggested_pricing_range
            assert "high" in view.suggested_pricing_range
            assert 0 <= view.economy_health <= 100

    def test_no_payroll_produces_warning(self, app):
        with app.app_context():
            cr = provision_classroom("biology_block_a")
            PayrollSettings.query.filter_by(class_id=cr.class_id).delete()
            db.session.commit()

            view = build_economic_view(cr.class_id)
            assert any("Payroll" in w for w in view.warnings)

    def test_frozen(self, app, classroom):
        with app.app_context():
            view = build_economic_view(classroom.class_id)
            with pytest.raises(AttributeError):
                view.economy_health = 100

    def test_collections_immutable(self, app, classroom):
        with app.app_context():
            view = build_economic_view(classroom.class_id)
            assert isinstance(view.warnings, tuple)
            with pytest.raises(TypeError):
                view.suggested_pricing_range["new_tier"] = 99.0
            with pytest.raises(TypeError):
                view.display_context["hack"] = True

    def test_nonexistent_class_returns_defaults(self, app):
        with app.app_context():
            view = build_economic_view("nonexistent-class-id")
            assert isinstance(view, EconomicView)
            assert view.economy_health == 50


# ---------------------------------------------------------------------------
# FeatureSettingsPageView (Phase 6-7)
# ---------------------------------------------------------------------------


class TestFeatureSettingsPageView:

    def test_build_returns_frozen_dataclass(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            assert isinstance(view, FeatureSettingsPageView)
            with pytest.raises(AttributeError):
                view.class_id = "mutated"

    def test_class_scoped(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            assert view.class_id == classroom.class_id
            assert view.class_label

    def test_features_contain_toggle_views(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            assert len(view.features) == 6
            for feat in view.features:
                assert isinstance(feat, FeatureToggleView)
                assert feat.feature_key
                assert feat.name
                assert feat.icon
                assert isinstance(feat.enabled, bool)

    def test_payroll_enabled_by_default(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            payroll = next(f for f in view.features if f.feature_key == "payroll")
            assert payroll.enabled is True

    def test_nonexistent_class_returns_none(self, app):
        with app.app_context():
            assert build_feature_settings_page_view("nonexistent") is None


# ---------------------------------------------------------------------------
# U04 hard-gate: CWI-dependent + essential feature gating
# ---------------------------------------------------------------------------


class TestFeatureToggleGating:
    """Insurance is CWI-gated; payroll & banking are essential (frozen ON)."""

    def test_essential_features_marked_and_enabled(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            for key in ("payroll", "banking"):
                feat = next(f for f in view.features if f.feature_key == key)
                assert feat.essential is True
                assert feat.enabled is True
                assert feat.locked is False

    def test_non_essential_features_not_marked_essential(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            for key in ("insurance", "rent", "hall_pass", "store"):
                feat = next(f for f in view.features if f.feature_key == key)
                assert feat.essential is False

    def test_insurance_locked_when_cwi_not_ready(self, app, classroom):
        # Fresh classrooms have a pay rate but no expected_weekly_hours, so CWI
        # is unresolvable and insurance must be gated behind the block symbol.
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            insurance = next(f for f in view.features if f.feature_key == "insurance")
            assert insurance.requires_cwi is True
            assert insurance.cwi_ready is False
            assert insurance.locked is True
            assert insurance.gate_reason  # non-empty tooltip

    def test_only_cwi_dependent_features_require_cwi(self, app, classroom):
        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            for feat in view.features:
                expected = feat.feature_key in {"insurance"}
                assert feat.requires_cwi is expected

    def test_insurance_unlocked_when_cwi_ready(self, app, classroom, monkeypatch):
        # When CWI is resolvable the block symbol disappears and the toggle returns.
        from app.services import class_configuration_view_models as vm
        from app.services.economic_engine import EconomicBase
        from decimal import Decimal

        ready_base = EconomicBase(
            class_id=classroom.class_id,
            economic_version_id="v1",
            economy_policy_mode="balanced",
            expected_weekly_hours=Decimal("5"),
            hourly_pay_rate=Decimal("30.00"),
            cwi=Decimal("150.00"),
        )
        monkeypatch.setattr(vm, "resolve_base", lambda class_id: ready_base)

        with app.app_context():
            view = build_feature_settings_page_view(classroom.class_id)
            insurance = next(f for f in view.features if f.feature_key == "insurance")
            assert insurance.cwi_ready is True
            assert insurance.locked is False
            assert insurance.gate_reason is None
