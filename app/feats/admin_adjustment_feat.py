from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import ledger_service
from app.utils.overdraft import evaluate_overdraft_allowance


@dataclass
class AdminAdjustmentResult:
    applied_count: int
    declined_count: int
    fee_count: int


def execute_admin_adjustments(*, adjustments: list[dict], banking_settings=None) -> AdminAdjustmentResult:
    """Ledger-led FEAT for bulk admin-created adjustments."""
    applied_count = 0
    declined_count = 0
    fee_count = 0

    for adjustment in adjustments:
        seat = adjustment.get("seat")
        if not seat:
            raise KeyError("Adjustment missing 'seat'. Bulk adjustments must be seat-bound.")

        amount = Decimal(str(adjustment["amount"]))
        account_type = adjustment.get("account_type", "checking")
        user_id = adjustment["user_id"]
        class_id = seat.class_id

        shortfall = Decimal("0.00")
        if account_type == "checking" and amount < 0:
            allowed, shortfall, _, _ = evaluate_overdraft_allowance(
                seat,
                abs(amount),
                banking_settings,
            )
            if not allowed:
                fee_charged, _ = ledger_service.apply_overdraft_fee_if_needed(
                    seat,
                    banking_settings,
                    force=True,
                )
                if fee_charged:
                    fee_count += 1
                declined_count += 1
                continue

        ledger_service.create_pending_transaction(
            seat_id=seat.id,
            class_id=class_id,
            teacher_id=user_id,
            amount=amount,
            account_type=account_type,
            type=adjustment["type"],
            description=adjustment["description"],
        )
        applied_count += 1

        if account_type == "checking" and amount < 0 and shortfall > 0:
            ledger_service.create_transfer_pair(
                seat_id=seat.id,
                class_id=class_id,
                teacher_id=user_id,
                amount=shortfall,
                from_account="savings",
                to_account="checking",
                withdraw_description="Overdraft protection transfer to checking",
                deposit_description="Overdraft protection transfer from savings",
            )

    db.session.flush()

    return AdminAdjustmentResult(applied_count=applied_count, declined_count=declined_count, fee_count=fee_count)
