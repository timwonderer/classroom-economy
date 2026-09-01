"""Slice 8.4d — V1 Analytics retirement guards.

DOM-ITR has replaced V1 Analytics; it is no longer sitting beside it. These guards
prove the retired V1 interpretation authority is gone from runtime:

    runtime references to AnalyticsEngine            = 0
    runtime references to suggested_action           = 0
    runtime references to ANALYTICS_POLICY_DEFAULTS   = 0

plus the retired modules are unimportable and the retired routes are unreachable.

Historical records (docs/archive, LOGS/AUDITS, tests) are intentionally out of
scope — the retirement does not distort history to satisfy a global grep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[1] / "app"

# Retired V1 interpretation authority — must not appear in runtime source.
_RETIRED_SYMBOLS = (
    "AnalyticsEngine",
    "suggested_action",
    "ANALYTICS_POLICY_DEFAULTS",
    "get_analytics_policy",
    "build_analytics_dashboard_view",
    "generate_alerts",
    "AnalyticsWindowView",
    "AnalyticsDashboardView",
)


def _runtime_hits(symbol: str) -> list[str]:
    hits = []
    for path in _APP.rglob("*.py"):
        if symbol in path.read_text():
            hits.append(str(path.relative_to(_APP.parent)))
    return hits


@pytest.mark.parametrize("symbol", _RETIRED_SYMBOLS)
def test_retired_symbol_absent_from_runtime(symbol):
    assert _runtime_hits(symbol) == [], f"{symbol} still referenced in runtime"


def test_retired_modules_are_unimportable():
    import importlib

    for module in ("app.utils.analytics_engine", "app.services.analytics.builders",
                   "app.services.analytics"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)


def test_only_the_interpretation_route_survives(app):
    analytics_rules = {
        rule.endpoint for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/admin/interpretation")
    }
    # The Interpretation page is the sole surviving analytics-blueprint route; the
    # V1 snapshot/alerts/acknowledge/events/student drill-down endpoints are gone.
    assert analytics_rules == {"analytics.dashboard"}


def test_economy_policy_modes_still_intact(app):
    # Retirement removed the analytics thresholds only — the legitimate economy
    # policy modes (tight/default/comfortable) are untouched.
    from app.utils.economy_policy import POLICY_MODES, get_policy_profile

    assert {"tight", "default", "comfortable"} <= set(POLICY_MODES)
    assert get_policy_profile("default") is not None
