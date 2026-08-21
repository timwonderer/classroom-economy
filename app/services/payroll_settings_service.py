from __future__ import annotations

import json
from decimal import Decimal

from app.extensions import db
from app.models import ClassEconomy, PayrollSettings, PolicyVersion
from app.utils.canonical_temporal_resolver import utc_now


def _payload_json_from_settings(setting: PayrollSettings) -> str:
    """Serialize a PayrollSettings row into the PolicyVersion payload JSON."""
    def _norm(v):
        if isinstance(v, Decimal):
            return str(v)
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        return v

    fields = (
        'settings_mode', 'pay_rate', 'time_unit', 'payroll_frequency_days',
        'first_pay_date', 'daily_limit_hours', 'pay_schedule_type',
        'pay_schedule_custom_value', 'pay_schedule_custom_unit',
        'overtime_enabled', 'overtime_threshold', 'overtime_threshold_unit',
        'overtime_threshold_period', 'overtime_multiplier',
        'max_time_per_day', 'max_time_per_day_unit', 'rounding_mode', 'is_active',
    )
    payload = {k: _norm(getattr(setting, k, None)) for k in fields}
    return json.dumps(payload, sort_keys=True, default=str)


def _activate_payroll_policy_version(class_id: str, setting: PayrollSettings) -> PolicyVersion:
    """Create and activate a new PolicyVersion snapshot for the payroll domain.

    Any prior active version for (class_id, domain='payroll') is deactivated. The
    payload is a canonical JSON snapshot of the current PayrollSettings row. The
    version_number auto-increments per class+domain.
    """
    now = utc_now()

    # Serialize version allocation per class, including the first activation
    # where no existing PolicyVersion row exists yet.
    db.session.query(ClassEconomy.class_id).filter(
        ClassEconomy.class_id == class_id,
    ).with_for_update().one()

    # Deactivate any existing active payroll version(s).
    existing_active = PolicyVersion.query.filter_by(
        class_id=class_id, domain='payroll', is_active=True,
    ).all()
    for row in existing_active:
        row.is_active = False

    # Next version number
    last = (
        PolicyVersion.query.filter_by(class_id=class_id, domain='payroll')
        .order_by(PolicyVersion.version_number.desc())
        .first()
    )
    next_version = (last.version_number + 1) if last else 1

    version = PolicyVersion(
        class_id=class_id,
        domain='payroll',
        version_number=next_version,
        policy_payload_json=_payload_json_from_settings(setting),
        created_at=now,
        activated_at=now,
        is_active=True,
    )
    db.session.add(version)
    db.session.flush()
    return version


def upsert_payroll_settings(*, class_id: str, settings_data: dict) -> PayrollSettings:
    """Create or update the canonical class-scoped payroll settings row.

    `class_id` is the sole scoping key (DOM-CLASS-001 / INV-ARC-019). There is no
    concept of "multiple blocks" for a class — a teacher's canonical context is
    exactly one class at a time.

    Also creates and activates a new `PolicyVersion` snapshot for the payroll
    domain so downstream payroll runs can reference an active version.
    """
    setting = PayrollSettings.query.filter_by(class_id=class_id).first()
    if not setting:
        setting = PayrollSettings(class_id=class_id)

    for key, value in settings_data.items():
        setattr(setting, key, value)

    setting.updated_at = utc_now()
    db.session.add(setting)
    db.session.flush()

    _activate_payroll_policy_version(class_id, setting)
    return setting


# NOTE: `expected_weekly_hours` was moved from `PayrollSettings` to `EconomicEngine`
# (canonical per DOM-CLASS-002). It is a CWI parameter, not a payroll parameter.
# Updates are performed via FEAT-CLASS-005 (`execute_evolve_economic_engine`
# with `updates={"expected_weekly_hours": ...}`), which creates a new immutable
# engine version. See `app/feats/class_configuration/feat_class_005_...`.
