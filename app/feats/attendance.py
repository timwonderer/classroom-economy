from __future__ import annotations

from app.extensions import db
from app.models import HallPassSettings
from app.utils.time import ensure_utc, utc_now


def _get_or_create_hall_pass_settings(*, class_id: str):
    """Fetch class-scoped hall pass settings, creating defaults when absent."""
    settings = HallPassSettings.query.filter_by(class_id=class_id).first()
    if settings:
        return settings

    settings = HallPassSettings(
        class_id=class_id,
        queue_enabled=True,
        queue_limit=10,
        pass_types=HallPassSettings.get_default_pass_types(),
    )
    db.session.add(settings)
    db.session.flush()
    return settings


def update_hall_pass_queue_settings(
    *,
    user_id: int,
    class_id: str,
    queue_enabled=None,
    queue_limit=None,
    updated_at=None,
) -> HallPassSettings:
    """Update class-scoped queue settings for hall-pass management."""
    settings = _get_or_create_hall_pass_settings(class_id=class_id)
    if not settings:
        raise ValueError("Class context is required")

    if queue_enabled is not None:
        settings.queue_enabled = bool(queue_enabled)

    if queue_limit is not None:
        try:
            parsed_limit = int(queue_limit)
        except (TypeError, ValueError):
            raise ValueError("Queue limit must be between 1 and 50")
        if parsed_limit < 1 or parsed_limit > 50:
            raise ValueError("Queue limit must be between 1 and 50")
        settings.queue_limit = parsed_limit

    settings.updated_at = ensure_utc(updated_at or utc_now())
    db.session.flush()
    return settings


def save_hall_pass_setup_config(
    *,
    user_id: int,
    class_id: str,
    hall_pass_enabled: bool,
    pass_types: list[dict],
    updated_at=None,
) -> HallPassSettings:
    """Persist class-scoped hall-pass configuration payload."""
    settings = _get_or_create_hall_pass_settings(class_id=class_id)
    if not settings:
        raise ValueError("Class scope not found")

    settings.queue_enabled = hall_pass_enabled
    settings.pass_types = pass_types
    settings.updated_at = ensure_utc(updated_at or utc_now())
    db.session.flush()
    return settings


def rotate_teacher_hall_pass_verify_token(*, user_id: int) -> str:
    """Rotate and persist a teacher hall-pass verification token on canonical User."""
    from app.models import User
    teacher_user = db.session.get(User, user_id)
    if not teacher_user:
        raise LookupError("User not found.")

    teacher_user.hall_pass_verify_token = User.generate_verify_token()
    db.session.flush()
    return teacher_user.hall_pass_verify_token
