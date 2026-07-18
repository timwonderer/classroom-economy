from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.utils.insurance_billing import get_insurance_billing_snapshot, insurance_next_payment_due
from app.utils.time import ensure_utc, utc_now


@dataclass
class ScheduledInsuranceChargeResult:
    transaction_id: int
    assessment_id: int
    cycle_idempotency_key: str


@feat_shell("FEAT-OBL-003")
def execute_scheduled_insurance_charge(
    *,
    seat,
    policy_version,
    class_id: str,
    execution_time,
    idempotency_key: str,
) -> ScheduledInsuranceChargeResult:
    """FEAT-wrapped scheduled insurance charge for one seat."""
    cycle_start = ensure_utc(execution_time) if execution_time else utc_now()
    snapshot = get_insurance_billing_snapshot(policy_version)
    premium = Decimal(str(snapshot["premium"] or "0.00"))
    due_at = insurance_next_payment_due(cycle_start, snapshot["charge_frequency"])
    coverage_start_time = cycle_start
    coverage_end_time = due_at
    user_id = seat.class_economy.user_id if getattr(seat, "class_economy", None) else None

    transaction, _created = ledger_service.create_pending_transaction_idempotent(
        idempotency_key=idempotency_key,
        seat_id=seat.id,
        class_id=class_id,
        target_seat_id=seat.id,
        actor_seat_id=ledger_service.resolve_class_authority_seat_id(class_id),
        mechanism="system",
        user_id=user_id,
        amount=-premium,
        account_type="checking",
        type="insurance_premium",
        description=f"Insurance premium: {getattr(policy_version, 'id', 'unknown')}",
        policy_id=getattr(policy_version, "id", None),
    )

    assessment = obligations_service.record_insurance_premium_payment(
        seat_id=seat.id,
        class_id=class_id,
        policy_version_id=getattr(policy_version, "id", None),
        amount_paid=premium,
        due_at=due_at,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=idempotency_key,
        transaction_id=transaction.id,
    )
    db.session.flush()

    return ScheduledInsuranceChargeResult(
        transaction_id=transaction.id,
        assessment_id=assessment.id,
        cycle_idempotency_key=idempotency_key,
    )
