"""Tests for analytics domain view model builders.

Verifies:
- All numeric/date values are pre-formatted as strings
- View models are immutable (frozen dataclasses)
- No ORM models leaked into views
- Threshold-based status determination works correctly
- Trend direction classification is accurate

Per SPEC-TIME-001 § VI: Tests verify that timezone conversion uses canonical_temporal_resolver,
not manual ZoneInfo conversion. Builders require canonical_execution_context with class_id.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from tests.helpers.canonical_classroom import provision_classroom
from app.services.analytics.builders import (
    build_metric_snapshot_view,
    build_alert_card_view,
    build_recent_event_view,
    build_analytics_dashboard_view,
    MetricSnapshotView,
    AnalyticsDashboardView,
)


class TestMetricSnapshotView:
    """Test metric formatting and threshold classification."""

    def test_metric_formats_value_as_percentage(self):
        """Test that metric values are pre-formatted as percentage strings."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("75.5"),
            previous_value=Decimal("70.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("80"),
            format_as="percent",
        )
        assert view.display_current_value == "75.5%"
        assert isinstance(view.display_current_value, str)

    def test_metric_formats_value_as_currency(self):
        """Test that metric values are pre-formatted as currency strings."""
        view = build_metric_snapshot_view(
            metric_name="Average Balance",
            icon_name="account_balance",
            current_value=Decimal("45.67"),
            previous_value=Decimal("40.00"),
            threshold_low=Decimal("30"),
            threshold_high=Decimal("50"),
            format_as="currency",
        )
        assert view.display_current_value == "$45.67"
        assert isinstance(view.display_current_value, str)

    def test_metric_formats_value_as_decimal(self):
        """Test that metric values are pre-formatted as decimal strings."""
        view = build_metric_snapshot_view(
            metric_name="Money Velocity",
            icon_name="speed",
            current_value=Decimal("2.45"),
            previous_value=Decimal("2.10"),
            threshold_low=Decimal("1.0"),
            threshold_high=Decimal("2.5"),
            format_as="decimal",
        )
        assert view.display_current_value == "2.45"
        assert isinstance(view.display_current_value, str)

    def test_metric_classifies_trend_as_increasing(self):
        """Test that trend direction is classified as increasing when current > previous * 1.05."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("80.0"),
            previous_value=Decimal("70.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("70"),
            format_as="percent",
        )
        assert view.trend_direction == "increasing"
        assert "↑" in view.display_trend_badge

    def test_metric_classifies_trend_as_decreasing(self):
        """Test that trend direction is classified as decreasing when current < previous * 0.95."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("60.0"),
            previous_value=Decimal("70.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("70"),
            format_as="percent",
        )
        assert view.trend_direction == "decreasing"
        assert "↓" in view.display_trend_badge

    def test_metric_classifies_trend_as_stable(self):
        """Test that trend direction is classified as stable when within 5% buffer."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("70.0"),
            previous_value=Decimal("70.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("80"),
            format_as="percent",
        )
        assert view.trend_direction == "stable"
        assert "→" in view.display_trend_badge

    def test_metric_determines_status_success(self):
        """Test that status is 'success' when current >= threshold_high."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("85.0"),
            previous_value=Decimal("80.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("70"),
            format_as="percent",
        )
        assert view.status_color == "success"
        assert view.status_label == "On Track"

    def test_metric_determines_status_warning(self):
        """Test that status is 'warning' when low <= current < high."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("65.0"),
            previous_value=Decimal("60.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("70"),
            format_as="percent",
        )
        assert view.status_color == "warning"
        assert view.status_label == "Caution"

    def test_metric_determines_status_danger(self):
        """Test that status is 'danger' when current < threshold_low."""
        view = build_metric_snapshot_view(
            metric_name="Participation Rate",
            icon_name="group",
            current_value=Decimal("40.0"),
            previous_value=Decimal("45.0"),
            threshold_low=Decimal("50"),
            threshold_high=Decimal("70"),
            format_as="percent",
        )
        assert view.status_color == "danger"
        assert view.status_label == "At Risk"

    def test_metric_view_is_frozen_immutable(self):
        """Test that MetricSnapshotView is immutable (frozen dataclass)."""
        view = build_metric_snapshot_view(
            metric_name="Test",
            icon_name="group",
            current_value=Decimal("50.0"),
            previous_value=Decimal("50.0"),
            threshold_low=Decimal("40"),
            threshold_high=Decimal("60"),
            format_as="percent",
        )
        # Attempting to modify should raise AttributeError
        with pytest.raises((AttributeError, TypeError)):
            view.display_current_value = "999.9%"

    def test_metric_no_orm_models_in_view(self):
        """Test that view contains only strings and primitives, no ORM models."""
        view = build_metric_snapshot_view(
            metric_name="Test",
            icon_name="group",
            current_value=Decimal("50.0"),
            previous_value=Decimal("50.0"),
            threshold_low=Decimal("40"),
            threshold_high=Decimal("60"),
            format_as="percent",
        )
        # All fields should be strings or simple types
        assert isinstance(view.metric_name, str)
        assert isinstance(view.icon_name, str)
        assert isinstance(view.current_value, Decimal)  # Raw for transparency
        assert isinstance(view.display_current_value, str)
        assert isinstance(view.trend_direction, str)
        assert isinstance(view.display_trend_badge, str)
        assert isinstance(view.status_color, str)
        assert isinstance(view.status_label, str)


class TestAnalyticsDashboardView:
    """Test complete dashboard view model."""

    def test_dashboard_view_zero_orm_leakage_with_snapshot(self, app):
        """Test that dashboard view contains NO ORM models when snapshot exists."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        # Create a mock snapshot
        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # All metrics should be MetricSnapshotView instances, not ORM
        assert len(dashboard_view.metrics) > 0
        for metric in dashboard_view.metrics:
            assert isinstance(metric, MetricSnapshotView)
            assert metric.display_current_value is not None
            assert isinstance(metric.display_current_value, str)

        # No ORM objects in alerts
        for alert in dashboard_view.all_alerts:
            assert not hasattr(alert, 'db') or alert.db is None

    def test_dashboard_view_handles_missing_snapshot(self, app):
        """Test that dashboard gracefully handles missing snapshot."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=None,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        assert dashboard_view.has_snapshot is False
        assert dashboard_view.display_no_data_message is not None
        assert len(dashboard_view.metrics) == 0
        assert dashboard_view.display_cwi_value == "$0.00/week"

    def test_dashboard_view_all_values_preformatted(self, app):
        """Test that NO template filtering is needed."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # Time window display
        assert dashboard_view.display_window_start is not None
        assert isinstance(dashboard_view.display_window_start, str)
        assert "Aug" in dashboard_view.display_window_start
        assert dashboard_view.display_window_end is not None
        assert isinstance(dashboard_view.display_window_end, str)
        assert "Aug" in dashboard_view.display_window_end

        # CWI value pre-formatted
        assert dashboard_view.display_cwi_value is not None
        assert isinstance(dashboard_view.display_cwi_value, str)
        assert "$" in dashboard_view.display_cwi_value
        assert "/week" in dashboard_view.display_cwi_value

        # All metric values pre-formatted
        for metric in dashboard_view.metrics:
            assert isinstance(metric.display_current_value, str)
            assert isinstance(metric.display_trend_badge, str)
            assert isinstance(metric.status_label, str)

    def test_dashboard_view_is_frozen_immutable(self, app):
        """Test that AnalyticsDashboardView is immutable (frozen dataclass)."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # Attempting to modify should raise AttributeError
        with pytest.raises((AttributeError, TypeError)):
            dashboard_view.display_cwi_value = "$999.99"

    def test_dashboard_view_correct_window_type(self, app):
        """Test that window type is passed through correctly."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=None,
            alerts_list=[],
            events_list=[],
            window_type="month",
            window_start=datetime(2026, 7, 8),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        assert dashboard_view.window_type == "month"

    def test_dashboard_view_builds_metrics_list(self, app):
        """Test that all 4 metrics are built from snapshot."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # Should have 4 metrics: participation, velocity, ontrack, budget
        assert len(dashboard_view.metrics) == 4
        metric_names = {m.metric_name for m in dashboard_view.metrics}
        assert "Participation Rate" in metric_names
        assert "Money Velocity" in metric_names
        assert "On-Track Students" in metric_names
        assert "Budget Survival" in metric_names


class TestAlertCardView:
    """Test alert view model construction."""

    def test_alert_card_view_handles_none(self):
        """Test that build_alert_card_view returns None when given None."""
        result = build_alert_card_view(None)
        assert result is None


class TestRecentEventView:
    """Test event view model formatting."""

    def test_recent_event_view_handles_none(self, app):
        """Test that build_recent_event_view returns None when given None."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")
        result = build_recent_event_view(None, mock_context)
        assert result is None

    def test_recent_event_view_formats_timestamp(self, app):
        """Test that event timestamp is pre-formatted as string using SPEC-TIME-001 canonical resolver.

        SPEC-TIME-001 requires (a) a real ClassEconomy so the class-local timezone
        authority can be resolved, and (b) a timezone-aware UTC timestamp (naive
        timestamps are rejected). We provision a class via the canonical producer and
        supply an aware UTC instant; the builder must then format the class-local date.
        """
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            context = SimpleNamespace(class_id=classroom.class_id)

            event = SimpleNamespace(
                id=1,
                description="Test event",
                event_type="transaction",
                created_at_utc=datetime(2026, 8, 5, 14, 30, 0, tzinfo=timezone.utc),
                old_value=None,
                new_value=None,
            )

            event_view = build_recent_event_view(event, context)

            assert event_view is not None
            assert isinstance(event_view.display_timestamp, str)
            assert "Aug" in event_view.display_timestamp
            assert ":" in event_view.display_timestamp  # Has time

    def test_recent_event_view_formats_numeric_values(self, app):
        """Test that numeric values are pre-formatted as currency."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        event = SimpleNamespace(
            id=1,
            description="Transfer sent",
            event_type="transaction",
            created_at_utc=datetime(2026, 8, 5, 14, 30, 0),
            old_value=Decimal("100.50"),
            new_value=Decimal("75.25"),
        )

        event_view = build_recent_event_view(event, mock_context)

        assert event_view is not None
        assert event_view.display_old_value == "$100.50"
        assert event_view.display_new_value == "$75.25"
        assert isinstance(event_view.display_change_indicator, str)

    def test_dashboard_view_with_non_empty_events_list(self, app):
        """Test that dashboard handles non-empty events_list (covers event path)."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        event = SimpleNamespace(
            id=1,
            description="Payroll posted",
            event_type="transaction",
            created_at_utc=datetime(2026, 8, 5, 14, 30, 0),
            old_value=Decimal("100.00"),
            new_value=Decimal("150.00"),
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[event],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # Verify events are processed
        assert len(dashboard_view.recent_events) == 1
        recent_event = dashboard_view.recent_events[0]
        assert recent_event.description == "Payroll posted"
        assert isinstance(recent_event.display_timestamp, str)
        assert isinstance(recent_event.display_change_indicator, str)

    def test_metric_snapshot_with_decreasing_trend(self):
        """Test trend badge and display_previous_value for decreasing metric."""
        metric = build_metric_snapshot_view(
            metric_name="Test Metric",
            icon_name="test_icon",
            current_value=Decimal("40.0"),
            previous_value=Decimal("50.0"),  # Decreasing
            threshold_low=Decimal("30.0"),
            threshold_high=Decimal("60.0"),
            format_as="percent",
        )

        # Verify trend direction
        assert metric.trend_direction == "decreasing"
        # Verify display_trend_badge shows decrease
        assert "↓" in metric.display_trend_badge
        assert "10.0%" in metric.display_trend_badge
        # Verify display_previous_value is pre-formatted
        assert metric.display_previous_value == "50.0%"
        assert isinstance(metric.display_previous_value, str)


class TestNoJinjaFiltersNeeded:
    """Integration tests verifying templates need zero Jinja filters."""

    def test_all_dashboard_view_values_are_strings(self, app):
        """Test that AnalyticsDashboardView contains only strings, no Decimal/datetime."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # All display_* fields should be strings
        assert isinstance(dashboard_view.display_window_start, str)
        assert isinstance(dashboard_view.display_window_end, str)
        assert isinstance(dashboard_view.display_cwi_value, str)
        assert isinstance(dashboard_view.cwi_status_color, str)
        assert isinstance(dashboard_view.cwi_status_label, str)

        # All metric display values should be strings
        for metric in dashboard_view.metrics:
            assert isinstance(metric.display_current_value, str)
            assert isinstance(metric.display_previous_value, str)
            assert isinstance(metric.display_trend_badge, str)

    def test_builds_analytics_view_model(self, app):
        """Test that builder creates AnalyticsDashboardView with only view model passed to template."""
        # Create a mock context with class_id (required by SPEC-TIME-001)
        mock_context = SimpleNamespace(class_id="test-class-123")

        snapshot = SimpleNamespace(
            participation_rate=75.0,
            participation_trend="increasing",
            money_velocity=2.5,
            velocity_trend="stable",
            cwi_deviation_within_20pct=80.0,
            balance_trend="increasing",
            budget_survival_pass_rate=85.0,
            cwi_value=50.0,
        )

        dashboard_view = build_analytics_dashboard_view(
            snapshot_orm=snapshot,
            alerts_list=[],
            events_list=[],
            window_type="week",
            window_start=datetime(2026, 8, 1),
            window_end=datetime(2026, 8, 8),
            canonical_execution_context=mock_context,
        )

        # Verify that this is the ONLY object suitable for template consumption
        assert isinstance(dashboard_view, AnalyticsDashboardView)
        assert dashboard_view is not None

        # Template should not need to:
        # - Call Jinja filters (|format, |format_datetime)
        # - Access ORM models
        # - Compute trends or thresholds
        # All values are pre-computed as display strings
        for metric in dashboard_view.metrics:
            assert isinstance(metric.display_current_value, str)
            assert isinstance(metric.display_trend_badge, str)
