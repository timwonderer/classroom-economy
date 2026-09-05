from __future__ import annotations

from app.extensions import db
from app.models import HallPassSettings
from app.feats.base import requires_feat_context
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now


def _current_hall_pass_settings(class_id: str) -> HallPassSettings | None:
    """The hall-pass policy currently in force for a class, or None.

    A pure read. The previous ``_get_or_create`` variant inserted a default row
    as a side effect of being asked a question, which both wrote from a read
    path and minted an unretired policy nobody submitted. Callers that need a
    starting point when no policy exists use the class defaults instead.

    Deterministic by construction: ``effective_date`` collides for rows written
    in the same request, so ``id`` supplies the total order.
    """
    return (
        HallPassSettings.query
        .filter_by(class_id=class_id, availability_state='IN_USE')
        .order_by(HallPassSettings.effective_date.desc(), HallPassSettings.id.desc())
        .first()
    )


def update_hall_pass_queue_settings(
    *,
    user_id: int,
    class_id: str,
    max_queue_limit: int | None = None,
    updated_at=None,
    correlation_id: str,
    idempotency_key: str,
) -> HallPassSettings:
    """Update class-scoped queue settings for hall-pass management.

    Deliberately *not* decorated with ``@requires_feat_context``. This is a
    thin argument-preparer over ``save_hall_pass_setup_config``, which owns the
    FEAT context. Because ``requires_feat_context`` opens a context
    unconditionally, decorating both meant a FEAT composed a FEAT and every
    call raised ``FEATContextError`` (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2) —
    which made the queue-limit API endpoint an unconditional 500.
    """
    if max_queue_limit is not None:
        try:
            parsed_limit = int(max_queue_limit)
        except (TypeError, ValueError):
            raise ValueError("Queue limit must be between 1 and 50")
        if parsed_limit < 1 or parsed_limit > 50:
            raise ValueError("Queue limit must be between 1 and 50")
    current = _current_hall_pass_settings(class_id)
    current_pass_types = (
        current.get_pass_types() if current is not None
        else HallPassSettings.get_default_pass_types()
    )
    current_queue_limit = current.max_queue_limit if current is not None else 10
    return save_hall_pass_setup_config(
        user_id=user_id,
        class_id=class_id,
        hall_pass_enabled=True,
        pass_type_payload=current_pass_types,
        max_queue_limit=parsed_limit if max_queue_limit is not None else current_queue_limit,
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
    """Record a hall-pass configuration submission as a NEW immutable row.

    DOM-POL-001 §VI.1: a submission is a new contract, never an edit. This
    already inserted a new row per save; what was missing is retiring the
    predecessor, without which the class accumulated several rows all claiming
    to be current and the reader picked one by sort order.
    """
    if not isinstance(pass_type_payload, list) or any(set(item) != {"pass_name", "max_queue", "consume_pass"} for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if any(not isinstance(item["pass_name"], str) or not isinstance(item["max_queue"], int) or item["max_queue"] < 0 or not isinstance(item["consume_pass"], bool) for item in pass_type_payload):
        raise ValueError("Invalid hall-pass payload")
    if not isinstance(max_queue_limit, int) or max_queue_limit < 0:
        raise ValueError("Invalid max queue limit")
    # Retire the predecessor BEFORE the insert is flushed so the partial unique
    # index never observes two IN_USE rows for the class.
    predecessor = _current_hall_pass_settings(class_id)
    if predecessor is not None:
        predecessor.availability_state = 'RETIRED'
        db.session.flush()

    settings = HallPassSettings(
        class_id=class_id,
        availability_state='IN_USE',
        max_queue_limit=max_queue_limit,
        pass_type_payload=pass_type_payload,
        effective_date=ensure_utc(updated_at or utc_now()),
    )
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
