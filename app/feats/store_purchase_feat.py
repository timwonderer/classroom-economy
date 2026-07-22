from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import ledger_service, store_service
from app.services.entitlement_service import grant_hall_passes
from app.services.context_resolver import CanonicalContext
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.utils.time import utc_now


from app.feats.base import requires_feat_context

@dataclass
class StorePurchaseResult:
    transaction_id: int
    purchase_ids: list[int]
    hall_pass_balance: int | None = None
    rent_uses_remaining: int | None = None
    success_message: str = ""


@requires_feat_context("FEAT-STOR-004")
def execute_rent_perk_purchase(
    *,
    ctx: CanonicalContext,
    seat,
    item,
    active_rent_item,
    ensure_active_grant: bool = False,
    rent_grant_use_limit: int | None = None,
    banking_settings,
    purchase_idempotency_key: str | None = None,
):
    description = f"Purchase: {item.name} [Rent Perk $0]"
    class_id = ctx.class_id
    if purchase_idempotency_key:
        purchase_tx, created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=purchase_idempotency_key,
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=Decimal('0.00'),
            account_type='checking',
            type='purchase',
            description=description,
        )
        if not created:
            return StorePurchaseResult(
                transaction_id=purchase_tx.id,
                purchase_ids=[],
                success_message=f"You purchased {item.name} for $0 (rent perk). Purchase already recorded.",
            )
    else:
        purchase_tx = ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
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
    purchase = store_service.record_rent_perk_purchase(
        seat=seat,
        item=item,
        purchase_tx_id=purchase_tx.id,
        active_rent_item=active_rent_item,
        now=utc_now(),
    )

    return StorePurchaseResult(
        transaction_id=purchase_tx.id,
        purchase_ids=[purchase.id],
        rent_uses_remaining=active_rent_item.uses_remaining if active_rent_item else None,
        success_message=f"You purchased {item.name} for $0 (rent perk).",
    )


@requires_feat_context("FEAT-STOR-002")
def execute_store_purchase(
    *,
    ctx: CanonicalContext,
    seat,
    item,
    quantity: int,
    total_price: Decimal,
    purchase_description: str,
    banking_settings,
    purchase_idempotency_key: str | None = None,
    expiry_date=None,
    uses_remaining=None,
    purchase_status: str = 'purchased',
):
    class_id = ctx.class_id
    if purchase_idempotency_key:
        purchase_tx, created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=purchase_idempotency_key,
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description,
        )
        if not created:
            return StorePurchaseResult(
                transaction_id=purchase_tx.id,
                purchase_ids=[],
                success_message=f"{item.name} purchase already recorded.",
            )
    else:
        purchase_tx = ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=-total_price,
            account_type='checking',
            type='purchase',
            description=purchase_description,
        )

    db.session.flush()
    store_service.decrement_inventory(item, quantity)

    hall_pass_balance = None
    created_purchase_ids: list[int] = []

    if item.item_type == 'hall_pass':
        hall_pass_balance = grant_hall_passes(
            seat,
            quantity,
            trigger_id=f"store_purchase_{seat.id}_{purchase_tx.id}",
            correlation_id=purchase_tx.correlation_id,
        )
    else:
        created_purchase_ids = store_service.record_standard_purchase_items(
            seat=seat,
            item=item,
            quantity=quantity,
            purchase_tx_id=purchase_tx.id,
            total_price=total_price,
            expiry_date=expiry_date,
            purchase_status=purchase_status,
            uses_remaining=uses_remaining,
            idempotency_key=purchase_idempotency_key,
        )

    intended_plan = build_intended_ledger_plan(
        seat_id=seat.id,
        class_id=class_id,
        user_id=getattr(seat, "user_id", None),
        debit_amount=total_price,
        description=purchase_description,
        source_account="checking",
        target_account="store",
    )
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        banking_settings=banking_settings,
        idempotency_key=purchase_idempotency_key or f"feat:store:purchase:{seat.id}:{class_id}:{item.id}:resolve",
        force_overdraft_fee=False,
        allow_recovery_transfer=True,
    )
    apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        banking_settings=banking_settings,
        idempotency_key=(
            f"{purchase_idempotency_key}:overdraft"
            if purchase_idempotency_key
            else f"feat:store:purchase:{seat.id}:{class_id}:{item.id}:overdraft"
        ),
    )

    if item.item_type == 'collective':
        store_service.unlock_collective_goal_if_ready(
            item=item,
            class_id=class_id,
        )

    success_message = f"You purchased {item.name}!"
    if item.is_bundle and item.bundle_quantity is not None:
        success_message = f"You purchased {quantity} bundle(s) of {item.name}! You have {item.bundle_quantity * quantity} uses."
    elif quantity > 1:
        success_message = f"You purchased {quantity}x {item.name}!"

    if item.bulk_discount_enabled and item.bulk_discount_quantity is not None and item.bulk_discount_percentage is not None and quantity >= item.bulk_discount_quantity:
        success_message += f" (Saved {item.bulk_discount_percentage}% with bulk discount!)"

    return StorePurchaseResult(
        transaction_id=purchase_tx.id,
        purchase_ids=created_purchase_ids,
        hall_pass_balance=hall_pass_balance,
        success_message=success_message,
    )
