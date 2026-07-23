from __future__ import annotations

import json
from datetime import datetime

from app.extensions import db
from app.models import PolicyTransition, PolicyVersion
from app.utils.time import ensure_utc, utc_now


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
    if source_version and is_active:
        source_version.is_active = False
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
