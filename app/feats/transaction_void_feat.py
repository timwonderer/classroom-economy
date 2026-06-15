from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import InsurancePolicy, RentPayment, StoreItem, StudentInsurance, StudentItem, Transaction, TransactionStatus
from app.services import ledger_service
from app.utils.seat_scope import get_seat_ids_for_student_join, seat_scoped_filter
from app.utils.time import ensure_utc, utc_now
from app.utils.transaction_idempotency import void_refund_key


@dataclass
class VoidTransactionResult:
    transaction_id: int
    reversal_transaction_id: int | None


class ImmediatePurchaseNotVoidable(ValueError):
    pass


class UsedDelayedPurchaseNotVoidable(ValueError):
    pass


def execute_void_transaction(tx: Transaction) -> VoidTransactionResult:
    """Ledger-led FEAT for transaction void orchestration."""
    is_pending = tx.status == TransactionStatus.PENDING

    if tx.type == 'purchase':
        _void_purchase(tx)
    elif tx.type == 'Rent Payment':
        _void_rent_payment(tx)
    elif tx.type == 'insurance_premium':
        _void_insurance_premium(tx)

    reversal_tx = None
    if tx.type == 'purchase':
        reversal_tx = ledger_service.compensate_posted_transaction(
            tx,
            idempotency_key=void_refund_key(tx.id),
            description=f"Void refund for transaction #{tx.id}: {tx.description}",
        )
        if is_pending:
            ledger_service.void_pending_transaction(tx)
    elif is_pending:
        ledger_service.void_pending_transaction(tx)
    else:
        reversal_tx = ledger_service.compensate_posted_transaction(
            tx,
            idempotency_key=void_refund_key(tx.id),
            description=f"Void refund for transaction #{tx.id}: {tx.description}",
        )

    return VoidTransactionResult(
        transaction_id=tx.id,
        reversal_transaction_id=reversal_tx.id if reversal_tx else tx.reversal_transaction_id,
    )


def _void_purchase(tx: Transaction) -> None:
    purchase_match = re.match(
        r'^Purchase:\s*(?P<name>.+?)(?:\s+\(x(?P<qty>\d+)\))?(?:\s+\[.*\])?$',
        (tx.description or '').strip()
    )
    if not purchase_match:
        raise ValueError("This purchase transaction cannot be voided automatically.")

    item_name = (purchase_match.group('name') or '').strip()
    quantity = int(purchase_match.group('qty') or 1)
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")
    store_item = StoreItem.query.filter_by(class_id=tx.class_id, name=item_name).first()
    if not store_item:
        raise ValueError("Purchase item record was not found. This transaction cannot be voided.")
    if store_item.item_type == 'immediate':
        raise ImmediatePurchaseNotVoidable
    if store_item.item_type != 'delayed':
        raise ValueError("Only delayed-use item purchases are voidable.")
    matching_items = StudentItem.query.filter(
        StudentItem.seat_id == tx.seat_id,
        StudentItem.store_item_id == store_item.id,
        StudentItem.class_id == tx.class_id,
    ).all()
    if not matching_items:
        raise ValueError("No matching student item was found for this purchase.")

    tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()

    def _distance(student_item):
        if not student_item.purchase_date:
            return float('inf')
        return abs((ensure_utc(student_item.purchase_date) - tx_ts).total_seconds())

    matching_items.sort(key=lambda si: (_distance(si), -si.id))
    selected_items = []
    selected_units = 0
    for student_item in matching_items:
        selected_items.append(student_item)
        selected_units += (student_item.quantity_purchased or 1)
        if selected_units >= quantity:
            break
    if selected_units < quantity:
        raise ValueError("Unable to map this transaction to purchasable student items.")

    used_statuses = {'processing', 'completed', 'redeemed'}
    if any((student_item.status or '').lower() in used_statuses for student_item in selected_items):
        raise UsedDelayedPurchaseNotVoidable

    ledger_service.create_pending_transaction(
        seat_id=tx.seat_id,
        class_id=tx.class_id,
        teacher_id=tx.teacher_id,
        amount=Decimal('0.00'),
        account_type=tx.account_type or 'checking',
        type='void_item_removed',
        description=f"item removed - {store_item.name}",
    )
    for student_item in selected_items:
        student_item.status = 'voided'
        if not student_item.redemption_date:
            student_item.redemption_date = utc_now()


def _void_rent_payment(tx: Transaction) -> None:
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")
    
    rent_payments = RentPayment.query.filter(
        RentPayment.seat_id == tx.seat_id,
        RentPayment.class_id == tx.class_id,
        RentPayment.amount_paid == abs(tx.amount or Decimal('0.00')),
    ).all()
    
    if rent_payments:
        tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()
        matched_rent_payment = min(
            rent_payments,
            key=lambda p: abs((ensure_utc(p.payment_date or tx.timestamp or utc_now()) - tx_ts).total_seconds())
        )
        db.session.delete(matched_rent_payment)


def _void_insurance_premium(tx: Transaction) -> None:
    policy_title = None
    if tx.description and tx.description.startswith("Insurance premium: "):
        policy_title = tx.description.replace("Insurance premium: ", "", 1).strip()
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")

    enrollments_query = (
        StudentInsurance.query
        .join(InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id)
        .filter(
            StudentInsurance.seat_id == tx.seat_id,
            StudentInsurance.class_id == tx.class_id,
        )
    )
    if policy_title:
        enrollments_query = enrollments_query.filter(InsurancePolicy.title == policy_title)
    enrollments = enrollments_query.all()
    if enrollments:
        tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()
        matched_enrollment = min(
            enrollments,
            key=lambda e: abs((ensure_utc(e.purchase_date or tx.timestamp or utc_now()) - tx_ts).total_seconds())
        )
        matched_enrollment.payment_current = False
        matched_enrollment.days_unpaid = max(1, matched_enrollment.days_unpaid or 0)
