"""Ledger-owned internal transfer service surface.

Transfer FEATs depend on this module rather than importing the mixed Ledger
service directly. The implementation remains Ledger-owned; this module is the
canonical service boundary for transfer creation and proof.
"""

from app.services.ledger_balance_query_service import TransferProofResult, verify_transfer
from app.services.ledger_command_service import FINGERPRINT_VERSION, _command_fingerprint
from app.services.ledger_posting_service import create_pending_transaction
from app.extensions import db
from app.models import LedgerCommandReservation, Transaction
from app.models import _quantize_currency


def create_transfer_pair(
    *, seat_id: int, class_id: str, user_id: int | None = None, amount,
    from_account: str, to_account: str, withdraw_description: str,
    deposit_description: str, idempotency_key: str | None = None,
) -> tuple[Transaction, Transaction]:
    """Create one reservation owning exactly two pending transfer effects."""
    from app.feats.base import get_active_feat_name, get_idempotency_key

    if not class_id or not seat_id:
        raise ValueError("FATAL: Internal transfer requires explicit class_id and seat_id.")
    if from_account not in {"checking", "savings"} or to_account not in {"checking", "savings"}:
        raise ValueError("Internal transfers require checking/savings account types.")
    if from_account == to_account:
        raise ValueError("Internal transfers require distinct source and destination accounts.")
    idempotency_key = idempotency_key or get_idempotency_key()
    feat_code = get_active_feat_name()
    if not idempotency_key or not feat_code:
        raise ValueError("Internal transfers require a command idempotency reservation.")
    quantized_amount = _quantize_currency(amount)
    if quantized_amount <= 0:
        raise ValueError("Internal transfer amount must be greater than zero.")
    fingerprint = _command_fingerprint(
        target_seat_id=seat_id, actor_seat_id=seat_id, amount=quantized_amount,
        account_type=f"{from_account}->{to_account}", type="internal_transfer",
        original_transaction_id=None, policy_id=None,
    )
    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation:
        if reservation.fingerprint_version != FINGERPRINT_VERSION or reservation.replay_fingerprint != fingerprint:
            raise ValueError("Replay fingerprint mismatch for existing transfer reservation.")
        effects = Transaction.query.filter_by(command_reservation_id=reservation.id).order_by(Transaction.id.asc()).all()
        if len(effects) != 2:
            raise RuntimeError("Transfer reservation does not have exactly two effects.")
        return effects[0], effects[1]
    reservation = LedgerCommandReservation(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key,
        replay_fingerprint=fingerprint, fingerprint_version=FINGERPRINT_VERSION,
    )
    db.session.add(reservation)
    db.session.flush()
    withdraw_tx = create_pending_transaction(
        seat_id=seat_id, class_id=class_id, target_seat_id=seat_id,
        actor_seat_id=seat_id, mechanism="self", user_id=user_id,
        amount=-quantized_amount, account_type=from_account, type="Withdrawal",
        description=withdraw_description, command_reservation=reservation,
    )
    deposit_tx = create_pending_transaction(
        seat_id=seat_id, class_id=class_id, target_seat_id=seat_id,
        actor_seat_id=seat_id, mechanism="self", user_id=user_id,
        amount=quantized_amount, account_type=to_account, type="Deposit",
        description=deposit_description, command_reservation=reservation,
    )
    db.session.flush()
    return withdraw_tx, deposit_tx

__all__ = ["TransferProofResult", "create_transfer_pair", "verify_transfer"]
