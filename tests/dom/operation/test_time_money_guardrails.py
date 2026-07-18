"""
Guardrail tests to prevent regressions in datetime and money handling.
"""

from pathlib import Path
import re

import pytest


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _iter_python_files():
    for path in APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


@pytest.fixture(scope="module")
def app_python_sources():
    """Cache all app/*.py file contents once per test module."""
    sources = []
    for path in _iter_python_files():
        sources.append((path.as_posix(), path.read_text(encoding="utf-8")))
    return sources


def test_DOM_OPS_001__no_direct_datetime_now_calls_outside_time_util(app_python_sources):
    offenders = []
    for path, text in app_python_sources:
        if path.endswith("app/utils/time.py"):
            continue
        if re.search(r"\bdatetime\.utcnow\(", text) or re.search(r"\bdatetime\.now\(", text):
            offenders.append(path)

    assert not offenders, f"Use utc_now() helper instead of direct datetime.now/utcnow: {offenders}"


def test_DOM_OPS_001__no_ad_hoc_replace_tzinfo_utc_outside_time_util(app_python_sources):
    offenders = []
    for path, text in app_python_sources:
        if path.endswith("app/utils/time.py"):
            continue
        if re.search(r"replace\(tzinfo=timezone\.utc\)", text):
            offenders.append(path)

    assert not offenders, f"Use ensure_utc() instead of ad-hoc replace(tzinfo=timezone.utc): {offenders}"


def test_DOM_OPS_001__no_generic_float_zero_fallbacks_in_routes(app_python_sources):
    """
    Prevent reintroducing ambiguous float defaults in route logic.
    """
    allowed_line_patterns = (
        "hold_seconds = 0.0",
        "gate_hold_seconds = 0.0",
    )

    offenders = []
    for path, source in app_python_sources:
        if "/app/routes/" not in path:
            continue
        lines = source.splitlines()
        for idx, line in enumerate(lines, start=1):
            if not re.search(r"(?<![\d])0\.0(?!\d)", line):
                continue
            if any(token in line for token in allowed_line_patterns):
                continue
            offenders.append(f"{path}:{idx}")

    assert not offenders, f"Use Decimal-safe defaults or explicit non-money justification: {offenders}"


def test_DOM_OPS_001__no_unscoped_temporal_bounds_helpers(app_python_sources):
    """
    Enforce INV-ARC-015 call-site discipline.

    day/week/month bounds helpers must be invoked with explicit class-temporal
    scope (timezone_name or class_id).
    """
    call_pattern = re.compile(r"\b(day_bounds_utc|week_bounds_utc|month_bounds_utc)\((.*?)\)", re.DOTALL)
    offenders = []

    target_paths = {
        "app/services/attendance_service.py",
        "app/attendance.py",
        "app/routes/student.py",
        "app/scheduled_tasks.py",
        "app/utils/insurance_eligibility.py",
    }

    for path, source in app_python_sources:
        if path.endswith("app/utils/time.py"):
            continue
        if not any(path.endswith(target) for target in target_paths):
            continue

        for match in call_pattern.finditer(source):
            helper = match.group(1)
            args = match.group(2)
            if "timezone_name=" in args or "class_id" in args:
                continue
            start_line = source.count("\n", 0, match.start()) + 1
            offenders.append(f"{path}:{start_line}:{helper}")

    assert not offenders, (
        "Temporal bounds helpers must be class/timezone scoped "
        "(pass timezone_name=... or class_id context): "
        f"{offenders}"
    )
