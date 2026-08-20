from __future__ import annotations

from app.extensions import db
from app.models import HallPassSettings
from app.feats.base import requires_feat_context
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now


def _get_or_create_hall_pass_settings(*, class_id: str):
    """Fetch the effective immutable hall-pass policy for a class."""
    settings = HallPassSettings.query.filter_by(class_id=class_id).order_by(HallPassSettings.effective_date.desc()).first()
    if settings:
        return settings

    settings = HallPassSettings(
        class_id=class_id,
        max_queue_limit=10,
        pass_type_payload=HallPassSettings.get_default_pass_types(),
    )
    db.session.add(settings)
    db.session.flush()
    return settings


@requires_feat_context("FEAT-SETTINGS-001")
def update_hall_pass_queue_settings(
    *,
    user_id: int,
    class_id: str,
    max_queue_limit: int | None = None,
    updated_at=None,
    correlation_id: str,
    idempotency_key: str,
) -> HallPassSettings:
    """Update class-scoped queue settings for hall-pass management."""
    if max_queue_limit is not None:
        try:
            parsed_limit = int(max_queue_limit)
        except (TypeError, ValueError):
            raise ValueError("Queue limit must be between 1 and 50")
        if parsed_limit < 1 or parsed_limit > 50:
            raise ValueError("Queue limit must be between 1 and 50")
    current = _get_or_create_hall_pass_settings(class_id=class_id)
    return save_hall_pass_setup_config(
        user_id=user_id,
        class_id=class_id,
        hall_pass_enabled=True,
        pass_type_payload=current.get_pass_types(),
        max_queue_limit=parsed_limit if max_queue_limit is not None else current.max_queue_limit,
        updated_at=updated_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-SETTINGS-001")
def save_hall_pass_setup_config(
    *,
    user_id: int,
    class_id: str,
    hall_pass_enabled: bool,
    pass_type_payload: list[dict],
    max_queue_limit: int = 10,
    updated_at=None,
    correlation_id: str,
    idempotency_key: str,
) -> HallPassSettings:
    """Persist class-scoped hall-pass configuration payload."""
    if not isinstance(pass_type_payload, list) or any(set(item) != {"pass_name", "max_queue", "consume_pass"} for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if any(not isinstance(item["pass_name"], str) or not isinstance(item["max_queue"], int) or item["max_queue"] < 0 or not isinstance(item["consume_pass"], bool) for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if not isinstance(max_queue_limit, int) or max_queue_limit < 0:
        raise ValueError("Invalid max queue limit")
    settings = HallPassSettings(class_id=class_id, max_queue_limit=max_queue_limit, pass_type_payload=pass_type_payload, effective_date=ensure_utc(updated_at or utc_now()))
    db.session.add(settings)
    db.session.flush()
    return settings


@requires_feat_context("FEAT-SETTINGS-001")
def rotate_teacher_hall_pass_verify_token(*, user_id: int, correlation_id: str, idempotency_key: str) -> str:
    """Rotate and persist a teacher hall-pass verification token on canonical User."""
    from app.models import User
    teacher_user = db.session.get(User, user_id)
    if not teacher_user:
        raise LookupError("User not found.")

    teacher_user.hall_pass_verify_token = User.generate_verify_token()
    db.session.flush()
    return teacher_user.hall_pass_verify_token
