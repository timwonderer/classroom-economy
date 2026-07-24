from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.services.store_entitlement_service import grant_entitlement
from app.utils.time import utc_now
from app.utils.insurance_eligibility import compute_coverage_start_utc_from_purchase
from app.models import GrantType


@dataclass
class InsurancePurchaseResult:
    enrollment_id: int
    premium_transaction_id: int
    entitlement_id: str | None
    overdraft_transfer_applied: bool


@feat_shell("FEAT-STOR-001")
def execute_insurance_purchase(
    *,
    seat,
    user_id: int,
    class_id: str,
    policy,
    banking_settings,
    overdraft_shortfall: Decimal = Decimal("0.00"),
) -> InsurancePurchaseResult:
    """Obligations-led FEAT for insurance enrollment + premium debit."""
    purchase_utc = utc_now()
    coverage_start_utc = compute_coverage_start_utc_from_purchase(
        purchase_utc=purchase_utc,
        class_id=class_id,
        waiting_period_days=policy.waiting_period_days,
    )

    enrollment = obligations_service.record_insurance_enrollment(
        seat_id=seat.id,
        policy=policy,
        class_id=class_id,
        purchase_date=purchase_utc,
        next_payment_due=purchase_utc + timedelta(days=30),
        coverage_start_date=coverage_start_utc,
    )

    entitlement = None
    entitlement_item_id = getattr(policy, "entitlement_item_id", None)
    if entitlement_item_id is not None:
        entitlement = grant_entitlement(
            entitlement_item_id=entitlement_item_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            class_id=class_id,
            grant_type=GrantType.PURCHASE,
            correlation_id=f"insurance:{seat.id}:{class_id}:{policy.id}",
        )

    premium_tx = ledger_service.create_pending_transaction(
        seat_id=seat.id,
        class_id=class_id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        user_id=user_id,
        amount=-policy.premium,
        account_type="checking",
        type="insurance_premium",
        description=f"Insurance premium: {policy.title}",
        policy_id=policy.id,
    )

    overdraft_transfer_applied = False
    if banking_settings and banking_settings.overdraft_protection_enabled and overdraft_shortfall > 0:
        intended_plan = build_intended_ledger_plan(
            seat_id=seat.id,
            class_id=class_id,
            user_id=user_id,
            debit_amount=policy.premium,
            description=f"Insurance premium: {policy.title}",
            source_account="checking",
            target_account="insurance",
        )
        resolved_plan = resolve_intended_ledger_plan(
            plan=intended_plan,
            banking_settings=banking_settings,
            idempotency_key=f"insurance:{seat.id}:{class_id}:{policy.id}:resolve",
            force_overdraft_fee=False,
            allow_recovery_transfer=True,
        )
        apply_resolved_ledger_plan(
            resolved_plan=resolved_plan,
            banking_settings=banking_settings,
            idempotency_key=f"insurance:{seat.id}:{class_id}:{policy.id}:overdraft",
        )
        overdraft_transfer_applied = resolved_plan.recovery_transfer_amount > 0

    return InsurancePurchaseResult(
        enrollment_id=enrollment.id,
        premium_transaction_id=premium_tx.id,
        entitlement_id=getattr(entitlement, "entitlement_id", None),
        overdraft_transfer_applied=overdraft_transfer_applied,
    )
