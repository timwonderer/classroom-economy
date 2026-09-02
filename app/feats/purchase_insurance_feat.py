"""
FEAT-OBL-004: Insurance Policy Purchase / Enrollment.

A student enters into (purchases) an insurance policy for the current class. The
user action is creating and immediately satisfying the FIRST premium obligation;
the INSURANCE entitlement grant is the consequence of successful satisfaction, not
the defining act — which is why this lives in the Obligations family, not Store.

Atomic success contract (one FEAT transaction; failure anywhere before commit
rolls back ALL of it, including the Ledger effect):

    resolve policy_uuid under class_id
      -> verify IN_USE
      -> reject same-policy concurrent coverage (POLICY_ALREADY_HELD)
      -> establish cycle-1 billing lineage (genesis) + record next boundary
      -> assess INSURANCE_PREMIUM for cycle 1
      -> satisfy it through the lawful Ledger path
      -> grant INSURANCE / PURCHASE entitlement (references policy_uuid; no snapshot)
      -> commit

policy_uuid IS the frozen contract: insurance_policies rows are immutable, so every
fact written here (assessment, entitlement, bill cycle) merely carries policy_uuid
and terms are retrieved later by resolving it. No terms are snapshotted.

Idempotency is COMMAND-owned. correlation_id embeds the idempotency_key, so a
replay of the SAME command is detected and returns the original result, while a
DIFFERENT command that finds active coverage for the same policy is rejected with
POLICY_ALREADY_HELD.

See docs/FEATURE-EXECUTION/FEAT-OBL-004_INSURANCE_POLICY_PURCHASE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import Seat, EntitlementEvent
from app.services import insurance_definition_service as insurance_defs
from app.services import ledger_service
from app.services import entitlement_service
from app.services import entitlement_read_service
from app.services.context_resolver import CanonicalContext
from app.feats.base import requires_feat_context, FEATContext
from app.feats.establish_bill_cycle_feat import execute_establish_bill_cycle
from app.feats.assess_obligation_feat import execute_assess_obligation
from app.feats.satisfy_obligation_feat import execute_satisfy_obligation_payment
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
)


@dataclass
class InsurancePurchaseResult:
    """Outcome of an insurance purchase (identity-blind, replay-safe)."""
    success: bool = False
    correlation_id: str | None = None
    entitlement_id: str | None = None
    transaction_id: int | None = None
    bill_cycle_id: int | None = None
    premium_charged: Decimal = Decimal("0.00")
    already_enrolled: bool = False  # this exact command already succeeded (idempotent replay)
    error_code: str | None = None
    error_message: str | None = None


def _next_premium_boundary(now_utc: datetime, charge_frequency: str) -> datetime:
    """Next recurring-premium boundary from the policy's charge cadence.

    INTERIM BINDING: DOM-POL does not yet designate a canonical cadence field, so
    this consumes the concrete `insurance_policies.charge_frequency` (WEEKLY |
    MONTHLY, DB-constrained). When DOM-POL fixes the cadence authority, bind to it
    here. Derivation is anchored on the canonically resolved `now_utc`
    (INV-ARC-015), not raw wall-clock arithmetic.
    """
    freq = (charge_frequency or "").upper()
    if freq == "WEEKLY":
        return now_utc + relativedelta(weeks=1)
    if freq == "MONTHLY":
        return now_utc + relativedelta(months=1)
    raise ValueError(f"unsupported insurance charge_frequency: {charge_frequency!r}")


@requires_feat_context("FEAT-OBL-004")
def execute_purchase_insurance(
    *,
    canonical_context: CanonicalContext,
    policy_uuid: str,
    idempotency_key: str,
) -> InsurancePurchaseResult:
    """Purchase (enroll in) an insurance policy for the acting student seat.

    Student self-purchase only: actor_seat_id == target_seat_id == context.seat_id.
    """
    if not policy_uuid:
        raise ValueError("execute_purchase_insurance requires a policy_uuid")
    if not idempotency_key:
        raise ValueError("execute_purchase_insurance requires an idempotency_key")

    class_id = canonical_context.class_id
    seat_id = canonical_context.seat_id
    if not class_id or not seat_id:
        return InsurancePurchaseResult(
            success=False, error_code="INVALID_CONTEXT",
            error_message="Canonical context lacks class_id/seat_id",
        )

    # One correlation ties the whole acquisition (assessment + payment + grant)
    # and embeds the command key so a same-command replay is detectable.
    correlation_id = f"insurance-purchase:{idempotency_key}"
    # Per-purchase recurring coverage lineage (unique per command, so a later
    # re-purchase after cancellation starts a fresh bill-cycle lineage).
    internal_ref = f"insurance:{seat_id}:{policy_uuid}:{idempotency_key}"

    # ----- Phase 1: read-only validation ----------------------------------- #

    # (0) Idempotent replay: this exact command already produced a grant.
    prior_grant = (
        EntitlementEvent.query
        .filter_by(
            class_id=class_id,
            target_seat_id=seat_id,
            entitlement_type="INSURANCE",
            event_type="GRANTED",
            correlation_id=correlation_id,
        )
        .first()
    )
    if prior_grant is not None:
        return InsurancePurchaseResult(
            success=True, already_enrolled=True,
            correlation_id=correlation_id,
            entitlement_id=prior_grant.entitlement_id,
        )

    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).first()
    if seat is None:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_SEAT", error_message="Seat not found in class scope",
        )

    definition = insurance_defs.get_insurance_definition(policy_uuid, class_id=class_id)
    if definition is None:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="POLICY_NOT_FOUND",
            error_message=f"Insurance policy {policy_uuid} not found in class {class_id}",
        )
    if definition.availability_state != insurance_defs.IN_USE:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INSURANCE_NOT_AVAILABLE_FOR_NEW_COVERAGE",
            error_message=(
                f"Insurance policy {policy_uuid} is not available for new coverage "
                f"(state={definition.availability_state})"
            ),
        )

    premium = Decimal(str(definition.premium))
    if premium <= Decimal("0.00"):
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INVALID_PREMIUM",
            error_message="Insurance premium resolves to a non-positive amount",
        )

    # Hard invariant: no second concurrently effective grant for the same policy.
    if entitlement_read_service.has_active_insurance_coverage(seat_id, class_id, policy_uuid):
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="POLICY_ALREADY_HELD",
            error_message="Seat already holds active coverage for this policy",
        )

    # Affordability: the first premium must be payable now (no overdraft here).
    available = ledger_service.get_available_balance(seat_id, class_id, "checking")
    if available < premium:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INSUFFICIENT_FUNDS",
            error_message=f"Checking balance {available} < premium {premium}",
        )

    # Resolve the recurring boundary in the read phase: a cadence we cannot
    # resolve aborts BEFORE any mutation (nothing written).
    now_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=SimpleNamespace(class_id=class_id),
        primitive="current_time",
    )
    now_utc = now_eval.canonical_now_utc
    try:
        next_assessment_at = _next_premium_boundary(now_utc, definition.charge_frequency)
    except ValueError as exc:
        return InsurancePurchaseResult(
            success=False, correlation_id=correlation_id,
            error_code="INVALID_CADENCE", error_message=str(exc),
        )

    # ----- Phase 2: mutation (single atomic FEAT transaction) --------------- #

    # (a) Genesis: establish cycle 1 for this coverage lineage, recording the
    #     next recurring-premium boundary. Cycle 1's assessment boundary is now
    #     (premium #1 due immediately); the next premium is due next_assessment_at.
    cycle = execute_establish_bill_cycle(
        class_id=class_id,
        internal_ref=internal_ref,
        cycle_boundary_at=now_utc,
        next_assessment_at=next_assessment_at,
        policy_uuid=policy_uuid,
    )

    # (b) Assess premium #1 against cycle 1.
    execute_assess_obligation(
        seat_id,
        class_id,
        internal_ref,
        correlation_id,
        "INSURANCE_PREMIUM",
        policy_uuid=policy_uuid,
        bill_cycle_id=cycle.id,
    )

    # (c) Post the premium debit through the canonical idempotent ledger path,
    #     then record the immutable PAYMENT satisfaction linked to that ledger row.
    authority_seat_id = ledger_service.resolve_class_authority_seat_id(class_id)
    transaction, _created = ledger_service.create_pending_transaction_idempotent(
        idempotency_key=f"insurance-premium:{idempotency_key}:cycle1",
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=authority_seat_id,
        actor_seat_id=seat_id,
        mechanism="self",
        user_id=seat.user_id,
        amount=-premium,
        account_type="checking",
        type="insurance_premium",
        description=f"Insurance premium (policy {policy_uuid}, cycle 1)",
    )
    execute_satisfy_obligation_payment(
        correlation_id,
        class_id,
        seat_id,
        transaction.id,
    )

    # (d) Grant the INSURANCE coverage entitlement (references policy_uuid).
    entitlement_id = entitlement_service.grant_insurance_entitlement(
        seat,
        policy_uuid,
        actor_seat_id=seat_id,
        correlation_id=correlation_id,
    )

    return InsurancePurchaseResult(
        success=True,
        correlation_id=correlation_id,
        entitlement_id=entitlement_id,
        transaction_id=transaction.id,
        bill_cycle_id=cycle.id,
        premium_charged=premium,
    )
