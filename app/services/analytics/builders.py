"""Analytics domain view model builders.

Transforms ORM AnalyticsWindowView snapshots into display-ready frozen dataclasses.
Pre-formats all numeric and date values for template consumption.

Per SPEC-UI-001 § VI: Each view model is immutable (@dataclass(frozen=True)).
Display fields are strings; raw Decimal values included for calculations/transparency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class MetricSnapshotView:
    """Pre-computed metric with all display fields.

    Templates use this to render a single metric row without:
    - Jinja filters (all formatting done)
    - Business logic (trend/threshold computed)
    - ORM access (all values pre-fetched)
    """
    metric_name: str
    icon_name: str  # Material Symbols icon (e.g., "group", "speed")
    current_value: Decimal
    display_current_value: str
    display_previous_value: str
    trend_direction: str  # "increasing", "decreasing", "stable"
    display_trend_badge: str
    status_color: str  # "success", "warning", "danger"
    status_label: str
    change_display: str  # Computed change value (e.g., "+5.2%")


@dataclass(frozen=True)
class AlertCardView:
    """Pre-formatted alert with display fields.

    Currently alerts are empty (not yet implemented in analytics),
    but structure is ready for future alert system.
    """
    alert_id: Optional[int]
    alert_key: str
    severity: str
    title: str
    description: str
    why_it_matters: str
    what_changed: str
    suggested_action: str
    is_acknowledged: bool
    display_acknowledged_badge: str
    icon_class: str
    alert_class: str


@dataclass(frozen=True)
class RecentEventView:
    """Pre-formatted event log entry."""
    event_id: int
    description: str
    event_type: str
    display_timestamp: str
    display_old_value: str
    display_new_value: str
    display_change_indicator: str


@dataclass(frozen=True)
class AnalyticsDashboardView:
    """Single page view model for analytics dashboard.

    Templates receive ONLY this frozen dataclass.
    All numeric formatting, date formatting, and business logic
    is pre-computed here. Templates just render.
    """
    # Time window context
    display_window_start: str  # "Mon DD"
    display_window_end: str  # "Mon DD, YYYY"
    window_type: str

    # CWI context
    cwi_value: Decimal  # Raw for transparency
    display_cwi_value: str  # "$X.XX"
    cwi_status_color: str  # "success", "warning", "danger"
    cwi_status_label: str  # "Healthy", "Caution", "Critical"

    # Pre-built metrics (list of MetricSnapshotView)
    metrics: list[MetricSnapshotView]

    # Pre-built alerts
    alerts_by_key: dict[str, AlertCardView]
    all_alerts: list[AlertCardView]
    alert_count: int

    # Pre-built events
    recent_events: list[RecentEventView]

    # State indicators
    has_snapshot: bool
    display_no_data_message: Optional[str]


def build_metric_snapshot_view(
    metric_name: str,
    icon_name: str,
    current_value: Decimal,
    previous_value: Optional[Decimal],
    threshold_low: Decimal,
    threshold_high: Decimal,
    format_as: str = "percent",  # "percent", "decimal", "currency"
) -> MetricSnapshotView:
    """Build a metric view with all display values pre-formatted.

    Eliminates template-level:
    - Jinja |format() filters
    - Trend direction conditionals
    - Threshold-based CSS class logic

    Args:
        metric_name: Display name ("Participation Rate", "Money Velocity", etc.)
        icon_name: Material Symbols icon name (e.g., "group", "speed")
        current_value: Current metric value (Decimal for precision)
        previous_value: Previous metric value for trend calculation (None for "no prior")
        threshold_low: Low threshold for "danger" status
        threshold_high: High threshold for "warning" status
        format_as: Format type for display_current_value

    Returns:
        MetricSnapshotView with all display fields pre-computed
    """
    # Format current value based on type (preserving Decimal precision)
    if format_as == "percent":
        display_current = f"{current_value:.1f}%"
    elif format_as == "currency":
        display_current = f"${current_value:.2f}"
    else:  # decimal
        display_current = f"{current_value:.2f}"

    # Handle previous value (may be None for "no prior data")
    if previous_value is None:
        display_previous = "No prior"
        trend_direction = "stable"
        trend_symbol = "→"
        change_display = ""
        display_trend_badge = f"{trend_symbol} No prior"
    else:
        # Format previous value based on type
        if format_as == "percent":
            display_previous = f"{previous_value:.1f}%"
        elif format_as == "currency":
            display_previous = f"${previous_value:.2f}"
        else:  # decimal
            display_previous = f"{previous_value:.2f}"

        # Compute trend direction with 5% buffer for stability
        if current_value > previous_value * Decimal("1.05"):
            trend_direction = "increasing"
            trend_symbol = "↑"
        elif current_value < previous_value * Decimal("0.95"):
            trend_direction = "decreasing"
            trend_symbol = "↓"
        else:
            trend_direction = "stable"
            trend_symbol = "→"

        # Compute change display using Decimal precision (not float)
        change = abs(current_value - previous_value)
        if format_as == "percent":
            change_display = f"{change:.1f}%"
        elif format_as == "currency":
            change_display = f"${change:.2f}"
        else:
            change_display = f"{change:.2f}"

        # Compute trend badge with change amount
        if trend_direction != "stable":
            display_trend_badge = f"{trend_symbol} {change_display}"
        else:
            display_trend_badge = f"{trend_symbol} Stable"

    # Determine status based on thresholds
    # Convert to Decimal for proper comparison
    current_val = Decimal(str(current_value)) if not isinstance(current_value, Decimal) else current_value
    high = Decimal(str(threshold_high)) if not isinstance(threshold_high, Decimal) else threshold_high
    low = Decimal(str(threshold_low)) if not isinstance(threshold_low, Decimal) else threshold_low

    if current_val >= high:
        status_color = "success"
        status_label = "On Track"
    elif current_val >= low:
        status_color = "warning"
        status_label = "Caution"
    else:
        status_color = "danger"
        status_label = "At Risk"

    return MetricSnapshotView(
        metric_name=metric_name,
        icon_name=icon_name,
        current_value=current_value,
        display_current_value=display_current,
        display_previous_value=display_previous,
        trend_direction=trend_direction,
        display_trend_badge=display_trend_badge,
        status_color=status_color,
        status_label=status_label,
        change_display=change_display,
    )


def build_alert_card_view(alert_orm_object: Optional[object] = None) -> Optional[AlertCardView]:
    """Build an alert view from ORM object.

    Currently alerts are not fully implemented in analytics,
    so this returns None. Structure is ready for future use.

    Args:
        alert_orm_object: Alert ORM object (or None for empty case)

    Raises:
        NotImplementedError: If called with a non-None alert_orm_object
    """
    if not alert_orm_object:
        return None

    # When alerts are implemented, this will accept Alert ORM model
    # and pre-compute display fields like severity CSS class, icon class, etc.
    raise NotImplementedError("Alert view building not yet implemented")


def build_recent_event_view(event_orm_object: object) -> Optional[RecentEventView]:
    """Build an event view from AuditEvent ORM object.

    Eliminates template-level:
    - Date formatting with .strftime()
    - Numeric value formatting
    - Event type to icon mapping

    Args:
        event_orm_object: AuditEvent ORM model instance

    Returns:
        RecentEventView with all display fields pre-formatted, or None
    """
    if not event_orm_object or not hasattr(event_orm_object, 'created_at_utc'):
        return None

    # Format timestamp as "Mon DD, YYYY at HH:MM AM/PM"
    if hasattr(event_orm_object, 'created_at_utc') and event_orm_object.created_at_utc:
        try:
            display_timestamp = event_orm_object.created_at_utc.strftime('%b %d, %Y at %I:%M %p')
        except (AttributeError, TypeError):
            display_timestamp = "Unknown date"
    else:
        display_timestamp = "Unknown date"

    # Format old_value and new_value
    old_value = getattr(event_orm_object, 'old_value', None)
    new_value = getattr(event_orm_object, 'new_value', None)

    # Try to format as currency if numeric
    try:
        if old_value is not None:
            if isinstance(old_value, (int, float, Decimal)):
                display_old = f"${float(old_value):.2f}"
            else:
                display_old = str(old_value)
        else:
            display_old = "N/A"
    except (ValueError, TypeError):
        display_old = "N/A"

    try:
        if new_value is not None:
            if isinstance(new_value, (int, float, Decimal)):
                display_new = f"${float(new_value):.2f}"
            else:
                display_new = str(new_value)
        else:
            display_new = "N/A"
    except (ValueError, TypeError):
        display_new = "N/A"

    # Compute change indicator
    if display_old != "N/A" and display_new != "N/A":
        try:
            old_num = float(old_value) if old_value is not None else 0
            new_num = float(new_value) if new_value is not None else 0
            if new_num > old_num:
                display_change = f"+${float(new_num - old_num):.2f}"
            elif new_num < old_num:
                display_change = f"-${float(old_num - new_num):.2f}"
            else:
                display_change = "$0.00"
        except (ValueError, TypeError):
            display_change = f"{display_old} → {display_new}"
    elif display_old == "N/A" and display_new == "N/A":
        display_change = ""
    else:
        display_change = f"{display_old} → {display_new}"

    description = getattr(event_orm_object, 'description', 'Event recorded')
    event_type = getattr(event_orm_object, 'event_type', 'transaction')
    event_id = getattr(event_orm_object, 'id', 0)

    return RecentEventView(
        event_id=event_id,
        description=description,
        event_type=event_type,
        display_timestamp=display_timestamp,
        display_old_value=display_old,
        display_new_value=display_new,
        display_change_indicator=display_change,
    )


def build_analytics_dashboard_view(
    snapshot_orm: Optional[object],
    alerts_list: list,
    events_list: list,
    window_type: str,
    window_start: datetime,
    window_end: datetime,
) -> AnalyticsDashboardView:
    """Build the complete analytics dashboard view model.

    This is the ONLY view model passed to the template.
    Everything else is pre-computed here.

    Eliminates template-level:
    - All Jinja |format() filters
    - All .strftime() date formatting
    - All alert lookup namespace construction
    - All threshold-based conditional logic
    - All trend direction logic

    Args:
        snapshot_orm: AnalyticsWindowView ORM object (or None)
        alerts_list: List of Alert ORM objects (currently empty)
        events_list: List of AuditEvent ORM objects
        window_type: "week", "month", "pay_cycle", "rent_cycle"
        window_start: Start of time window (UTC)
        window_end: End of time window (UTC)

    Returns:
        AnalyticsDashboardView frozen dataclass
    """
    # Format time window display
    display_window_start = window_start.strftime('%b %d')
    display_window_end = window_end.strftime('%b %d, %Y')

    # If no snapshot, return minimal view
    if not snapshot_orm:
        return AnalyticsDashboardView(
            display_window_start=display_window_start,
            display_window_end=display_window_end,
            window_type=window_type,
            cwi_value=Decimal('0'),
            display_cwi_value='$0.00/week',
            cwi_status_color='secondary',
            cwi_status_label='No data',
            metrics=[],
            alerts_by_key={},
            all_alerts=[],
            alert_count=0,
            recent_events=[],
            has_snapshot=False,
            display_no_data_message='No analytics data available yet. Analytics will appear once students start participating.',
        )

    # Build CWI context
    cwi_value = Decimal(str(snapshot_orm.cwi_value)) if hasattr(snapshot_orm, 'cwi_value') else Decimal('0')
    display_cwi_value = f"${float(cwi_value):.2f}/week"

    # Determine CWI status (threshold-based)
    # Placeholder thresholds - adjust based on actual business rules
    cwi_decimal = Decimal(str(cwi_value)) if not isinstance(cwi_value, Decimal) else cwi_value
    if cwi_decimal >= Decimal('50'):
        cwi_status_color = 'success'
        cwi_status_label = 'Healthy'
    elif cwi_decimal >= Decimal('30'):
        cwi_status_color = 'warning'
        cwi_status_label = 'Caution'
    else:
        cwi_status_color = 'danger'
        cwi_status_label = 'Critical'

    # Build metrics list
    metrics = []

    # Participation Rate metric
    if hasattr(snapshot_orm, 'participation_rate'):
        participation_metric = build_metric_snapshot_view(
            metric_name='Participation Rate',
            icon_name='group',
            current_value=Decimal(str(snapshot_orm.participation_rate)),
            previous_value=None,  # No prior data available in snapshot
            threshold_low=Decimal('50'),
            threshold_high=Decimal('70'),
            format_as='percent',
        )
        metrics.append(participation_metric)

    # Money Velocity metric
    if hasattr(snapshot_orm, 'money_velocity'):
        velocity_metric = build_metric_snapshot_view(
            metric_name='Money Velocity',
            icon_name='speed',
            current_value=Decimal(str(snapshot_orm.money_velocity)),
            previous_value=None,  # No prior data available in snapshot
            threshold_low=Decimal('1.0'),
            threshold_high=Decimal('2.0'),
            format_as='decimal',
        )
        metrics.append(velocity_metric)

    # On-Track Students metric
    if hasattr(snapshot_orm, 'cwi_deviation_within_20pct'):
        ontrack_metric = build_metric_snapshot_view(
            metric_name='On-Track Students',
            icon_name='target',
            current_value=Decimal(str(snapshot_orm.cwi_deviation_within_20pct)),
            previous_value=None,  # No prior data available in snapshot
            threshold_low=Decimal('60'),
            threshold_high=Decimal('80'),
            format_as='percent',
        )
        metrics.append(ontrack_metric)

    # Budget Survival metric
    if hasattr(snapshot_orm, 'budget_survival_pass_rate'):
        budget_metric = build_metric_snapshot_view(
            metric_name='Budget Survival',
            icon_name='account_balance',
            current_value=Decimal(str(snapshot_orm.budget_survival_pass_rate)),
            previous_value=None,  # No prior data available in snapshot
            threshold_low=Decimal('60'),
            threshold_high=Decimal('80'),
            format_as='percent',
        )
        metrics.append(budget_metric)

    # Build alerts (currently empty, structure ready for future)
    alerts_by_key = {}
    all_alerts = []
    for alert in alerts_list:
        alert_view = build_alert_card_view(alert)
        if alert_view:
            all_alerts.append(alert_view)
            alerts_by_key[alert_view.alert_key] = alert_view

    alert_count = len([a for a in all_alerts if not a.is_acknowledged])

    # Build recent events
    recent_events = []
    for event in events_list:
        event_view = build_recent_event_view(event)
        if event_view:
            recent_events.append(event_view)

    return AnalyticsDashboardView(
        display_window_start=display_window_start,
        display_window_end=display_window_end,
        window_type=window_type,
        cwi_value=cwi_value,
        display_cwi_value=display_cwi_value,
        cwi_status_color=cwi_status_color,
        cwi_status_label=cwi_status_label,
        metrics=metrics,
        alerts_by_key=alerts_by_key,
        all_alerts=all_alerts,
        alert_count=alert_count,
        recent_events=recent_events,
        has_snapshot=True,
        display_no_data_message=None,
    )
