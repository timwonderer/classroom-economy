"""Tests for Phase 5 Class Configuration domain view models."""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models import PayrollSettings
from app.services.class_configuration_view_models import (
    ClassSummaryView,
    ClassConfigurationView,
    FeatureConfigurationView,
    FeatureStateView,
    build_class_summary_view,
    build_class_list_view,
    build_class_configuration_view,
    build_feature_configuration_view,
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


class TestClassListView:

    def test_returns_all_teacher_classes(self, app, classroom):
        with app.app_context():
            views = build_class_list_view(classroom.teacher_user_id)
            assert len(views) >= 1
            class_ids = [v.class_id for v in views]
            assert classroom.class_id in class_ids

    def test_returns_empty_for_unknown_teacher(self, app):
        with app.app_context():
            assert build_class_list_view(999999) == []

    def test_multi_tenancy_isolation(self, app):
        with app.app_context():
            cr1 = provision_classroom("chemistry_p1")
            cr2 = provision_classroom("biology_block_a")
            db.session.commit()

            list1 = build_class_list_view(cr1.teacher_user_id)
            list2 = build_class_list_view(cr2.teacher_user_id)

            ids1 = {v.class_id for v in list1}
            ids2 = {v.class_id for v in list2}

            assert cr1.class_id in ids1
            assert cr2.class_id not in ids1
            assert cr2.class_id in ids2
            assert cr1.class_id not in ids2


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
            assert isinstance(view.features_enabled, list)

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

    def test_nonexistent_class_returns_defaults(self, app):
        with app.app_context():
            view = build_economic_view("nonexistent-class-id")
            assert isinstance(view, EconomicView)
            assert view.economy_health == 50
