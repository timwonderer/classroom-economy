from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.utils.time import ensure_utc, to_class_time, utc_now


@dataclass
class ScheduledRentChargeResult:
    transaction_id: int
    payment_id: int
    cycle_idempotency_key: str


@feat_shell("FEAT-OBL-002")
def execute_scheduled_rent_charge(
    *,
    seat,
    settings,
    class_id: str,
    execution_time,
    idempotency_key: str,
) -> ScheduledRentChargeResult:
    """
    FEAT-wrapped scheduled rent charge for one seat + one class cycle.
    """
    # Resolve the immutable policy version governing this cycle
    active_version = obligations_service.resolve_active_rent_policy_version(class_id)
    if active_version is None:
        raise ValueError(f"No active rent policy version for class {class_id}")

    cycle_start = ensure_utc(execution_time) if execution_time else utc_now()
    cycle_length_days = int(active_version.cycle_length_days or 30)
    cycle_end = cycle_start + timedelta(days=cycle_length_days)
    cycle_start_class = to_class_time(cycle_start, class_id)

    user_id = seat.class_economy.user_id if getattr(seat, "class_economy", None) else None
    amount = Decimal(str(active_version.rent_amount or Decimal("0.00")))
    period = (seat.block_identifier or seat.block or "A").strip().upper()

    transaction, _created = ledger_service.create_pending_transaction_idempotent(
        idempotency_key=idempotency_key,
        seat_id=seat.id,
        class_id=class_id,
        teacher_id=user_id,  # ledger API still uses teacher_id; DOM-LED canonicalization pending
        amount=-amount,
        account_type="checking",
        type="Rent Payment",
        description=f"Scheduled rent cycle charge ({cycle_start.isoformat()})",
    )

    payment = obligations_service.record_rent_payment(
        seat_id=seat.id,
        class_id=class_id,
        period=period,
        amount_paid=amount,
        period_month=cycle_start_class.month,
        period_year=cycle_start_class.year,
        coverage_month=cycle_start_class.month,
        coverage_year=cycle_start_class.year,
        coverage_start_time=cycle_start,
        coverage_end_time=cycle_end,
        cycle_idempotency_key=idempotency_key,
        was_late=False,
        late_fee_charged=Decimal("0.00"),
        rent_policy_version_id=active_version.id,
    )
    db.session.flush()

    return ScheduledRentChargeResult(
        transaction_id=transaction.id,
        payment_id=payment.id,
        cycle_idempotency_key=idempotency_key,
    )
