"""Ledger-owned append-only correction boundary."""

from decimal import Decimal

from app.extensions import db
from app.services.ledger_command_service import create_idempotent_transaction
from app.utils.canonical_temporal_resolver import utc_now
from app.models import _quantize_currency


def void_pending_transaction(transaction, *, voided_at=None) -> None:
    transaction.is_void = True
    transaction.status = "VOID"
    transaction.voided_at = voided_at or utc_now()


def compensate_posted_transaction(
    transaction, *, description: str, compensation_type: str = "refund",
    idempotency_key: str | None = None,
):
    """Create an append-only compensating effect and link it to the original."""
    if not idempotency_key:
        raise ValueError("Ledger corrections require a command idempotency reservation.")
    compensation_amount = _quantize_currency(-(transaction.amount or Decimal("0.00")))
    kwargs = dict(
        seat_id=transaction.seat_id, class_id=transaction.class_id,
        target_seat_id=transaction.target_seat_id,
        actor_seat_id=transaction.actor_seat_id, mechanism=transaction.mechanism,
        user_id=transaction.user_id, amount=compensation_amount,
        account_type=transaction.account_type or "checking", type=compensation_type,
        description=description, original_transaction_id=transaction.id,
        policy_id=transaction.policy_id,
    )
    reversal_tx, _created = create_idempotent_transaction(
        idempotency_key=idempotency_key, **kwargs
    )
    db.session.flush()
    transaction.reversal_transaction_id = reversal_tx.id
    transaction.is_void = True
    db.session.flush()
    return reversal_tx


__all__ = ["compensate_posted_transaction", "void_pending_transaction"]
