"""Ledger-owned command reservation and replay service boundary.

The persistence helper remains isolated in ``transaction_idempotency`` while
callers migrate to this domain-owned service surface.
"""

import hashlib
import json

from app.extensions import db
from app.models import LedgerCommandReservation, Transaction
from sqlalchemy.exc import IntegrityError
from app.utils.transaction_idempotency import (
    FINGERPRINT_VERSION,
    _command_fingerprint,
    create_idempotent_transaction,
)


def create_reserved_effects(*, class_id: str, feat_code: str, idempotency_key: str,
                            effects: list[dict]) -> tuple[list[Transaction], bool]:
    """Create or replay one reservation owning multiple Ledger effects."""
    if not class_id or not feat_code or not idempotency_key or not effects:
        raise ValueError("A reserved command requires class, FEAT, key, and effects.")
    fingerprint_fields = [
        {key: effect.get(key) for key in (
            "seat_id", "target_seat_id", "actor_seat_id", "mechanism", "user_id",
            "amount", "account_type", "type", "original_transaction_id", "policy_id",
        )}
        for effect in effects
    ]
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_fields, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation:
        if reservation.fingerprint_version != FINGERPRINT_VERSION or reservation.replay_fingerprint != fingerprint:
            raise ValueError("Replay fingerprint mismatch for existing Ledger command reservation.")
        effects = (Transaction.query.filter_by(command_reservation_id=reservation.id)
                   .order_by(Transaction.id.asc()).all())
        if not effects:
            raise RuntimeError("Ledger command reservation has no committed effects.")
        return effects, False
    reservation = LedgerCommandReservation(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key,
        replay_fingerprint=fingerprint, fingerprint_version=FINGERPRINT_VERSION,
    )
    try:
        with db.session.begin_nested():
            db.session.add(reservation)
            db.session.flush()
    except IntegrityError:
        reservation = LedgerCommandReservation.query.filter_by(
            class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
        ).one()
        if reservation.fingerprint_version != FINGERPRINT_VERSION or reservation.replay_fingerprint != fingerprint:
            raise ValueError("Replay fingerprint mismatch for existing Ledger command reservation.")
        effects = (Transaction.query.filter_by(command_reservation_id=reservation.id)
                   .order_by(Transaction.id.asc()).all())
        if not effects:
            raise RuntimeError("Ledger command reservation has no committed effects.")
        return effects, False
    from app.services.ledger_posting_service import create_pending_transaction
    created = [create_pending_transaction(command_reservation=reservation, **effect) for effect in effects]
    return created, True

__all__ = ["FINGERPRINT_VERSION", "_command_fingerprint", "create_idempotent_transaction", "create_reserved_effects"]
