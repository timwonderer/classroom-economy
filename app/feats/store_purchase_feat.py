from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import access_policy_service, identity_service, ledger_service, store_service
from app.utils.time import utc_now


from app.feats.base import requires_feat_context

@dataclass
class StorePurchaseResult:
    transaction_id: int
    student_item_ids: list[int]
    hall_pass_balance: int | None = None
    rent_uses_remaining: int | None = None
    success_message: str = ""


@requires_feat_context("FEAT-STOR-001-RENT-PERK")
def execute_rent_perk_purchase(
    *,
    scope,
    seat,
    teacher_id: int,
    item,
    active_rent_item,
    ensure_active_grant: bool = False,
    rent_grant_use_limit: int | None = None,
    banking_settings,
    purchase_idempotency_key: str | None = None,
):
    """Store-led FEAT for zero-cost rent-perk purchases."""
    class_id = scope.class_id
    access_policy_service.assert_can_purchase_item(
        scope=scope,
        teacher_id=teacher_id,
        class_id=class_id,
    )
    description = f"Purchase: {item.name} [Rent Perk $0]"
    if purchase_idempotency_key:
        purchase_tx, created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=purchase_idempotency_key,
            seat_id=seat.id,
            class_id=class_id,
            teacher_id=teacher_id,
            amount=Decimal('0.00'),
            account_type='checking',
            type='purchase',
            description=description,
        )
        if not created:
            return StorePurchaseResult(
                transaction_id=purchase_tx.id,
                student_item_ids=[],
                success_message=f"You purchased {item.name} for $0 (rent perk). Purchase already recorded.",
            )
    else:
        purchase_tx = ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            teacher_id=teacher_id,
            amount=Decimal('0.00'),
            account_type='checking',
            type='purchase',
            description=description,
        )

    if ensure_active_grant and active_rent_item is None:
        active_rent_item = store_service.ensure_active_rent_per_use_grant(
            seat=seat,
            store_item_id=item.id,
            use_limit=rent_grant_use_limit,
            now=utc_now(),
            expiry_date=None,
        )

    db.session.flush()
    student_item = store_service.record_rent_perk_purchase(
        seat=seat,
        item=item,
        purchase_tx_id=purchase_tx.id,
        active_rent_item=active_rent_item,
        now=utc_now(),
    )

    return StorePurchaseResult(
        transaction_id=purchase_tx.id,
        student_item_ids=[student_item.id],
        rent_uses_remaining=active_rent_item.uses_remaining if active_rent_item else None,
        success_message=f"You purchased {item.name} for $0 (rent perk).",
    )


@requires_feat_context("FEAT-STOR-002")
def execute_store_purchase(
    *,
    scope,
    seat,
    teacher_id: int,
    student_id: int | None,
    item,
    quantity: int,
    total_price: Decimal,
    purchase_description: str,
    banking_settings,
    purchase_idempotency_key: str | None = None,
    expiry_date=None,
    uses_remaining=None,
    student_item_status: str = 'purchased',
):
    """Store-led FEAT for standard purchases."""
    class_id = scope.class_id
    access_policy_service.assert_can_purchase_item(
        scope=scope,
        teacher_id=teacher_id,
        class_id=class_id,
    )
    if purchase_idempotency_key:
        purchase_tx, created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=purchase_idempotency_key,
            seat_id=seat.id,
            class_id=class_id,
            teacher_id=teacher_id,
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description,
        )
        if not created:
            return StorePurchaseResult(
                transaction_id=purchase_tx.id,
                student_item_ids=[],
                success_message=f"{item.name} purchase already recorded.",
            )
    else:
        purchase_tx = ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            teacher_id=teacher_id,
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description,
        )

    db.session.flush()
    store_service.decrement_inventory(item, quantity)

    hall_pass_balance = None
    created_item_ids: list[int] = []

    if item.item_type == 'hall_pass':
        hall_pass_balance = identity_service.add_hall_passes(seat, quantity)
    else:
        created_item_ids = store_service.record_standard_purchase_items(
            seat=seat,
            student_id=student_id,
            item=item,
            quantity=quantity,
            purchase_tx_id=purchase_tx.id,
            expiry_date=expiry_date,
            student_item_status=student_item_status,
            uses_remaining=uses_remaining,
        )

    checking_balance, savings_balance = ledger_service.get_available_balances(seat.id, class_id)
    if banking_settings and banking_settings.overdraft_protection_enabled and checking_balance < 0:
        shortfall = abs(checking_balance)
        if savings_balance >= shortfall:
            ledger_service.create_transfer_pair(
                seat_id=seat.id,
                class_id=class_id,
                teacher_id=teacher_id,
                amount=shortfall,
                from_account='savings',
                to_account='checking',
                withdraw_description='Overdraft protection transfer to checking',
                deposit_description='Overdraft protection transfer from savings',
            )
            db.session.flush()

    ledger_service.apply_overdraft_fee_if_needed(
        seat,
        banking_settings,
        idempotency_key=f"{purchase_idempotency_key}:overdraft" if purchase_idempotency_key else None
    )

    if item.item_type == 'collective':
        store_service.unlock_collective_goal_if_ready(
            item=item,
            class_id=class_id,
        )

    # FEAT-LEGACY-WRAP: commit moved to shell

    success_message = f"You purchased {item.name}!"
    if item.is_bundle and item.bundle_quantity is not None:
        success_message = f"You purchased {quantity} bundle(s) of {item.name}! You have {item.bundle_quantity * quantity} uses."
    elif quantity > 1:
        success_message = f"You purchased {quantity}x {item.name}!"

    if item.bulk_discount_enabled and item.bulk_discount_quantity is not None and item.bulk_discount_percentage is not None and quantity >= item.bulk_discount_quantity:
        success_message += f" (Saved {item.bulk_discount_percentage}% with bulk discount!)"

    return StorePurchaseResult(
        transaction_id=purchase_tx.id,
        student_item_ids=created_item_ids,
        hall_pass_balance=hall_pass_balance,
        success_message=success_message,
    )
