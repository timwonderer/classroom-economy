from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import ClassEconomy, _quantize_currency
from app.services import access_policy_service, ledger_service, obligations_service, store_service
from app.services.entitlement_service import reconcile_rent_hall_pass_top_off
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.utils.join_code import get_display_join_code
from app.utils.time import utc_now


@dataclass
class RentPaymentResult:
    transaction_id: int
    payment_id: int
    passes_awarded: int
    per_use_items_granted: int
    is_partial: bool
    amount_paid: Decimal
    new_remaining: Decimal


def execute_rent_payment(
    *,
    seat,
    context: dict,
    payment_amount: Decimal,
    period: str,
    settings,
    is_late: bool,
    late_fee: Decimal,
    total_paid_so_far: Decimal,
    total_due: Decimal,
    remaining_amount: Decimal,
    coverage_month: int,
    coverage_year: int,
    current_month: int,
    current_year: int,
    payment_due_date,
    banking_settings=None,
    overdraft_shortfall: Decimal = Decimal("0.00"),
    now=None,
    calculate_due_dates_fn=None,
) -> RentPaymentResult:
    """Obligations-led FEAT for rent payment orchestration."""
    now = now or utc_now()
    user_id = getattr(context, "user_id", None)
    class_id = seat.class_id
    join_code = get_display_join_code(class_id)

    # Resolve the immutable policy version governing this cycle
    active_version = obligations_service.resolve_active_rent_policy_version(class_id)
    if active_version is None:
        raise ValueError(f"No active rent policy version for class {class_id}")

    access_policy_service.assert_can_pay_rent(
        seat_id=seat.id,
        class_id=class_id,
        user_id=user_id,
    )
    current_block = (getattr(seat, "block", None) or period or "").strip().upper()
    is_partial = payment_amount < remaining_amount

    billed_period_date = payment_due_date or now
    payment_description = f'Rent for Period {period} - {billed_period_date.strftime("%B %Y")}'
    if is_partial and settings.allow_incremental_payment:
        payment_description += f' (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})'
    elif late_fee > Decimal('0'):
        payment_description += f' (includes ${late_fee:.2f} late fee)'

    transaction = ledger_service.create_pending_transaction(
        seat_id=seat.id,
        class_id=class_id,
        user_id=user_id,
        amount=-payment_amount,
        account_type='checking',
        type='Rent Payment',
        description=payment_description,
    )
    late_fee_for_this_payment = Decimal('0.00')
    if is_late and late_fee > Decimal('0.00'):
        late_fee_for_this_payment = (
            _quantize_currency((payment_amount / total_due) * late_fee)
            if is_partial
            else _quantize_currency(late_fee)
        )

    payment = obligations_service.record_rent_payment(
        seat_id=seat.id,
        class_id=class_id,
        period=period,
        amount_paid=payment_amount,
        period_month=current_month,
        period_year=current_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        was_late=is_late,
        late_fee_charged=late_fee_for_this_payment,
        transaction_id=transaction.id,
        rent_policy_version_id=active_version.id,
    )
    db.session.flush()

    intended_plan = build_intended_ledger_plan(
        seat_id=seat.id,
        class_id=class_id,
        user_id=user_id,
        debit_amount=payment_amount,
        description=payment_description,
        source_account="checking",
        target_account="rent",
    )
    resolved_plan = resolve_intended_ledger_plan(
        plan=intended_plan,
        banking_settings=banking_settings,
        idempotency_key=f"rent_payment:{seat.id}:{class_id}:{period}:{coverage_year}-{coverage_month}:{payment_amount}:resolve",
        force_overdraft_fee=False,
        allow_recovery_transfer=True,
    )
    apply_resolved_ledger_plan(
        resolved_plan=resolved_plan,
        banking_settings=banking_settings,
        idempotency_key=(
            f"rent_payment:{seat.id}:{class_id}:{period}:"
            f"{coverage_year}-{coverage_month}:{payment_amount}"
        ),
    )

    passes_awarded = 0
    per_use_items_granted = 0
    newly_fully_paid = total_paid_so_far < total_due and (total_paid_so_far + payment_amount >= total_due)
    if newly_fully_paid:
        target_rent_passes = store_service.get_rent_hall_pass_grant_total_from_version(active_version)
        passes_awarded, _, _ = reconcile_rent_hall_pass_top_off(
            seat=seat,
            target_rent_passes=target_rent_passes,
        )
        if calculate_due_dates_fn is not None:
            per_use_items_granted = store_service.grant_rent_per_use_items_from_version(
                seat=seat,
                version=active_version,
                calculate_due_dates_fn=calculate_due_dates_fn,
                settings=settings,
            )

    db.session.flush()

    return RentPaymentResult(
        transaction_id=transaction.id,
        payment_id=payment.id,
        passes_awarded=passes_awarded,
        per_use_items_granted=per_use_items_granted,
        is_partial=is_partial,
        amount_paid=payment_amount,
        new_remaining=_quantize_currency(total_due - (total_paid_so_far + payment_amount)),
    )
