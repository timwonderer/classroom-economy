from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services.context_resolver import CanonicalContext
from app.feats.base import get_active_feat_name, get_idempotency_key
from app.services.ledger_command_service import create_reserved_effects


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
    """FEAT for bulk admin-created adjustments (teacher credits and penalties).

    An admin adjustment is a teacher-applied credit or PENALTY (fine). A penalty
    is neither an intended purchase nor an existing obligation, so — per the
    economic model — it MUST NOT generate an NSF/overdraft fine, and it does not
    raid the student's savings to cover itself. It posts as a direct ledger
    debit/credit on the seat's own account (INV-ARC-019: anchored on class_id +
    seat_id), settling below zero if the balance cannot cover the penalty.

    ``declined_count`` / ``fee_count`` are retained on the result for backward
    compatibility and are always 0: penalties are never declined for insufficient
    funds and never incur a fee.
    """
    effect_specs = []

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

        effect_specs.append({
            "seat_id": seat.id,
            "class_id": class_id,
            "target_seat_id": seat.id,
            "actor_seat_id": actor_seat_id,
            "mechanism": mechanism,
            "user_id": user_id,
            "amount": amount,
            "account_type": account_type,
            "type": adjustment["type"],
            "description": adjustment["description"],
        })

    if not effect_specs:
        return AdminAdjustmentResult(applied_count=0, declined_count=0, fee_count=0)
    feat_code = get_active_feat_name()
    idempotency_key = get_idempotency_key()
    if not feat_code or not idempotency_key:
        raise ValueError("Bulk Ledger adjustments require an active command reservation.")
    created_effects, _created = create_reserved_effects(
        class_id=ctx.class_id,
        feat_code=feat_code,
        idempotency_key=idempotency_key,
        effects=effect_specs,
    )
    applied_count = len(created_effects)

    db.session.flush()

    return AdminAdjustmentResult(applied_count=applied_count, declined_count=0, fee_count=0)
