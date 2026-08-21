from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services.context_resolver import CanonicalContext
from app.services import ledger_service
from app.services.class_configuration_query_service import get_current_economic_engine
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan


@dataclass
class AdminAdjustmentResult:
    applied_count: int
    declined_count: int
    fee_count: int


def execute_admin_adjustments(
    *,
    ctx: CanonicalContext,
    adjustments: list[dict],
    actor_seat_id: int,
) -> AdminAdjustmentResult:
    """Ledger-led FEAT for bulk admin-created adjustments."""
    applied_count = 0
    declined_count = 0
    fee_count = 0
    economic_engine = get_current_economic_engine(ctx.class_id)

    for adjustment in adjustments:
        seat = adjustment.get("seat")
        if not seat:
            raise KeyError("Adjustment missing 'seat'. Bulk adjustments must be seat-bound.")
        if seat.class_id != ctx.class_id:
            raise ValueError("Adjustment seat must belong to the active canonical class context.")

        amount = Decimal(str(adjustment["amount"]))
        account_type = adjustment.get("account_type", "checking")
        user_id = adjustment["user_id"]
        class_id = seat.class_id
        mechanism = "system" if ctx.actor_role == "sysadmin" else "teacher"
        shortfall = Decimal("0.00")
        if account_type == "checking" and amount < 0:
            intended_plan = build_intended_ledger_plan(
                seat_id=seat.id,
                class_id=class_id,
                user_id=user_id,
                debit_amount=abs(amount),
                description=adjustment["description"],
                source_account="checking",
                target_account="admin_adjustment",
            )
            resolved_plan = resolve_intended_ledger_plan(
                plan=intended_plan,
                economic_engine=economic_engine,
                idempotency_key=f"admin-adjustment:{seat.id}:{class_id}:{amount}:resolve",
                force_overdraft_fee=True,
                allow_recovery_transfer=True,
            )
            if resolved_plan.outcome == "DENY":
                declined_count += 1
                continue
            if resolved_plan.overdraft_fee_amount > 0:
                fee_count += 1
            apply_resolved_ledger_plan(
                resolved_plan=resolved_plan,
                economic_engine=economic_engine,
                idempotency_key=f"admin-adjustment:{seat.id}:{class_id}:{amount}:fee",
            )

        ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            target_seat_id=seat.id,
            actor_seat_id=actor_seat_id,
            mechanism=mechanism,
            user_id=user_id,
            amount=amount,
            account_type=account_type,
            type=adjustment["type"],
            description=adjustment["description"],
        )
        applied_count += 1

    db.session.flush()

    return AdminAdjustmentResult(applied_count=applied_count, declined_count=declined_count, fee_count=fee_count)
