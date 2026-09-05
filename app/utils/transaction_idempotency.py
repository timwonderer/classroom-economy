import hashlib
import json

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LedgerCommandReservation, Seat, Transaction, TransactionStatus


IDEMPOTENT_TRANSACTION_TYPES = frozenset({
    "insurance_reimbursement",
    "insurance_premium",
    "purchase",
    "refund",
    "overdraft_fee",
    "payroll",
    "manual_payment",
    "bug_reward",
    "issue_reversal",
    "issue_compensation",
    "rent_payment",
    "Interest",
    "void_item_removed",
})

IDEMPOTENCY_KEY_PREFIX = "txn"
MAX_IDEMPOTENCY_KEY_LENGTH = 128
FINGERPRINT_VERSION = 1


def _normalize_key_part(value):
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def build_transaction_idempotency_key(*parts):
    normalized_parts = [
        _normalize_key_part(part)
        for part in parts
        if part is not None and str(part).strip() != ""
    ]
    return ":".join([IDEMPOTENCY_KEY_PREFIX, *normalized_parts])


def insurance_reimbursement_key(claim_id):
    return build_transaction_idempotency_key("insurance", "claim", claim_id, "reimbursement")


def store_purchase_refund_key(purchase_id, reason):
    return build_transaction_idempotency_key("refund", "store-purchase", purchase_id, reason)


def purchase_transaction_key(student_id, class_id, item_id, client_idempotency_token):
    return build_transaction_idempotency_key(
        "purchase",
        "student",
        student_id,
        "class",
        class_id,
        "item",
        item_id,
        client_idempotency_token,
    )


def void_refund_key(transaction_id):
    return build_transaction_idempotency_key("void", "transaction", transaction_id, "refund")


def get_idempotent_transaction(idempotency_key, class_id=None, seat_id=None, type=None, feat_code=None):
    if not idempotency_key:
        return None

    query = Transaction.query.filter(Transaction.idempotency_key == idempotency_key)
    if class_id:
        query = query.filter(Transaction.class_id == class_id)
        
    if seat_id:
        query = query.filter(Transaction.seat_id == seat_id)
    if type:
        query = query.filter(Transaction.type == type)
    if feat_code:
        query = query.filter(Transaction.feat_code == feat_code)
        
    return query.first()


def _command_fingerprint(*, target_seat_id, actor_seat_id, amount, account_type, type, original_transaction_id, policy_id):
    representation = {
        "account_type": account_type,
        "actor_seat_id": actor_seat_id,
        "amount": str(amount),
        "original_transaction_id": original_transaction_id,
        "policy_id": policy_id,
        "target_seat_id": target_seat_id,
        "type": type,
    }
    encoded = json.dumps(representation, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_TRANSACTION_AUDIT_FIELDS = [
    "amount", "account_type", "type", "status",
    "class_id", "seat_id", "target_seat_id", "actor_seat_id",
    "mechanism", "description", "correlation_id",
]


def create_idempotent_transaction(
    *,
    idempotency_key,
    seat_id,
    class_id,
    target_seat_id,
    actor_seat_id,
    mechanism,
    user_id=None,
    amount,
    account_type,
    type,
    description,
    original_transaction_id=None,
    policy_id=None,
):
    from app.feats.base import get_active_feat_name, audit_protected

    transaction_type = type
    if transaction_type not in IDEMPOTENT_TRANSACTION_TYPES:
        raise ValueError(f"Transaction type '{transaction_type}' is not enabled for idempotent creation.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("Idempotency key must be a non-empty string.")
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(
            f"Idempotency key exceeds max length of {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )
    if not class_id or not seat_id or not target_seat_id or not actor_seat_id:
        raise ValueError("FATAL: Idempotent Ledger mutation requires explicit class and seat scope.")
    if account_type not in {"checking", "savings"}:
        raise ValueError("FATAL: Idempotent Ledger mutation requires a checking or savings account_type.")
    scoped_seats = (
        db.session.query(Seat.id)
        .filter(Seat.id.in_({seat_id, target_seat_id, actor_seat_id}), Seat.class_id == class_id)
        .all()
    )
    if len(scoped_seats) != len({seat_id, target_seat_id, actor_seat_id}):
        raise ValueError("FATAL: Idempotent Ledger mutation seats must all belong to the provided class_id.")

    feat_code = get_active_feat_name()
    fingerprint = _command_fingerprint(
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        amount=amount,
        account_type=account_type,
        type=transaction_type,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )

    reservation = LedgerCommandReservation.query.filter_by(
        class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
    ).first()
    if reservation:
        if reservation.fingerprint_version != FINGERPRINT_VERSION or reservation.replay_fingerprint != fingerprint:
            raise ValueError("Replay fingerprint mismatch for existing Ledger command reservation.")
        existing = Transaction.query.filter_by(command_reservation_id=reservation.id).order_by(Transaction.id.asc()).first()
        if existing:
            return existing, False
        raise RuntimeError("Ledger command reservation exists without an associated effect.")

    reservation = LedgerCommandReservation(
        class_id=class_id,
        feat_code=feat_code,
        idempotency_key=idempotency_key,
        replay_fingerprint=fingerprint,
        fingerprint_version=FINGERPRINT_VERSION,
    )
    new_txn = Transaction(
        idempotency_key=idempotency_key,
        feat_code=feat_code,
        seat_id=seat_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        mechanism=mechanism,
        class_id=class_id,
        user_id=user_id,
        amount=amount,
        account_type=account_type,
        status=TransactionStatus.PENDING,
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
        command_reservation=reservation,
    )
    try:
        db.session.add(reservation)
        db.session.add(new_txn)
        db.session.flush()
        # Emit audit event after successful creation (id is now populated)
        audit_protected("ledger_transaction", new_txn, "INSERT", _TRANSACTION_AUDIT_FIELDS)
        return new_txn, True
    except IntegrityError:
        db.session.rollback()
        with db.session.begin_nested():
            existing_reservation = LedgerCommandReservation.query.filter_by(
                class_id=class_id, feat_code=feat_code, idempotency_key=idempotency_key
            ).first()
        if existing_reservation:
            if existing_reservation.replay_fingerprint != fingerprint:
                raise ValueError("Replay fingerprint mismatch for existing Ledger command reservation.")
            existing = Transaction.query.filter_by(command_reservation_id=existing_reservation.id).order_by(Transaction.id.asc()).first()
            if existing:
                return existing, False
        raise
