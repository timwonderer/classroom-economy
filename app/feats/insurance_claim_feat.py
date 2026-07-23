"""
FEAT-STOR-003: Insurance Claim Lifecycle
"""

from __future__ import annotations

from dataclasses import dataclass

from app.feats.base import requires_feat_context
from app.services.store_entitlement_service import (
    approve_insurance_claim,
    get_entitlement,
    get_insurance_claim,
    reject_insurance_claim,
    submit_insurance_claim,
)
from app.utils.insurance_eligibility import (
    CLAIM_TYPE_NON_MONETARY,
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
    if resolved not in {CLAIM_TYPE_TRANSACTION_MONETARY, CLAIM_TYPE_NON_MONETARY}:
        raise InsuranceClaimError("INVALID_CLAIM_TYPE")
    return resolved


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
    policy_claim_type: str | None = None,
) -> InsuranceClaimResult:
    claim = get_insurance_claim(claim_id=claim_id)
    if claim is None:
        raise InsuranceClaimError("CLAIM_NOT_FOUND")
    claim_type = _resolve_claim_type(claim=claim, policy_claim_type=policy_claim_type)
    claim = approve_insurance_claim(claim_id=claim_id, decided_by_seat_id=decided_by_seat_id)
    if claim_type == CLAIM_TYPE_TRANSACTION_MONETARY:
        return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Transaction claim approved.")
    return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Non-monetary claim approved.")


@requires_feat_context("FEAT-STOR-003")
def execute_claim_rejection(
    *,
    claim_id: str,
    decided_by_seat_id: int,
) -> InsuranceClaimResult:
    claim = reject_insurance_claim(claim_id=claim_id, decided_by_seat_id=decided_by_seat_id)
    return InsuranceClaimResult(claim_id=claim.claim_id, status=claim.status.value, message="Claim rejected.")
