from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction


IDEMPOTENT_TRANSACTION_TYPES = frozenset({
    "insurance_reimbursement",
    "insurance_premium",
    "purchase",
    "refund",
    "overdraft_fee",
    "payroll",
    "Interest",
})

IDEMPOTENCY_KEY_PREFIX = "txn"
MAX_IDEMPOTENCY_KEY_LENGTH = 128


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

    feat_code = get_active_feat_name()

    existing = get_idempotent_transaction(
        idempotency_key,
        class_id=class_id,
        seat_id=target_seat_id,
        type=transaction_type,
        feat_code=feat_code,
    )
    if existing:
        return existing, False

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
        type=type,
        description=description,
        original_transaction_id=original_transaction_id,
        policy_id=policy_id,
    )
    try:
        db.session.add(new_txn)
        db.session.flush()
        # Emit audit event after successful creation (id is now populated)
        audit_protected("ledger_transaction", new_txn, "INSERT", _TRANSACTION_AUDIT_FIELDS)
        return new_txn, True
    except IntegrityError:
        db.session.rollback()
        with db.session.begin_nested():
            existing = get_idempotent_transaction(
                idempotency_key,
                class_id=class_id,
                seat_id=target_seat_id,
                type=transaction_type,
                feat_code=feat_code,
            )
        if existing:
            return existing, False
        raise
