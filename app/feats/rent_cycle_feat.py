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
    cycle_start = ensure_utc(execution_time) if execution_time else utc_now()
    cycle_length_days = int(getattr(settings, "cycle_length_days", 30) or 30)
    cycle_end = cycle_start + timedelta(days=cycle_length_days)
    cycle_start_class = to_class_time(cycle_start, class_id)

    user_id = seat.class_economy.user_id if getattr(seat, "class_economy", None) else None
    amount = Decimal(str(getattr(settings, "rent_amount", Decimal("0.00")) or Decimal("0.00")))
    period = (seat.class_economy.section if getattr(seat, "class_economy", None) else "A").strip().upper()

    transaction, _created = ledger_service.create_pending_transaction_idempotent(
        idempotency_key=idempotency_key,
        seat_id=seat.id,
        class_id=class_id,
        target_seat_id=seat.id,
        actor_seat_id=ledger_service.resolve_class_authority_seat_id(class_id),
        mechanism="system",
        user_id=user_id,
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
    )
    db.session.flush()

    return ScheduledRentChargeResult(
        transaction_id=transaction.id,
        payment_id=payment.id,
        cycle_idempotency_key=idempotency_key,
    )
