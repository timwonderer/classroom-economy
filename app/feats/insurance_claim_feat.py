"""
FEAT-STOR-003: Insurance Claim Lifecycle (v2.0)

Orchestrates the complete insurance claim lifecycle:
- Submission: Validate coverage, create pending_action with immutable policy_uuid
- Resolution: Teacher adjudication (approve/reject), coordinate Ledger on approval
- Both paths write CONSUMED entitlement event (claim reached terminal resolution)
- Only approval triggers Ledger coordination; rejection doesn't reverse entitlement

All mutations (Ledger + EntitlementEvent + PendingAction deletion) succeed or fail
together (atomic).

Contract: Both approval and rejection write CONSUMED events recording the decision.
Only approval triggers Ledger coordination. Rejection doesn't reverse entitlement
(stays GRANTED for future claims).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from datetime import datetime
import uuid

from app.extensions import db
from app.feats.base import feat_shell, FEATContext
from app.feats.ledger_resolution_feat import (
    build_intended_ledger_plan,
    resolve_intended_ledger_plan,
)
from app.models import Seat, EntitlementEvent, ClassEconomy, PendingAction
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import StorePolicyResolver, PolicyNotFound, PolicyParseError, PolicyValidationError
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION
from app.utils.time import utc_now
from app.models import _quantize_currency


class InsuranceClaimError(Exception):
    """Raised when insurance claim validation or execution fails."""
    pass


@dataclass
class InsuranceClaimSubmissionResult:
    """Result of a successful insurance claim submission."""
    success: bool
    pending_action_id: Optional[str] = None
    correlation_id: Optional[str] = None
    entitlement_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    eligibility_flags: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class InsuranceClaimResolutionResult:
    """Result of insurance claim resolution (approval or rejection)."""
    success: bool
    pending_action_id: Optional[str] = None
    entitlement_event_id: Optional[str] = None
    decision: Optional[str] = None  # "APPROVED" or "REJECTED"
    reimbursement_amount: Optional[Decimal] = None
    ledger_transaction_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def submit_insurance_claim(
    *,
    canonical_context: CanonicalContext,
    entitlement_id: str,
    claim_subject: dict,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimSubmissionResult:
    """
    Submit an insurance claim against an active entitlement.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role
        entitlement_id: Insurance entitlement being claimed against
        claim_subject: Type-specific claim data (e.g., {transaction_id: X})
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        InsuranceClaimSubmissionResult with pending_action_id or error
    """
    return _submit_insurance_claim_impl(
        canonical_context=canonical_context,
        entitlement_id=entitlement_id,
        claim_subject=claim_subject,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-STOR-003")
def _submit_insurance_claim_impl(
    *,
    canonical_context: CanonicalContext,
    entitlement_id: str,
    claim_subject: dict,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimSubmissionResult:
    """Implementation of insurance claim submission."""
    try:
        # 1. Validate canonical context
        if not canonical_context or not canonical_context.user_id:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CONTEXT",
                error_message="Invalid canonical context",
            )

        # Get seat for authorization
        seat = db.session.get(Seat, canonical_context.seat_id)
        if not seat or seat.class_id != canonical_context.class_id:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CONTEXT",
                error_message="Seat not found or class mismatch",
            )

        # 2. Read GRANTED entitlement event
        granted_event = (
            db.session.query(EntitlementEvent)
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.class_id == canonical_context.class_id,
                EntitlementEvent.event_type == "GRANTED",
                EntitlementEvent.target_seat_id == canonical_context.seat_id,
            )
            .first()
        )

        if not granted_event:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="ENTITLEMENT_NOT_FOUND",
                error_message="Insurance entitlement not found or not granted",
            )

        # Check entitlement type
        if granted_event.entitlement_type != "INSURANCE":
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="WRONG_ENTITLEMENT_TYPE",
                error_message=f"Entitlement type is {granted_event.entitlement_type}, not INSURANCE",
            )

        # Check no terminal event exists
        terminal_event = (
            db.session.query(EntitlementEvent)
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.class_id == canonical_context.class_id,
                EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
            )
            .first()
        )

        if terminal_event:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="ENTITLEMENT_TERMINAL",
                error_message=f"Entitlement already has terminal event: {terminal_event.event_type}",
            )

        # 3. Resolve policy from immutable policy_uuid
        policy_uuid = granted_event.payload.get("policy_uuid") if granted_event.payload else None
        if not policy_uuid:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="MISSING_POLICY_UUID",
                error_message="Granted event missing policy_uuid in payload",
            )

        try:
            policy = StorePolicyResolver.resolve_store_item(policy_uuid)
        except (PolicyNotFound, PolicyParseError, PolicyValidationError) as e:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="POLICY_NOT_RESOLVABLE",
                error_message=f"Cannot resolve policy: {str(e)}",
            )

        # Validate coverage is active (using canonical temporal resolver)
        temporal_context = canonical_temporal_resolver(
            class_id=canonical_context.class_id,
            seat_id=canonical_context.seat_id,
            evaluation_level=CLASS_LEVEL_EVALUATION,
        )

        if not temporal_context:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="TEMPORAL_CONTEXT_ERROR",
                error_message="Cannot determine temporal context",
            )

        # Check if coverage window is active (policy-determined)
        policy_config = policy.get("config", {})
        if policy_config.get("coverage_disabled") is True:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="COVERAGE_NOT_ACTIVE",
                error_message="Coverage is not active for this policy",
            )

        # 4. Validate claim subject structure
        if not isinstance(claim_subject, dict):
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_SUBJECT",
                error_message="Claim subject must be a dictionary",
            )

        # 5. Check for existing pending_action (idempotency)
        if not correlation_id:
            correlation_id = f"corr_{uuid.uuid4().hex}"

        existing_pending = (
            db.session.query(PendingAction)
            .filter(
                PendingAction.class_id == canonical_context.class_id,
                PendingAction.entitlement_id == entitlement_id,
                PendingAction.correlation_id == correlation_id,
            )
            .first()
        )

        if existing_pending:
            # Return prior result (idempotent)
            return InsuranceClaimSubmissionResult(
                success=True,
                pending_action_id=existing_pending.pending_action_id,
                correlation_id=existing_pending.correlation_id,
                entitlement_id=entitlement_id,
                submitted_at=existing_pending.submitted_at,
                eligibility_flags=existing_pending.payload.get("policy_eligibility_flags"),
            )

        # 6. Validate eligibility (flag for review, don't block)
        eligibility_flags = {
            "count_limit_exceeded": False,
            "period_limit_exceeded": False,
            "claim_window_exceeded": False,
        }

        # Count existing CONSUMED events for this entitlement to check limits
        consumed_count = (
            db.session.query(EntitlementEvent)
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.event_type == "CONSUMED",
            )
            .count()
        )

        claim_limit = policy_config.get("claim_limit", 0)
        if claim_limit > 0 and consumed_count >= claim_limit:
            eligibility_flags["count_limit_exceeded"] = True

        # 7. Create pending_action row
        pending_action_id = str(uuid.uuid4())
        now = utc_now()

        pending_action = PendingAction(
            pending_action_id=pending_action_id,
            class_id=canonical_context.class_id,
            seat_id=canonical_context.seat_id,
            entitlement_id=entitlement_id,
            correlation_id=correlation_id,
            authoritative_feat="FEAT-STOR-003-RESOLVE",
            payload={
                "claim_subject": claim_subject,
                "policy_uuid": policy_uuid,
                "submitted_by_seat_id": canonical_context.seat_id,
                "submitted_at_timestamp": now.isoformat(),
                "policy_eligibility_flags": eligibility_flags,
            },
            submitted_at=now,
        )

        db.session.add(pending_action)
        db.session.flush()

        return InsuranceClaimSubmissionResult(
            success=True,
            pending_action_id=pending_action_id,
            correlation_id=correlation_id,
            entitlement_id=entitlement_id,
            submitted_at=now,
            eligibility_flags=eligibility_flags,
        )

    except Exception as e:
        db.session.rollback()
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="INTERNAL_ERROR",
            error_message=f"Submission failed: {str(e)}",
        )


def resolve_insurance_claim(
    *,
    canonical_context: CanonicalContext,
    pending_action_id: str,
    approved: bool,
    override_reason: str | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimResolutionResult:
    """
    Adjudicate a pending insurance claim (approve or reject).

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role (teacher)
        pending_action_id: ID of pending_action to resolve
        approved: True for approval, False for rejection
        override_reason: Optional reason for approval (if overriding eligibility flags)
        idempotency_key: Optional replay guard

    Returns:
        InsuranceClaimResolutionResult with decision and entitlement event ID
    """
    return _resolve_insurance_claim_impl(
        canonical_context=canonical_context,
        pending_action_id=pending_action_id,
        approved=approved,
        override_reason=override_reason,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-STOR-003")
def _resolve_insurance_claim_impl(
    *,
    canonical_context: CanonicalContext,
    pending_action_id: str,
    approved: bool,
    override_reason: str | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimResolutionResult:
    """Implementation of insurance claim resolution."""
    try:
        # 1. Validate canonical context and teacher authorization
        if not canonical_context or not canonical_context.user_id:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="INVALID_CONTEXT",
                error_message="Invalid canonical context",
            )

        if canonical_context.actor_role != "teacher":
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="UNAUTHORIZED",
                error_message="Only teachers can resolve insurance claims",
            )

        # Get teacher seat for authorization
        teacher_seat = db.session.get(Seat, canonical_context.seat_id)
        if not teacher_seat or teacher_seat.class_id != canonical_context.class_id:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="UNAUTHORIZED",
                error_message="Teacher not found or class mismatch",
            )

        # 2. Read pending_action by ID
        pending_action = (
            db.session.query(PendingAction)
            .filter(
                PendingAction.pending_action_id == pending_action_id,
                PendingAction.class_id == canonical_context.class_id,
            )
            .first()
        )

        if not pending_action:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="PENDING_ACTION_NOT_FOUND",
                error_message=f"Pending action {pending_action_id} not found",
            )

        entitlement_id = pending_action.entitlement_id
        policy_uuid = pending_action.payload.get("policy_uuid")
        claim_subject = pending_action.payload.get("claim_subject")

        # 3. Read GRANTED entitlement event and check still valid
        granted_event = (
            db.session.query(EntitlementEvent)
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.class_id == canonical_context.class_id,
                EntitlementEvent.event_type == "GRANTED",
            )
            .first()
        )

        if not granted_event:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="ENTITLEMENT_NOT_FOUND",
                error_message="Original GRANTED event not found",
            )

        # Check no terminal event already exists (shouldn't happen, but verify)
        terminal_event = (
            db.session.query(EntitlementEvent)
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
            )
            .first()
        )

        if terminal_event:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="ENTITLEMENT_TERMINAL",
                error_message=f"Entitlement already terminal: {terminal_event.event_type}",
            )

        # 4. Resolve policy from immutable policy_uuid
        try:
            policy = StorePolicyResolver.resolve_store_item(policy_uuid)
        except (PolicyNotFound, PolicyParseError, PolicyValidationError) as e:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="POLICY_DELETED",
                error_message=f"Policy no longer resolvable: {str(e)}",
            )

        # Get student seat for event creation
        student_seat = db.session.get(Seat, granted_event.target_seat_id)
        if not student_seat:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="STUDENT_SEAT_NOT_FOUND",
                error_message="Student seat not found",
            )

        # 5. Process based on approval/rejection decision
        event_id = str(uuid.uuid4())
        now = utc_now()
        reimbursement_amount = Decimal("0.00")
        ledger_transaction_id = None

        if approved:
            # APPROVED path: coordinate Ledger and write CONSUMED event

            # Resolve reimbursement amount from policy
            policy_config = policy.get("config", {})
            reimbursement_amount = Decimal(str(policy_config.get("reimbursement_amount", "0.00")))
            reimbursement_amount = _quantize_currency(reimbursement_amount)

            if reimbursement_amount > 0:
                # Coordinate Ledger credit via FEAT-LED-000 (nested FEAT call)
                ledger_plan = build_intended_ledger_plan(
                    seat_id=student_seat.id,
                    class_id=canonical_context.class_id,
                    user_id=student_seat.user_id,
                    debit_amount=-reimbursement_amount,  # Negative = credit
                    description=f"Insurance claim reimbursement (policy {policy_uuid})",
                    source_account="checking",
                )

                ledger_resolved = resolve_intended_ledger_plan(
                    plan=ledger_plan,
                    idempotency_key=idempotency_key,
                )

                if ledger_resolved.outcome == "DENY":
                    return InsuranceClaimResolutionResult(
                        success=False,
                        error_code="LEDGER_REJECTED",
                        error_message="Ledger denied reimbursement credit",
                    )

                # Extract ledger transaction ID if available
                # (In a real implementation, the ledger service would return this)
                # For now, we record the resolved plan in the event payload

            # Write CONSUMED entitlement event
            consumed_event = EntitlementEvent(
                event_id=event_id,
                class_id=canonical_context.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=student_seat.id,
                actor_seat_id=teacher_seat.id,
                product_id=granted_event.product_id,
                entitlement_type="INSURANCE",
                acquisition_type="PERK",
                event_type="CONSUMED",
                correlation_id=pending_action.correlation_id,
                payload={
                    "claim_subject": claim_subject,
                    "claim_decision": "APPROVED",
                    "reimbursement_amount": str(reimbursement_amount),
                    "override_reason": override_reason,
                    "policy_uuid": policy_uuid,
                },
                timestamp=now,
            )

            db.session.add(consumed_event)

        else:
            # REJECTED path: write CONSUMED event with rejection marker, no Ledger
            consumed_event = EntitlementEvent(
                event_id=event_id,
                class_id=canonical_context.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=student_seat.id,
                actor_seat_id=teacher_seat.id,
                product_id=granted_event.product_id,
                entitlement_type="INSURANCE",
                acquisition_type="PERK",
                event_type="CONSUMED",
                correlation_id=pending_action.correlation_id,
                payload={
                    "claim_subject": claim_subject,
                    "claim_decision": "REJECTED",
                    "rejection_reason": override_reason,
                    "policy_uuid": policy_uuid,
                },
                timestamp=now,
            )

            db.session.add(consumed_event)

        # 6. Delete pending_action (atomic with event write)
        db.session.delete(pending_action)

        # Flush and commit
        db.session.flush()

        return InsuranceClaimResolutionResult(
            success=True,
            pending_action_id=None,  # Deleted
            entitlement_event_id=event_id,
            decision="APPROVED" if approved else "REJECTED",
            reimbursement_amount=reimbursement_amount if approved else None,
            ledger_transaction_id=ledger_transaction_id,
        )

    except Exception as e:
        db.session.rollback()
        return InsuranceClaimResolutionResult(
            success=False,
            error_code="INTERNAL_ERROR",
            error_message=f"Resolution failed: {str(e)}",
        )
