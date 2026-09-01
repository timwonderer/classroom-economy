"""Frozen ``reference_configuration`` capture for cycle materialization (DOM-ITR-001 §IX §VII).

At the closed-cycle boundary the materialization writer freezes a **versioned,
immutable informational projection** of the economic configuration that governed
the cycle, so a materialized ``interpretation_cycle_record`` is self-describing and
is never reinterpreted against later configuration. This module builds that
projection from authoritative CLASS/economic reads only.

The projection is explicitly:
* **informational** — never executable CLASS state; nothing reads it to make an
  economic decision (§IX),
* **not a cross-domain FK** — ``policy.policy_uuid`` / ``policy.version`` are
  informational lineage strings (INV-ARC-021 §V.7),
* **versioned** via its own ``schema_version`` so the Economic Engine can evolve
  without churning this table.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models import PolicyVersion
from app.services.class_configuration_query_service import (
    calculate_cwi,
    get_payroll_settings,
    resolve_expected_weekly_hours,
)

# Version of the reference_configuration projection shape (independent of the
# observations_json schema_version and of SPEC-ITR-001's version).
REFERENCE_CONFIGURATION_SCHEMA_VERSION = 1


def _money(value) -> str | None:
    """Two-place canonical decimal string, or ``None`` when unset."""
    if value is None:
        return None
    return f"{Decimal(str(value)).quantize(Decimal('0.01'))}"


def _num(value) -> str | None:
    """Normalized canonical decimal string, or ``None`` when unset."""
    if value is None:
        return None
    return str(Decimal(str(value)).normalize())


def capture_reference_configuration(class_id: str) -> dict[str, Any]:
    """Freeze the governing economic reference values for ``class_id`` (§IX).

    Deterministic for stable configuration: two captures over unchanged
    configuration produce an identical dict, which is what makes idempotent replay
    of a materialization safe. All numeric values are canonical decimal **strings**
    (or ``None`` when the input is unconfigured — an honest absence, not zero).
    """
    payroll = get_payroll_settings(class_id)
    hourly_pay_rate = None
    if payroll is not None and payroll.pay_rate is not None:
        # pay_rate is stored as $/minute; the CWI reference uses $/hour.
        hourly_pay_rate = Decimal(str(payroll.pay_rate)) * 60

    active_policy = (
        PolicyVersion.query
        .filter_by(class_id=class_id, domain="payroll", is_active=True)
        .order_by(PolicyVersion.version_number.desc())
        .first()
    )

    return {
        "schema_version": REFERENCE_CONFIGURATION_SCHEMA_VERSION,
        "economic_engine": {
            "cwi": _money(calculate_cwi(class_id)),
            "expected_weekly_hours": _num(resolve_expected_weekly_hours(class_id)),
            "hourly_pay_rate": _money(hourly_pay_rate),
        },
        "policy": {
            "policy_uuid": active_policy.policy_uuid if active_policy else None,
            "version": str(active_policy.version_number) if active_policy else None,
        },
    }
