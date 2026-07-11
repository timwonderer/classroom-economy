from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.services import access_policy_service, ledger_service, obligations_service
from app.utils.time import utc_now
from app.utils.transaction_idempotency import insurance_reimbursement_key


@dataclass
class InsuranceClaimResolutionResult:
    claim_id: int
    reimbursement_transaction_id: int | None


@dataclass
class InsuranceClaimFileResult:
    claim_id: int


def execute_file_claim(
    *,
    scope,
    enrollment,
    seat_id: int,
    class_id: str,
    incident_date,
    description: str,
    claim_amount,
    claim_item: str | None,
    comments: str | None,
    transaction_id: int | None,
):
    """Obligations-led FEAT for student claim filing."""
    access_policy_service.assert_can_file_claim(
        scope=scope,
        enrollment=enrollment,
    )
    claim = obligations_service.record_insurance_claim(
        enrollment_id=enrollment.id,
        policy_id=enrollment.policy_id,
        seat_id=seat_id,
        class_id=class_id,
        incident_date=incident_date,
        description=description,
        claim_amount=claim_amount,
        claim_item=claim_item,
        comments=comments,
        transaction_id=transaction_id,
    )
    return InsuranceClaimFileResult(claim_id=claim.id)


def execute_insurance_claim_resolution(
    *,
    scope,
    claim,
    enrollment,
    new_status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_user_id: int | None,
    approved_amount: Decimal | None,
    processed_by_seat_id: int | None = None,
):
    """Obligations-led FEAT for insurance claim resolution and reimbursement."""
    access_policy_service.assert_can_process_claim(
        scope=scope,
        enrollment=enrollment,
        claim=claim,
    )
    processed_at = utc_now()
    obligations_service.apply_claim_resolution(
        claim,
        status=new_status,
        teacher_notes=teacher_notes,
        rejection_reason=rejection_reason,
        processed_by_user_id=processed_by_user_id,
        processed_by_seat_id=processed_by_seat_id,
        processed_at=processed_at,
        approved_amount=approved_amount,
    )

    reimbursement_tx_id = None
    if approved_amount is not None and new_status in ("approved", "paid"):
        transaction_description = f"Insurance reimbursement for claim #{claim.id} ({enrollment.contract_title})"
        if claim.transaction_id:
            transaction_description += f" linked to transaction #{claim.transaction_id}"
        reimbursement_tx, _created = ledger_service.create_pending_transaction_idempotent(
            idempotency_key=insurance_reimbursement_key(claim.id),
            seat_id=claim.seat_id,
            class_id=scope.class_id,
            user_id=processed_by_user_id,
            amount=approved_amount,
            account_type="checking",
            type="insurance_reimbursement",
            description=transaction_description,
            original_transaction_id=claim.transaction_id,
            policy_id=claim.policy_id,
        )
        reimbursement_tx_id = reimbursement_tx.id

    return InsuranceClaimResolutionResult(claim_id=claim.id, reimbursement_transaction_id=reimbursement_tx_id)
