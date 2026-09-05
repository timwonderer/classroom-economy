"""Ledger-owned monetary effect creation boundary."""

from app.extensions import db
from app.feats.base import audit_protected
from app.models import Seat, Transaction, TransactionStatus, _quantize_currency
from app.services.ledger_command_service import create_idempotent_transaction

_TRANSACTION_AUDIT_FIELDS = [
    "amount", "account_type", "type", "status", "class_id", "seat_id",
    "target_seat_id", "actor_seat_id", "mechanism", "description",
    "correlation_id",
]


def create_pending_transaction(
    *, seat_id: int, class_id: str, target_seat_id: int, actor_seat_id: int,
    mechanism: str, user_id: int | None = None, amount, account_type: str,
    type: str, description: str, original_transaction_id: int | None = None,
    policy_id: int | None = None, idempotency_key: str | None = None,
    command_reservation=None,
) -> Transaction:
    """Create one pending Ledger effect inside the caller-owned FEAT."""
    if idempotency_key and command_reservation is not None:
        raise ValueError("Provide either idempotency_key or command_reservation, not both.")
    if idempotency_key:
        transaction, _created = create_idempotent_transaction(
            idempotency_key=idempotency_key, seat_id=seat_id, class_id=class_id,
            target_seat_id=target_seat_id, actor_seat_id=actor_seat_id,
            mechanism=mechanism, user_id=user_id, amount=_quantize_currency(amount),
            account_type=account_type, type=type, description=description,
            original_transaction_id=original_transaction_id, policy_id=policy_id,
        )
        return transaction
    if not class_id or not seat_id or not target_seat_id or not actor_seat_id:
        raise ValueError(f"FATAL: Ledger mutation requires seat_id ({seat_id}) and class_id ({class_id}).")
    if account_type not in {"checking", "savings"}:
        raise ValueError("FATAL: Ledger mutation requires a checking or savings account_type.")
    scoped_seats = (
        db.session.query(Seat.id)
        .filter(Seat.id.in_({seat_id, target_seat_id, actor_seat_id}), Seat.class_id == class_id)
        .all()
    )
    if len(scoped_seats) != len({seat_id, target_seat_id, actor_seat_id}):
        raise ValueError("FATAL: Ledger mutation seats must all belong to the provided class_id.")
    if command_reservation is not None and command_reservation.class_id != class_id:
        raise ValueError("FATAL: Command reservation must belong to the provided class_id.")
    transaction = Transaction(
        seat_id=seat_id, target_seat_id=target_seat_id, actor_seat_id=actor_seat_id,
        class_id=class_id, user_id=user_id, amount=_quantize_currency(amount),
        account_type=account_type, status=TransactionStatus.PENDING,
        mechanism=mechanism, type=type, description=description,
        original_transaction_id=original_transaction_id, policy_id=policy_id,
    )
    db.session.add(transaction)
    if command_reservation is not None:
        transaction.command_reservation = command_reservation
    db.session.flush()
    audit_protected("ledger_transaction", transaction, "INSERT", _TRANSACTION_AUDIT_FIELDS)
    return transaction


def create_pending_transaction_idempotent(
    *, idempotency_key: str, seat_id: int, class_id: str, target_seat_id: int,
    actor_seat_id: int, mechanism: str, user_id: int | None = None, amount,
    account_type: str, type: str, description: str,
    original_transaction_id: int | None = None, policy_id: int | None = None,
):
    transaction, created = create_idempotent_transaction(
        idempotency_key=idempotency_key, seat_id=seat_id, class_id=class_id,
        target_seat_id=target_seat_id, actor_seat_id=actor_seat_id,
        mechanism=mechanism, user_id=user_id, amount=_quantize_currency(amount),
        account_type=account_type, type=type, description=description,
        original_transaction_id=original_transaction_id, policy_id=policy_id,
    )
    return transaction, created


__all__ = ["create_pending_transaction", "create_pending_transaction_idempotent"]
