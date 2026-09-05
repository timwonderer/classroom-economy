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
        'max_time_per_day', 'max_time_per_day_unit', 'rounding_mode',
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


def _current_payroll_settings(class_id: str) -> PayrollSettings | None:
    """The payroll policy currently in force for a class, or None.

    Scoped by ``class_id`` alone, matching the partial unique index and the
    reader in ``class_configuration_query_service``. ``block`` is display
    metadata, never a scoping key (CLAUDE.md §7 / INV-ARC-019).

    Deterministic by construction: ``created_at`` collides for rows written in
    the same request, so ``id`` supplies the total order.
    """
    return (
        PayrollSettings.query
        .filter_by(class_id=class_id, availability_state='IN_USE')
        .order_by(PayrollSettings.created_at.desc(), PayrollSettings.id.desc())
        .first()
    )


# Columns a submission may set. Anything else in `settings_data` is a caller
# error rather than something to silently drop onto the row.
_SUBMITTABLE_FIELDS = PayrollSettings._FROZEN_POLICY_FIELDS + ('next_payroll_date',)


def upsert_payroll_settings(*, class_id: str, settings_data: dict) -> PayrollSettings:
    """Record a payroll policy submission as a NEW immutable row.

    `class_id` is the sole scoping key (DOM-CLASS-001 / INV-ARC-019).

    Despite the name — kept so the many call sites stay stable — this never
    updates in place. DOM-POL-001 §VI.1: "Any submission — first-time or
    resubmission — produces a new `policy_uuid`. The backend MUST NOT infer
    whether a change is meaningful; a submission is a new contract." The
    predecessor is retired in the same transaction, which is what keeps the
    partial unique index on (class_id, block) WHERE IN_USE satisfiable.

    Fields the submission does not mention are carried forward from the
    predecessor, so a partial form post still yields a complete contract rather
    than a row of column defaults.

    Also creates and activates a new `PolicyVersion` snapshot for the payroll
    domain. That lineage is DOM-CLASS-003 economic-policy evolution — a distinct
    concern from this row's own versioning, and not a "current version" pointer
    for it (DOM-POL-001 §VI.0).
    """
    unknown = set(settings_data) - set(_SUBMITTABLE_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown payroll settings field(s): {sorted(unknown)}. "
            "Payroll policy columns are enumerated by PayrollSettings._FROZEN_POLICY_FIELDS."
        )

    predecessor = _current_payroll_settings(class_id)

    carried = {}
    if predecessor is not None:
        carried = {
            field: getattr(predecessor, field)
            for field in _SUBMITTABLE_FIELDS
        }
    carried.update(settings_data)

    setting = PayrollSettings(class_id=class_id, availability_state='IN_USE', **carried)
    setting.created_at = utc_now()
    setting.updated_at = setting.created_at

    # Retire the predecessor BEFORE the insert is flushed so the partial unique
    # index never sees two IN_USE rows for the scope.
    if predecessor is not None:
        predecessor.availability_state = 'RETIRED'
        db.session.flush()

    db.session.add(setting)
    db.session.flush()

    _activate_payroll_policy_version(class_id, setting)
    return setting


# NOTE: `expected_weekly_hours` was moved from `PayrollSettings` to `EconomicEngine`
# (canonical per DOM-CLASS-002). It is a CWI parameter, not a payroll parameter.
# Updates are performed via FEAT-CLASS-005 (`execute_evolve_economic_engine`
# with `updates={"expected_weekly_hours": ...}`), which creates a new immutable
# engine version. See `app/feats/class_configuration/feat_class_005_...`.
