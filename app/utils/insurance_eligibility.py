"""Shared transaction-based insurance eligibility rules."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Optional, Set, Tuple

from sqlalchemy import and_

from app.models import InsuranceClaim, RedemptionEvent, RedemptionEventAction, RentItem, StoreItem, StorePurchase, Transaction, TransactionStatus
from app.utils.time import ensure_utc, get_class_now, to_class_time

CLAIM_TYPE_TRANSACTION_MONETARY = "transaction_monetary"
CLAIM_TYPE_NON_MONETARY = "non_monetary"

CLAIM_REASON_HARD_DENY_CATEGORY = "HARD_DENY_CATEGORY"
CLAIM_REASON_INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
CLAIM_REASON_DELAY_USE_NOT_USED = "DELAY_USE_NOT_USED"
CLAIM_REASON_DELAY_USE_EXPIRED = "DELAY_USE_EXPIRED"
CLAIM_REASON_NO_ACTIVE_POLICY = "NO_ACTIVE_POLICY"
CLAIM_REASON_PREMIUM_NOT_CURRENT = "PREMIUM_NOT_CURRENT"
CLAIM_REASON_WAITING_PERIOD = "WAITING_PERIOD"
CLAIM_REASON_TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
CLAIM_REASON_ALREADY_CLAIMED = "ALREADY_CLAIMED"
CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS = "REIMBURSEMENT_ALREADY_EXISTS"
CLAIM_REASON_UNCLASSIFIED_TRANSACTION = "UNCLASSIFIED_TRANSACTION"

_PURCHASE_NAME_RE = re.compile(r"^Purchase:\s*(.+?)(?:\s+\(x\d+\)|\s+\[|$)")
_TRANSFER_TYPES = {"withdrawal", "deposit"}
_HARD_DENY_TYPES = {"rent payment", "insurance_premium", "insurance_reimbursement"}


def _compute_waiting_end_class(
    *,
    purchase_utc: datetime,
    class_id: str,
    waiting_period_days: int,
) -> datetime:
    """
    Calendar-based waiting end in class-local time.

    Purchase day is excluded; waiting starts at next class-local midnight.
    """
    purchase_class = to_class_time(purchase_utc, class_id)
    tz = purchase_class.tzinfo
    next_day = purchase_class.date() + timedelta(days=1)
    waiting_start_class = datetime.combine(next_day, time.min).replace(tzinfo=tz)
    return waiting_start_class + timedelta(days=max(0, int(waiting_period_days or 0)))


def compute_coverage_start_utc_from_purchase(
    *,
    purchase_utc: datetime,
    class_id: str,
    waiting_period_days: int,
) -> datetime:
    """
    Convert class-local calendar waiting boundary into UTC for storage.
    """
    waiting_end_class = _compute_waiting_end_class(
        purchase_utc=ensure_utc(purchase_utc),
        class_id=class_id,
        waiting_period_days=waiting_period_days,
    )
    return ensure_utc(waiting_end_class)


def compute_waiting_end_class_for_enrollment(
    enrollment,
    *,
    fallback_purchase_utc: Optional[datetime] = None,
    fallback_class_id: Optional[str] = None,
) -> Optional[datetime]:
    """
    Canonical waiting-window boundary for an enrollment:
    00:00 next class-local day after purchase through 00:00 after day N.
    """
    class_id = (
        getattr(enrollment, "class_id", None)
        or fallback_class_id
        or getattr(getattr(enrollment, "policy", None), "class_id", None)
    )
    if not class_id:
        return None

    purchase_utc = ensure_utc(getattr(enrollment, "purchase_date", None) or fallback_purchase_utc)
    if purchase_utc is None:
        return None

    waiting_days = int(
        getattr(enrollment, "contract_waiting_period_days", None)
        or getattr(getattr(enrollment, "policy", None), "waiting_period_days", 0)
        or 0
    )
    return _compute_waiting_end_class(
        purchase_utc=purchase_utc,
        class_id=class_id,
        waiting_period_days=waiting_days,
    )


def _normalize_tx_type(tx_type: Optional[str]) -> str:
    return (tx_type or "").strip().lower()


def _is_internal_transfer(tx: Transaction) -> bool:
    tx_type = _normalize_tx_type(tx.type)
    if tx_type in _TRANSFER_TYPES:
        return True
    desc = (tx.description or "").lower()
    return "transfer to " in desc or "transfer from " in desc


def _is_hard_deny(tx: Transaction) -> bool:
    tx_type = _normalize_tx_type(tx.type)
    if tx_type in _HARD_DENY_TYPES:
        return True
    desc = (tx.description or "").lower()
    if "insurance premium" in desc:
        return True
    return False


def _extract_purchase_item_name(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = _PURCHASE_NAME_RE.match(description.strip())
    if not match:
        return None
    return match.group(1).strip() or None


def _check_delay_use_rule(tx: Transaction, *, class_id: str, now_class: datetime) -> Optional[str]:
    if _normalize_tx_type(tx.type) != "purchase":
        return None

    item_name = _extract_purchase_item_name(tx.description)
    if not item_name:
        # Preserve claimability for manual purchase descriptions.
        return None

    item_query = StoreItem.query.filter(
        StoreItem.name == item_name,
        StoreItem.class_id == class_id,
    )
    store_item = item_query.order_by(StoreItem.id.desc()).first()
    if not store_item:
        # Store item metadata may have changed; skip delay-use checks when unknown.
        return None
    if store_item.item_type != "delayed":
        return None

    tx_ts = ensure_utc(tx.timestamp)
    tolerance = timedelta(minutes=5)
    item_query = StorePurchase.query.filter(
        StorePurchase.seat_id == tx.seat_id,
        StorePurchase.store_item_id == store_item.id,
        and_(
            StorePurchase.purchased_at >= tx_ts - tolerance,
            StorePurchase.purchased_at <= tx_ts + tolerance,
        ),
    )
    item_row = item_query.order_by(StorePurchase.id.desc()).first()
    if not item_row:
        # Fallback for historical rows with slight timestamp drift.
        fallback_query = StorePurchase.query.filter(
            StorePurchase.seat_id == tx.seat_id,
            StorePurchase.store_item_id == store_item.id,
        )
        item_row = fallback_query.order_by(StorePurchase.purchased_at.desc()).first()
    if not item_row:
        # Legacy data may not have a matching canonical store row.
        return None

    redemption_event = RedemptionEvent.query.filter_by(
        purchase_id=item_row.id,
        action=RedemptionEventAction.APPROVED,
    ).first()
    used_at = ensure_utc(redemption_event.timestamp) if redemption_event else None
    if not used_at:
        return CLAIM_REASON_DELAY_USE_NOT_USED

    expiry_at = ensure_utc(item_row.expiry_date) if item_row.expiry_date else None
    if expiry_at and used_at > expiry_at:
        return CLAIM_REASON_DELAY_USE_EXPIRED
    if expiry_at and not used_at and now_class > to_class_time(expiry_at, class_id):
        return CLAIM_REASON_DELAY_USE_EXPIRED
    return None


def _is_rent_perk_or_privilege_purchase(tx: Transaction, *, class_id: str) -> bool:
    if _normalize_tx_type(tx.type) != "purchase":
        return False
    if tx.amount is not None and tx.amount == 0:
        return True
    desc = (tx.description or "").lower()
    if "rent perk" in desc:
        return True

    item_name = _extract_purchase_item_name(tx.description)
    if not item_name:
        return False
    item_query = StoreItem.query.filter(
        StoreItem.name == item_name,
        StoreItem.class_id == class_id,
    )
    store_item = item_query.order_by(StoreItem.id.desc()).first()
    if not store_item:
        return False

    rent_item = RentItem.query.filter(RentItem.store_item_id == store_item.id).first()
    return bool(rent_item and (rent_item.rent_item_type or "").lower() == "privilege")


def evaluate_claim_transaction_eligibility(
    tx: Transaction,
    *,
    enrollment,
    now_utc: datetime,
    claim_type: Optional[str] = None,
    claim_time_limit_days: Optional[int] = None,
    policy_id: Optional[int] = None,
    enrollment_join_code: Optional[str] = None,
    claimed_tx_ids: Optional[Set[int]] = None,
    reimbursed_tx_ids: Optional[Set[int]] = None,
) -> Tuple[bool, Optional[str]]:
    """Return (eligible, reason_code) for transaction-based claims."""
    if not tx or tx.id is None:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if claim_type != CLAIM_TYPE_TRANSACTION_MONETARY:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if not enrollment or enrollment.status != "active":
        return False, CLAIM_REASON_NO_ACTIVE_POLICY

    if tx.amount is None or tx.amount >= 0 or tx.is_void:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if tx.status != TransactionStatus.POSTED:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if _normalize_tx_type(tx.type) == "":
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if _is_hard_deny(tx):
        return False, CLAIM_REASON_HARD_DENY_CATEGORY

    if _is_internal_transfer(tx):
        return False, CLAIM_REASON_INTERNAL_TRANSFER

    if not enrollment.payment_current:
        return False, CLAIM_REASON_PREMIUM_NOT_CURRENT

    tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else None
    if tx_ts is None:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    class_id = getattr(enrollment, "class_id", None) or getattr(tx, "class_id", None)
    if not class_id:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if _is_rent_perk_or_privilege_purchase(tx, class_id=class_id):
        return False, CLAIM_REASON_HARD_DENY_CATEGORY

    now_class = get_class_now(class_id, reference_time_utc=now_utc)

    tx_ts_class = to_class_time(tx_ts, class_id)

    # Canonical waiting-period anchor is the enrollment coverage window.
    # Fallback to computed waiting boundary only when coverage_start_date is absent.
    waiting_end_class = compute_waiting_end_class_for_enrollment(
        enrollment,
        fallback_purchase_utc=tx_ts,
        fallback_class_id=class_id,
    )
    if waiting_end_class is not None and (now_class < waiting_end_class or tx_ts_class < waiting_end_class):
        return False, CLAIM_REASON_WAITING_PERIOD

    effective_time_limit = int(claim_time_limit_days) if claim_time_limit_days is not None else None
    if effective_time_limit is not None and effective_time_limit > 0:
        if (now_class.date() - tx_ts_class.date()).days > effective_time_limit:
            return False, CLAIM_REASON_TIME_LIMIT_EXCEEDED

    if enrollment_join_code and tx.join_code != enrollment_join_code:
        return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION

    if claimed_tx_ids is None:
        existing_claim = InsuranceClaim.query.filter(InsuranceClaim.transaction_id == tx.id).first()
        if existing_claim:
            return False, CLAIM_REASON_ALREADY_CLAIMED
    elif tx.id in claimed_tx_ids:
        return False, CLAIM_REASON_ALREADY_CLAIMED

    if reimbursed_tx_ids is None:
        if policy_id is None:
            return False, CLAIM_REASON_UNCLASSIFIED_TRANSACTION
        existing_reimbursement = Transaction.query.filter(
            Transaction.type == "insurance_reimbursement",
            Transaction.original_transaction_id == tx.id,
            Transaction.policy_id == policy_id,
            Transaction.is_void.is_(False),
        ).first()
        if existing_reimbursement:
            return False, CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS
    elif tx.id in reimbursed_tx_ids:
        return False, CLAIM_REASON_REIMBURSEMENT_ALREADY_EXISTS

    delay_reason = _check_delay_use_rule(tx, class_id=class_id, now_class=now_class)
    if delay_reason:
        return False, delay_reason

    return True, None


def collect_reimbursed_source_tx_ids(policy_id: int) -> Set[int]:
    rows = (
        Transaction.query.with_entities(Transaction.original_transaction_id)
        .filter(
            Transaction.type == "insurance_reimbursement",
            Transaction.policy_id == policy_id,
            Transaction.original_transaction_id.isnot(None),
            Transaction.is_void.is_(False),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def resolve_claim_type(*, claim=None, policy_claim_type: Optional[str] = None) -> str:
    """Canonical claim type resolution used across admin/student claim flows."""
    if policy_claim_type in {
        CLAIM_TYPE_TRANSACTION_MONETARY,
        CLAIM_TYPE_NON_MONETARY,
    }:
        return policy_claim_type
    if claim is None:
        return CLAIM_TYPE_TRANSACTION_MONETARY
    if getattr(claim, "transaction_id", None):
        return CLAIM_TYPE_TRANSACTION_MONETARY
    if getattr(claim, "claim_item", None):
        return CLAIM_TYPE_NON_MONETARY
    return CLAIM_TYPE_TRANSACTION_MONETARY
