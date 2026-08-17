from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import EntitlementEvent, StoreItem, Transaction, TransactionStatus
from app.services import ledger_service, obligations_service
# TODO (Phase 4): store_entitlement_service deleted; must query EntitlementEvent directly
# from app.services.store_entitlement_service import list_entitlement_history
from app.utils.seat_scope import seat_scoped_filter
from app.utils.canonical_temporal_resolver import ensure_utc, utc_now
from app.utils.transaction_idempotency import void_refund_key


@dataclass
class VoidTransactionResult:
    transaction_id: int
    reversal_transaction_id: int | None


class ImmediatePurchaseNotVoidable(ValueError):
    pass


class UsedDelayedPurchaseNotVoidable(ValueError):
    pass


from app.feats.base import requires_feat_context

@requires_feat_context("FEAT-LED-002")
def execute_void_transaction(tx: Transaction, correlation_id: str | None = None, idempotency_key: str | None = None) -> VoidTransactionResult:
    """Ledger-led FEAT for transaction void orchestration."""
    is_pending = tx.status == TransactionStatus.PENDING

    if tx.type == 'purchase':
        _void_purchase(tx)
    elif tx.type == 'Rent Payment':
        _void_rent_payment(tx)

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
    matching_items = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == tx.seat_id,
            EntitlementEvent.class_id == tx.class_id,
            EntitlementEvent.product_id == store_item.id,
            EntitlementEvent.event_type == "GRANTED",
        )
        .order_by(EntitlementEvent.timestamp.asc())
        .all()
    )
    if not matching_items:
        raise ValueError("No matching student item was found for this purchase.")

    tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()

    def _distance(purchase):
        if not purchase.granted_at:
            return float('inf')
        return abs((ensure_utc(purchase.granted_at) - tx_ts).total_seconds())

    matching_items.sort(key=lambda si: (_distance(si), -si.id))
    selected_items = []
    selected_units = 0
    for purchase in matching_items:
        selected_items.append(purchase)
        selected_units += 1
        if selected_units >= quantity:
            break
    if selected_units < quantity:
        raise ValueError("Unable to map this transaction to purchasable student items.")

    if any(
        EntitlementEvent.query.filter_by(
            entitlement_id=event.entitlement_id,
            class_id=tx.class_id,
            event_type="CONSUMED",
        ).first()
        for event in selected_items
    ):
        raise ValueError("Transaction cannot be voided because selected entitlements are already consumed.")

    ledger_service.create_pending_transaction(
        seat_id=tx.seat_id,
        class_id=tx.class_id,
        target_seat_id=tx.seat_id,
        actor_seat_id=tx.actor_seat_id or tx.seat_id,
        mechanism=tx.mechanism.value if getattr(tx, "mechanism", None) else "system",
        user_id=tx.user_id,
        amount=Decimal('0.00'),
        account_type=tx.account_type or 'checking',
        type='void_item_removed',
        description=f"item removed - {store_item.name}",
    )
    # Canonical entitlement state is authoritative; the void path only records
    # the compensating ledger effect here.


def _void_rent_payment(tx: Transaction) -> None:
    if not tx.class_id:
        raise ValueError("Transaction is missing class scope (class_id) and cannot be voided safely.")
    
    rent_payments = obligations_service.get_paid_rent_assessments_for_cycle(
        tx.class_id,
        tx.timestamp.month if tx.timestamp else utc_now().month,
        tx.timestamp.year if tx.timestamp else utc_now().year,
        seat_ids=[tx.seat_id],
    )

    rent_payments = [
        payment for payment in rent_payments
        if payment.satisfaction and payment.satisfaction.amount_paid == abs(tx.amount or Decimal('0.00'))
    ]

    if rent_payments:
        tx_ts = ensure_utc(tx.timestamp) if tx.timestamp else utc_now()
        matched_rent_payment = min(
            rent_payments,
            key=lambda p: abs((ensure_utc(p.satisfaction.satisfied_at or tx.timestamp or utc_now()) - tx_ts).total_seconds())
        )
        obligations_service.remove_rent_payment_assessment(matched_rent_payment.id)
