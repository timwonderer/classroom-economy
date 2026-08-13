"""
Class Configuration domain — Economic view for presentation consumers.

Phase 5: Builds presentation-ready economic guidance for other domains.
Encapsulates CWI calculations, pricing recommendations, and economy health.
This service is the authoritative source for economic presentation data.

Consumers (Store, Obligations, etc.) consume EconomicView, not PayrollSettings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.class_configuration_query_service import (
    calculate_cwi,
    get_payroll_settings,
    get_policy_mode,
    validate_payroll_rate,
)


_CWI_PRICING_DIVISORS = {"low": 20.0, "medium": 10.0, "high": 5.0}
_DEFAULT_PRICING = {"low": 5.0, "medium": 10.0, "high": 15.0}


@dataclass(frozen=True)
class EconomicView:
    """Presentation-ready economic guidance for consuming domains."""
    suggested_pricing_range: dict[str, Any]
    economy_health: int
    warnings: list[str]
    display_context: dict[str, Any]


def build_economic_view(class_id: str) -> EconomicView:
    """Build presentation-ready economic guidance for a class.

    Uses real CWI, payroll settings, and policy mode from the query service.
    Pricing suggestions scale from CWI when available.
    """
    cwi = calculate_cwi(class_id)
    payroll = get_payroll_settings(class_id)
    policy_mode = get_policy_mode(class_id)

    warnings: list[str] = []
    display_context: dict[str, Any] = {}

    if payroll and payroll.expected_weekly_hours is not None:
        display_context["expected_weekly_hours"] = float(payroll.expected_weekly_hours)

    if payroll:
        hourly_rate = float(payroll.pay_rate) * 60
        display_context["hourly_rate"] = hourly_rate
        if policy_mode:
            _, rate_warning = validate_payroll_rate(hourly_rate, policy_mode)
            if rate_warning:
                warnings.append(rate_warning)

    if policy_mode:
        display_context["policy_mode"] = policy_mode

    if cwi is not None and cwi > 0:
        pricing = {
            tier: round(cwi / divisor, 2)
            for tier, divisor in _CWI_PRICING_DIVISORS.items()
        }
        health = _estimate_health(cwi, policy_mode)
    else:
        pricing = dict(_DEFAULT_PRICING)
        health = 50
        if payroll is None:
            warnings.append("Payroll not configured — economy health unknown")

    return EconomicView(
        suggested_pricing_range=pricing,
        economy_health=health,
        warnings=warnings,
        display_context=display_context,
    )


def _estimate_health(cwi: float, policy_mode: str | None) -> int:
    """Heuristic economy health score based on CWI and policy mode."""
    if policy_mode == "tight":
        thresholds = (50, 150, 400)
    elif policy_mode == "comfortable":
        thresholds = (200, 600, 1500)
    else:
        thresholds = (100, 400, 1000)

    if cwi < thresholds[0]:
        return 25
    if cwi < thresholds[1]:
        return 50
    if cwi < thresholds[2]:
        return 75
    return 90
