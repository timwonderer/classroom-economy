from __future__ import annotations

import json
from datetime import datetime

from app.extensions import db
from app.models import PolicyTransition, PolicyVersion
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now


INSURANCE_DOMAIN = "insurance"


def _load_payload(version: PolicyVersion) -> dict:
    try:
        return json.loads(version.policy_payload_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def get_insurance_entitlement_item_id(version: PolicyVersion) -> int | None:
    payload = _load_payload(version)
    raw_item_id = payload.get("entitlement_item_id")
    try:
        return int(raw_item_id) if raw_item_id is not None and raw_item_id != "" else None
    except (TypeError, ValueError):
        return None


def list_insurance_policy_versions(class_id: str) -> list[PolicyVersion]:
    return (
        PolicyVersion.query.filter_by(class_id=class_id, domain=INSURANCE_DOMAIN)
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .all()
    )


def get_insurance_policy_version(version_id: int, *, class_id: str) -> PolicyVersion | None:
    return PolicyVersion.query.filter_by(id=version_id, class_id=class_id, domain=INSURANCE_DOMAIN).first()


def _next_version_number(class_id: str) -> int:
    current_max = (
        db.session.query(db.func.max(PolicyVersion.version_number))
        .filter(PolicyVersion.class_id == class_id, PolicyVersion.domain == INSURANCE_DOMAIN)
        .scalar()
    )
    return int(current_max or 0) + 1


def create_policy_version(
    *,
    class_id: str,
    actor_user_id: int | None,
    payload: dict,
    source_version: PolicyVersion | None = None,
    is_active: bool = True,
    activation_mode: str = "manual",
    status: str = "applied",
    correlation_id: str | None = None,
) -> PolicyVersion:
    now = utc_now()
    version = PolicyVersion(
        class_id=class_id,
        domain=INSURANCE_DOMAIN,
        version_number=_next_version_number(class_id),
        policy_payload_json=json.dumps(payload, sort_keys=True, default=str),
        created_at=now,
        activated_at=now if is_active else None,
        is_active=is_active,
    )
    db.session.add(version)
    db.session.flush()

    transition = PolicyTransition(
        class_id=class_id,
        domain=INSURANCE_DOMAIN,
        source_policy_version_id=source_version.id if source_version else None,
        target_policy_version_id=version.id,
        activation_mode=activation_mode,
        status=status,
        created_at=now,
        created_by=actor_user_id,
        applied_at=now if status == "applied" else None,
        correlation_id=correlation_id,
    )
    db.session.add(transition)
    db.session.flush()
    version.created_by_transition_id = transition.id
    return version


def schedule_policy_deletion(
    *,
    class_id: str,
    actor_user_id: int | None,
    source_version: PolicyVersion,
    deletion_at: datetime,
) -> PolicyVersion:
    payload = _load_payload(source_version)
    payload["deletion_pending"] = True
    payload["deletion_at"] = ensure_utc(deletion_at).isoformat()
    payload["is_active"] = False
    return create_policy_version(
        class_id=class_id,
        actor_user_id=actor_user_id,
        payload=payload,
        source_version=source_version,
        is_active=False,
        activation_mode="delete",
        status="pending",
        correlation_id=f"policy-delete:{class_id}:{source_version.id}",
    )


def _iter_policy_lineage_version_ids(start_version_id: int) -> list[int]:
    """Return every policy-version id in the connected insurance lineage."""
    lineage_ids: list[int] = []
    seen: set[int] = set()
    stack = [start_version_id]

    while stack:
        version_id = stack.pop()
        if version_id in seen:
            continue
        seen.add(version_id)
        lineage_ids.append(version_id)

        outgoing = (
            db.session.query(PolicyTransition.source_policy_version_id, PolicyTransition.target_policy_version_id)
            .filter(
                PolicyTransition.domain == INSURANCE_DOMAIN,
                PolicyTransition.source_policy_version_id == version_id,
            )
            .all()
        )
        incoming = (
            db.session.query(PolicyTransition.source_policy_version_id, PolicyTransition.target_policy_version_id)
            .filter(
                PolicyTransition.domain == INSURANCE_DOMAIN,
                PolicyTransition.target_policy_version_id == version_id,
            )
            .all()
        )
        for source_id, target_id in outgoing:
            if target_id not in seen:
                stack.append(target_id)
        for source_id, target_id in incoming:
            if source_id and source_id not in seen:
                stack.append(source_id)

    return lineage_ids


def delete_policy_lineage(*, class_id: str, version_id: int) -> None:
    """Hard-delete all insurance policy lineage rows for one class lineage."""
    lineage_ids = _iter_policy_lineage_version_ids(version_id)
    if not lineage_ids:
        return

    db.session.query(PolicyTransition).filter(
        PolicyTransition.class_id == class_id,
        PolicyTransition.domain == INSURANCE_DOMAIN,
        (
            PolicyTransition.source_policy_version_id.in_(lineage_ids)
            | PolicyTransition.target_policy_version_id.in_(lineage_ids)
        ),
    ).delete(synchronize_session=False)
    db.session.query(PolicyVersion).filter(
        PolicyVersion.class_id == class_id,
        PolicyVersion.domain == INSURANCE_DOMAIN,
        PolicyVersion.id.in_(lineage_ids),
    ).delete(synchronize_session=False)
    db.session.flush()


def delete_due_policy_lineages(*, execution_time=None) -> list[int]:
    """Delete any scheduled insurance policy lineage whose boundary has arrived."""
    now = ensure_utc(execution_time or utc_now())
    due_versions = (
        PolicyVersion.query.filter_by(domain=INSURANCE_DOMAIN)
        .order_by(PolicyVersion.class_id.asc(), PolicyVersion.version_number.asc(), PolicyVersion.id.asc())
        .all()
    )
    deleted_ids: list[int] = []
    for version in due_versions:
        payload = _load_payload(version)
        if not payload.get("deletion_pending"):
            continue
        deletion_at = payload.get("deletion_at")
        if not deletion_at:
            continue
        try:
            deletion_boundary = datetime.fromisoformat(deletion_at)
            if ensure_utc(deletion_boundary) > now:
                continue
        except (TypeError, ValueError):
            continue
        delete_policy_lineage(class_id=version.class_id, version_id=version.id)
        deleted_ids.append(version.id)

    return deleted_ids
