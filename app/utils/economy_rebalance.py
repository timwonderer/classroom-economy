from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
import sqlalchemy as sa
from typing import Any

from app.extensions import db
from app.models import (
    ClassEconomy,
    FeatureSettings,
    InsurancePolicy,
    PolicyTransition,
    PolicyVersion,
    RentSettings,
)
from app.utils.time import ensure_utc, utc_now


REBALANCE_ACTIVATION_IMMEDIATE = "immediate"
REBALANCE_ACTIVATION_NEXT_RENEWAL = "next_renewal"
REBALANCE_ACTIVATION_NEXT_PAYROLL = "next_payroll"
REBALANCE_TRIGGER_INSURANCE_RENEWAL = "insurance_renewal"
POLICY_TRANSITION_STATUS_PENDING = "pending"
POLICY_TRANSITION_STATUS_APPLIED = "applied"
POLICY_TRANSITION_STATUS_CANCELLED = "cancelled"
POLICY_TRANSITION_STATUS_SUPERSEDED = "superseded"

REBALANCE_DOMAIN_RENT = "rent"
REBALANCE_DOMAIN_INSURANCE = "insurance"


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None


def _get_rent_effective_at(settings, reference_time: datetime) -> datetime:
    from app.routes.student import _add_rent_period, _calculate_rent_timeline, _get_rent_period_delta

    timeline = _calculate_rent_timeline(settings, reference_time)
    upcoming_due_date = timeline.get("upcoming_due_date")
    if upcoming_due_date is None:
        return reference_time
    return _add_rent_period(upcoming_due_date, _get_rent_period_delta(settings))


def prepare_scheduled_rebalance_changes(change_plan, *, rent_settings=None, insurance_policies=None, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    insurance_by_id = {policy.id: policy for policy in (insurance_policies or [])}
    scheduled_changes = []

    for change in change_plan:
        enriched_change = dict(change)
        effective_at = None

        if change.get("type") == "rent" and rent_settings is not None:
            effective_at = _get_rent_effective_at(rent_settings, reference_time)
        elif change.get("type") == "insurance":
            policy = insurance_by_id.get(change.get("policy_id"))
            if policy is not None:
                enriched_change["activation_event"] = REBALANCE_TRIGGER_INSURANCE_RENEWAL
                enriched_change["activation_policy_id"] = policy.id

        enriched_change["effective_at"] = _serialize_dt(effective_at)
        scheduled_changes.append(enriched_change)

    return scheduled_changes


def _domain_for_change(change: dict[str, Any]) -> str | None:
    change_type = (change.get("type") or "").strip().lower()
    if change_type == "rent":
        return REBALANCE_DOMAIN_RENT
    if change_type == "insurance":
        return REBALANCE_DOMAIN_INSURANCE
    return None


def _canonical_change_payload(change: dict[str, Any]) -> str:
    allowed_keys = (
        "type",
        "block",
        "join_code",
        "policy_id",
        "title",
        "current_value",
        "new_value",
        "effective_at",
        "activation_event",
        "activation_policy_id",
    )
    payload = {key: change.get(key) for key in allowed_keys if change.get(key) is not None}
    return json.dumps(payload, sort_keys=True)


def _transition_conflict_key(domain: str, change: dict[str, Any]) -> str:
    if domain == REBALANCE_DOMAIN_RENT:
        return f"rent:{(change.get('block') or '').strip().upper()}"
    if domain == REBALANCE_DOMAIN_INSURANCE:
        return f"insurance:{change.get('policy_id')}"
    return domain


def _next_policy_version_number(class_id: str, domain: str) -> int:
    current_max = (
        db.session.query(sa.func.max(PolicyVersion.version_number))
        .filter(PolicyVersion.class_id == class_id, PolicyVersion.domain == domain)
        .scalar()
    )
    return int(current_max or 0) + 1


def _get_active_policy_version(class_id: str, domain: str) -> PolicyVersion | None:
    return (
        PolicyVersion.query.filter_by(
            class_id=class_id,
            domain=domain,
            is_active=True,
        )
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .first()
    )


def _supersede_pending_transitions(
    class_id: str,
    domain: str,
    superseding_transition_id: int,
    *,
    reference_time: datetime,
    conflict_key: str | None = None,
) -> None:
    pending = (
        PolicyTransition.query.filter(
            PolicyTransition.class_id == class_id,
            PolicyTransition.domain == domain,
            PolicyTransition.status == POLICY_TRANSITION_STATUS_PENDING,
            PolicyTransition.id != superseding_transition_id,
        )
        .all()
    )
    for transition in pending:
        if conflict_key:
            target = db.session.get(PolicyVersion, transition.target_policy_version_id)
            if not target:
                continue
            try:
                payload = json.loads(target.policy_payload_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            pending_key = _transition_conflict_key(domain, payload)
            if pending_key != conflict_key:
                continue
        transition.status = POLICY_TRANSITION_STATUS_SUPERSEDED
        transition.superseded_by_transition_id = superseding_transition_id
        transition.applied_at = reference_time


def _create_policy_transition(
    *,
    class_id: str,
    domain: str,
    change_payload: dict[str, Any],
    activation_mode: str,
    created_by: int,
    status: str,
    reference_time: datetime,
    applied_at: datetime | None = None,
    correlation_id: str | None = None,
) -> PolicyTransition:
    source_version = _get_active_policy_version(class_id, domain)
    conflict_key = _transition_conflict_key(domain, change_payload)
    target_version = PolicyVersion(
        class_id=class_id,
        domain=domain,
        version_number=_next_policy_version_number(class_id, domain),
        policy_payload_json=_canonical_change_payload(change_payload),
        created_at=reference_time,
        activated_at=applied_at if status == POLICY_TRANSITION_STATUS_APPLIED else None,
        is_active=status == POLICY_TRANSITION_STATUS_APPLIED,
    )
    db.session.add(target_version)
    db.session.flush()

    transition = PolicyTransition(
        class_id=class_id,
        domain=domain,
        source_policy_version_id=source_version.id if source_version else None,
        target_policy_version_id=target_version.id,
        activation_mode=activation_mode,
        status=status,
        created_at=reference_time,
        created_by=created_by,
        applied_at=applied_at if status == POLICY_TRANSITION_STATUS_APPLIED else None,
        correlation_id=correlation_id,
    )
    db.session.add(transition)
    db.session.flush()
    target_version.created_by_transition_id = transition.id

    if status == POLICY_TRANSITION_STATUS_APPLIED:
        if source_version:
            source_version.is_active = False
        _supersede_pending_transitions(
            class_id,
            domain,
            transition.id,
            reference_time=applied_at or reference_time,
            conflict_key=conflict_key,
        )
    elif status == POLICY_TRANSITION_STATUS_PENDING:
        _supersede_pending_transitions(
            class_id,
            domain,
            transition.id,
            reference_time=reference_time,
            conflict_key=conflict_key,
        )

    return transition


def _create_policy_transitions_for_changes(
    settings_row,
    changes: list[dict[str, Any]],
    *,
    activation_mode: str,
    created_by: int,
    status: str,
    reference_time: datetime,
    applied_at: datetime | None = None,
) -> list[PolicyTransition]:
    class_id = getattr(settings_row, "class_id", None)
    if not class_id:
        return []

    created: list[PolicyTransition] = []
    for idx, change in enumerate(changes):
        domain = _domain_for_change(change)
        if not domain:
            continue
        correlation_id = f"rebalance:{class_id}:{domain}:{int(reference_time.timestamp())}:{idx}"
        created.append(
            _create_policy_transition(
                class_id=class_id,
                domain=domain,
                change_payload=change,
                activation_mode=activation_mode,
                created_by=created_by,
                status=status,
                reference_time=reference_time,
                applied_at=applied_at,
                correlation_id=correlation_id,
            )
        )
    return created


def cancel_pending_policy_transitions(class_id: str | None, *, actor_id: int, reference_time: datetime | None = None) -> int:
    if not class_id:
        return 0
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    pending = PolicyTransition.query.filter_by(
        class_id=class_id,
        status=POLICY_TRANSITION_STATUS_PENDING,
    ).all()
    for transition in pending:
        transition.status = POLICY_TRANSITION_STATUS_CANCELLED
        transition.cancelled_at = reference_time
        transition.applied_at = reference_time
        transition.created_by = actor_id
    return len(pending)


def _get_pending_policy_transitions_for_class(class_id: str | None):
    if not class_id:
        return []
    return (
        PolicyTransition.query.filter_by(
            class_id=class_id,
            status=POLICY_TRANSITION_STATUS_PENDING,
        )
        .order_by(PolicyTransition.created_at.asc(), PolicyTransition.id.asc())
        .all()
    )


def get_pending_policy_transition_count(class_id: str | None) -> int:
    if not class_id:
        return 0
    return (
        db.session.query(sa.func.count(PolicyTransition.id))
        .filter(
            PolicyTransition.class_id == class_id,
            PolicyTransition.status == POLICY_TRANSITION_STATUS_PENDING,
        )
        .scalar()
        or 0
    )


def get_pending_policy_transition_effective_at(class_id: str | None) -> datetime | None:
    pending = _get_pending_policy_transitions_for_class(class_id)
    effective_candidates: list[datetime] = []
    for transition in pending:
        target = db.session.get(PolicyVersion, transition.target_policy_version_id)
        if not target:
            continue
        try:
            payload = json.loads(target.policy_payload_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        effective_at_raw = payload.get("effective_at")
        if not effective_at_raw:
            continue
        try:
            effective_candidates.append(ensure_utc(datetime.fromisoformat(effective_at_raw)))
        except (TypeError, ValueError):
            continue
    if effective_candidates:
        return min(effective_candidates)
    return None


def _get_effective_rent_settings(class_id: str | None):
    if not class_id:
        return None
    return (
        RentSettings.query.filter_by(
            class_id=class_id,
            is_enabled=True,
        )
        .order_by(RentSettings.block.isnot(None).desc(), RentSettings.id.desc())
        .first()
    )


def _apply_change_list(teacher_id, settings_row, changes, activation_mode, *, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    applied_labels = []
    applied_changes: list[dict[str, Any]] = []
    class_id = getattr(settings_row, "class_id", None)

    for change in changes:
        change_type = change.get("type")
        if change_type == "rent":
            rent_settings = _get_effective_rent_settings(class_id)
            if rent_settings:
                rent_settings.rent_amount = Decimal(str(change.get("new_value")))
                applied_labels.append("Rent")
                applied_changes.append(dict(change))
        elif change_type == "insurance":
            policy = InsurancePolicy.query.filter_by(
                class_id=class_id,
                id=change.get("policy_id"),
                is_active=True,
            ).first()
            if policy:
                policy.premium = Decimal(str(change.get("new_value")))
                applied_labels.append(f"Insurance: {policy.title}")
                applied_changes.append(dict(change))

    if applied_labels:
        settings_row.economy_last_rebalanced_at = reference_time
        settings_row.economy_last_rebalanced_by = teacher_id

    return applied_labels, applied_changes


def apply_rebalance_changes(teacher_id, settings_row, change_plan, activation_mode, *, reference_time=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    applied_labels, applied_changes = _apply_change_list(
        teacher_id,
        settings_row,
        change_plan,
        activation_mode,
        reference_time=reference_time,
    )
    if applied_changes:
        _create_policy_transitions_for_changes(
            settings_row,
            applied_changes,
            activation_mode=activation_mode,
            created_by=teacher_id,
            status=POLICY_TRANSITION_STATUS_APPLIED,
            reference_time=reference_time,
            applied_at=reference_time,
        )
    return applied_labels


def activate_due_rebalances(teacher_id, *, class_id=None, reference_time=None, renewal_policy_id=None):
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    class_ids_subq = (
        db.session.query(ClassEconomy.class_id)
        .filter(ClassEconomy.user_id == teacher_id)
        .subquery()
    )
    pending_rows_query = FeatureSettings.query.filter(FeatureSettings.class_id.in_(sa.select(class_ids_subq)))
    if class_id:
        pending_rows_query = pending_rows_query.filter(FeatureSettings.class_id == class_id)

    activated = 0
    applied_labels = []

    for settings_row in pending_rows_query.all():
        pending_transitions = _get_pending_policy_transitions_for_class(settings_row.class_id)
        if pending_transitions:
            for transition in pending_transitions:
                target_version = db.session.get(PolicyVersion, transition.target_policy_version_id)
                if not target_version:
                    transition.status = POLICY_TRANSITION_STATUS_CANCELLED
                    transition.cancelled_at = reference_time
                    continue
                try:
                    change = json.loads(target_version.policy_payload_json or "{}")
                except (TypeError, ValueError, json.JSONDecodeError):
                    transition.status = POLICY_TRANSITION_STATUS_CANCELLED
                    transition.cancelled_at = reference_time
                    continue
                activation_mode = transition.activation_mode or REBALANCE_ACTIVATION_NEXT_PAYROLL
                activation_event = change.get("activation_event")
                activation_policy_id = change.get("activation_policy_id")
                effective_at = _parse_dt(change.get("effective_at"))
                is_due = False
                if activation_event == REBALANCE_TRIGGER_INSURANCE_RENEWAL:
                    is_due = renewal_policy_id is not None and str(activation_policy_id) == str(renewal_policy_id)
                elif activation_mode == REBALANCE_ACTIVATION_NEXT_PAYROLL and effective_at is None:
                    is_due = True
                elif effective_at is not None and effective_at <= reference_time:
                    is_due = True

                if not is_due:
                    continue

                applied_now, applied_changes = _apply_change_list(
                    teacher_id,
                    settings_row,
                    [change],
                    activation_mode,
                    reference_time=reference_time,
                )
                if applied_changes:
                    source_version = (
                        db.session.get(PolicyVersion, transition.source_policy_version_id)
                        if transition.source_policy_version_id
                        else None
                    )
                    if source_version:
                        source_version.is_active = False
                    target_version.is_active = True
                    target_version.activated_at = reference_time
                    transition.status = POLICY_TRANSITION_STATUS_APPLIED
                    transition.applied_at = reference_time
                    _supersede_pending_transitions(
                        settings_row.class_id,
                        transition.domain,
                        transition.id,
                        reference_time=reference_time,
                        conflict_key=_transition_conflict_key(transition.domain, change),
                    )
                    applied_labels.extend(applied_now)
                    activated += 1
                else:
                    transition.status = POLICY_TRANSITION_STATUS_CANCELLED
                    transition.cancelled_at = reference_time
                    transition.applied_at = reference_time

            continue

        # No pending policy transitions for this class; the JSON fallback has been retired.
        continue

    return activated, applied_labels


def queue_scheduled_policy_transitions(
    teacher_id: int,
    settings_row,
    scheduled_changes: list[dict[str, Any]],
    *,
    activation_mode: str = REBALANCE_ACTIVATION_NEXT_RENEWAL,
    reference_time: datetime | None = None,
) -> int:
    reference_time = ensure_utc(reference_time) if reference_time else utc_now()
    created = _create_policy_transitions_for_changes(
        settings_row,
        scheduled_changes,
        activation_mode=activation_mode,
        created_by=teacher_id,
        status=POLICY_TRANSITION_STATUS_PENDING,
        reference_time=reference_time,
    )
    return len(created)
