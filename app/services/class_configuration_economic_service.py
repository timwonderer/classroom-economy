"""
Class Configuration domain — Economic view for presentation consumers.

Phase 5-7: Builds presentation-ready economic guidance for other domains.
Encapsulates CWI calculations, pricing recommendations, and economy health.
This service is the authoritative source for economic presentation data.

Consumers (Store, Obligations, etc.) consume EconomicView, not PayrollSettings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EconomicView:
    """
    Presentation-ready economic guidance for consuming domains.

    Encapsulates:
    - Suggested pricing ranges (based on economy health)
    - Economy health indicators (sufficient liquidity, inflation concerns)
    - Warnings for teachers (economy imbalances, thresholds)

    Consumers do NOT see intermediate calculations (CWI, hourly rates, etc.).
    They see only presentation concepts needed for the UI.
    """
    # Suggested pricing guidance for teachers
    suggested_pricing_range: dict[str, Any]  # e.g., {"low": 5.0, "medium": 10.0, "high": 15.0}

    # Economy health indicator (0-100)
    economy_health: int  # 0 = critical, 100 = thriving

    # Teacher-facing warnings (empty list if no issues)
    warnings: list[str]

    # Context for UI
    display_context: dict[str, Any]  # e.g., {"expected_weekly_hours": 5.0, "class_size": 20}


def build_economic_view(class_id: str) -> EconomicView:
    """
    Build presentation-ready economic guidance for a class.

    This is a stub implementation until the Class Configuration domain
    implements full economic analysis. Returns placeholder values for now.

    Args:
        class_id: The class to analyze

    Returns:
        EconomicView with presentation-ready guidance

    TODO (Class Configuration domain, Phase 7+):
    - Implement CWI calculations for the class
    - Analyze balance distribution and inflation
    - Generate pricing recommendations based on economy health
    - Identify warnings (low liquidity, high inflation, etc.)
    """
    # STUB: Placeholder values until Class Configuration domain implements
    return EconomicView(
        suggested_pricing_range={
            "low": 5.0,
            "medium": 10.0,
            "high": 15.0,
        },
        economy_health=75,  # Placeholder: healthy economy
        warnings=[],  # No warnings in stub implementation
        display_context={
            "expected_weekly_hours": 5.0,  # Placeholder default
        },
    )
