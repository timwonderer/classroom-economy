"""
FEAT-STOR-003: Insurance Claim Lifecycle
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from app.feats.base import requires_feat_context
from app.feats.prod import record_payroll_event
from app.services import ledger_service
from app.services.store_entitlement_service import (
    approve_insurance_claim,
    get_entitlement,
    get_insurance_claim,
    reject_insurance_claim,
    submit_insurance_claim,
)
from app.utils.insurance_eligibility import (
    CLAIM_TYPE_NON_MONETARY,
    CLAIM_TYPE_PRODUCTIVITY,
    CLAIM_TYPE_TRANSACTION_MONETARY,
    resolve_claim_type,
)


@dataclass
class InsuranceClaimResult:
    claim_id: str
    status: str
    message: str


class InsuranceClaimError(Exception):
    pass


def _validate_insurance_entitlement(entitlement) -> None:
    if entitlement is None:
        raise InsuranceClaimError("ENTITLEMENT_NOT_FOUND")


def _resolve_claim_type(*, claim=None, policy_claim_type: str | None = None) -> str:
    resolved = resolve_claim_type(claim=claim, policy_claim_type=policy_claim_type)
    return resolved


def _resolve_policy_version_id_from_claim(claim) -> int | None:
    entitlement = getattr(claim, "entitlement", None)
    if entitlement is None:
        return None
    entitlement_item_id = getattr(entitlement, "entitlement_item_id", None)
    class_id = getattr(claim, "class_id", None) or getattr(entitlement, "class_id", None)
    if entitlement_item_id is None or not class_id:
        return None
    from app.models import PolicyVersion
    version = None
    for candidate in (
        PolicyVersion.query.filter_by(class_id=class_id, domain="insurance")
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .all()
    ):
        try:
            payload = json.loads(candidate.policy_payload_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if int(payload.get("entitlement_item_id") or 0) == int(entitlement_item_id):
            version = candidate
            break
    return version.id if version else None


@requires_feat_context("FEAT-STOR-003")
def execute_claim_submission(
    *,
    entitlement_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    class_id: str,
    transaction_id: int | None = None,
    claimed_dates: dict | list | None = None,
    correlation_id: str | None = None,
    policy_claim_type: str | None = None,
) -> InsuranceClaimResult:
    entitlement = get_entitlement(entitlement_id=entitlement_id)
    _validate_insurance_entitlement(entitlement)
    claim_type = _resolve_claim_type(policy_claim_type=policy_claim_type)
    claim = submit_insurance_claim(
        entitlement_id=entitlement_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        class_id=class_id,
        transaction_id=transaction_id,
        claimed_dates=claimed_dates,
        correlation_id=correlation_id,
    )
    return InsuranceClaimResult(
        claim_id=claim.claim_id,
        status=claim.status.value,
        message=f"{claim_type.replace('_', ' ').title()} claim submitted.",
    )


@requires_feat_context("FEAT-STOR-003")
def execute_claim_approval(
    *,
    claim_id: str,
    decided_by_seat_id: int,
    ctx=None,
    policy_claim_type: str | None = None,
) -> InsuranceClaimResult:
    claim = get_insurance_claim(claim_id=claim_id)
    if claim is None:
        raise InsuranceClaimError("CLAIM_NOT_FOUND")
    claim_type = _resolve_claim_type(claim=claim, policy_claim_type=policy_claim_type)
    claim = approve_insurance_claim(claim_id=claim_id, decided_by_seat_id=decided_by_seat_id)
    if claim_type == CLAIM_TYPE_TRANSACTION_MONETARY and claim.referenced_transaction is not None:
        ledger_service.create_pending_transaction(
            seat_id=claim.target_seat_id,
            class_id=claim.class_id,
            target_seat_id=claim.target_seat_id,
            actor_seat_id=decided_by_seat_id,
            mechanism="teacher",
            user_id=None,
            amount=abs(claim.referenced_transaction.amount or 0),
            account_type=claim.referenced_transaction.account_type or "checking",
            type="insurance_reimbursement",
            description=f"Insurance reimbursement: {claim.referenced_transaction.description or claim.claim_id}",
            original_transaction_id=claim.referenced_transaction.id,
            policy_id=None,
        )
    if claim_type == CLAIM_TYPE_PRODUCTIVITY:
        policy_version_id = _resolve_policy_version_id_from_claim(claim)
        if policy_version_id is None:
            raise InsuranceClaimError("POLICY_VERSION_NOT_FOUND")
        approved_amount = (
            getattr(claim, "approved_amount", None)
            or getattr(claim, "claim_amount", None)
            or Decimal("0.00")
        )
        approved_amount = Decimal(str(approved_amount))
        if approved_amount > 0 and ctx is not None:
            record_payroll_event(
                ctx=ctx,
                target_seat_id=claim.target_seat_id,
                payroll_event_type="manual_credit",
                correlation_id=claim.correlation_id or claim.claim_id,
                idempotency_key=f"insurance-productivity:{claim.claim_id}",
                policy_version_id=policy_version_id,
                mechanism="teacher",
                summary_json={
                    "description": f"Insurance productivity reimbursement: {claim.claim_id}",
                    "source": "insurance_claim_approval",
                },
                amount=approved_amount,
            )
    if claim_type == CLAIM_TYPE_TRANSACTION_MONETARY:
        return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Transaction claim approved.")
    if claim_type == CLAIM_TYPE_PRODUCTIVITY:
        return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Productivity claim approved.")
    if claim_type == CLAIM_TYPE_NON_MONETARY:
        return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Non-monetary claim approved.")
    return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Non-monetary claim approved.")


@requires_feat_context("FEAT-STOR-003")
def execute_claim_rejection(
    *,
    claim_id: str,
    decided_by_seat_id: int,
) -> InsuranceClaimResult:
    claim = reject_insurance_claim(claim_id=claim_id, decided_by_seat_id=decided_by_seat_id)
    return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Claim rejected.")
