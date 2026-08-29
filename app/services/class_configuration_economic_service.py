"""
Class Configuration domain — Economic view for presentation consumers.

Phase 5: Builds presentation-ready economic guidance for other domains.
Encapsulates CWI calculations, pricing recommendations, and economy health.
This service is the authoritative source for economic presentation data.

Consumers (Store, Obligations, etc.) consume EconomicView, not PayrollSettings.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.services.class_configuration_query_service import (
    get_effective_economic_engine,
    get_payroll_settings,
    get_policy_mode,
    resolve_expected_weekly_hours,
    validate_payroll_rate,
)


_CWI_PRICING_DIVISORS = {"low": 20.0, "medium": 10.0, "high": 5.0}
_DEFAULT_PRICING = MappingProxyType({"low": 5.0, "medium": 10.0, "high": 15.0})


@dataclass(frozen=True)
class EconomicView:
    """Presentation-ready economic guidance for consuming domains."""
    suggested_pricing_range: MappingProxyType
    economy_health: int
    warnings: tuple[str, ...]
    display_context: MappingProxyType


def _resolve_expected_weekly_hours(class_id: str) -> float | None:
    """Read expected_weekly_hours from the EconomicEngine governing payroll."""
    return resolve_expected_weekly_hours(class_id)


def _compute_cwi_from_payroll(payroll, expected_weekly_hours) -> float | None:
    """Compute CWI given already-resolved payroll row and expected_weekly_hours.

    NOTE (SPEC-ECON-003 migration): the canonical CWI calculation authority is
    ``app/services/economic_engine.resolve_base`` (per SPEC-ECON-003 §3/§4.1). This
    is a pre-existing duplicate formula site retained during the conservative
    migration; it should be consolidated to consume ``resolve_base`` once parity is
    proven for this presentation surface. Numerically identical today:
    ``pay_rate_per_minute × 60 × expected_weekly_hours``.
    """
    if payroll is None or expected_weekly_hours is None:
        return None
    return (float(payroll.pay_rate) * 60) * float(expected_weekly_hours)


def build_economic_view(class_id: str) -> EconomicView:
    """Build presentation-ready economic guidance for a class.

    Uses real CWI, payroll settings, and policy mode from the query service.
    Pricing suggestions scale from CWI when available.
    """
    payroll = get_payroll_settings(class_id)
    policy_mode = get_policy_mode(class_id)
    expected_weekly_hours = _resolve_expected_weekly_hours(class_id)
    cwi = _compute_cwi_from_payroll(payroll, expected_weekly_hours)

    warnings: list[str] = []
    display_context: dict[str, Any] = {}

    if expected_weekly_hours is not None:
        display_context["expected_weekly_hours"] = expected_weekly_hours

    if payroll:
        hourly_rate = float(payroll.pay_rate) * 60
        display_context["hourly_rate"] = hourly_rate
        is_valid, rate_warning = validate_payroll_rate(
            hourly_rate,
            policy_mode or "default",
        )
        if rate_warning:
            warnings.append(rate_warning)
        if not is_valid:
            cwi = None

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
        elif expected_weekly_hours is None:
            warnings.append("Expected weekly hours not set — economy health unknown")

    return EconomicView(
        suggested_pricing_range=MappingProxyType(pricing),
        economy_health=health,
        warnings=tuple(warnings),
        display_context=MappingProxyType(display_context),
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
