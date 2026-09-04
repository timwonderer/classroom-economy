"""
FEAT-OBL-001: Rent Payment.

Completes a rent obligation for one seat/cycle atomically, coordinating three
domains under a single FEAT transaction (INV-ARC-021):

  1. Ledger    — post the rent principal debit (canonical write path).
  2. Obligations — record the immutable PAYMENT satisfaction event linked to
                   that ledger transaction (via FEAT-OBL-003).
  3. Store     — grant the RentSettings ``satisfaction_benefits`` PERK
                 entitlements (hall passes) carrying the obligation's
                 correlation_id, so they can later be EXPIRED at the rent
                 boundary by reconciliation.

Idempotency is COMMAND-owned: each payment command carries an ``idempotency_key``
that identifies the individual payment request. The ledger write is keyed by that
command key, and the PAYMENT satisfaction event dedupes on the resulting ledger
transaction. A replay of the SAME command neither re-charges nor re-grants — it
returns the prior outcome. Two DISTINCT commands against the same obligation are
two lawful PARTIAL payments that both persist under the one correlation
("one obligation → one correlation → many PAYMENT events"). Idempotency is never
inferred by counting prior payments. Either a command commits fully or not at all.

Amount semantics: the assessed rent amount is resolved from the upstream policy
via ``assessment.policy_uuid`` (DOM-OBL-001 §V.1). A command may satisfy the full
remaining principal (``payment_amount=None``) or, when RentSettings enables
``allow_incremental_payment``, a partial slice of it. Paid-to-date is the sum of
PAYMENT ledger magnitudes; the obligation is satisfied once that sum reaches the
assessed principal. Satisfaction PERKs are granted exactly once, on the command
that transitions the obligation from underpaid to fully paid.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal

from app.models import ObligationAssessment, Seat, RentSettings
from app.services import obligations_service
from app.services import ledger_service
from app.services import entitlement_service
from app.services.class_configuration_query_service import get_rent_settings
from app.feats.base import requires_feat_context, FEATContext
from app.feats.satisfy_obligation_feat import satisfy_obligation, SatisfyObligationRequest


@dataclass
class RentPaymentResult:
    """Result of rent payment execution (identity-blind, replay-safe)."""
    success: bool = False
    correlation_id: str | None = None
    transaction_id: int | None = None
    amount_paid: Decimal = Decimal("0.00")  # amount settled by THIS command
    remaining_after: Decimal = Decimal("0.00")  # principal still outstanding after this command
    fully_paid: bool = False  # True iff the obligation is now fully satisfied
    passes_awarded: int = 0
    already_satisfied: bool = False  # obligation was already fully settled before this command
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class RentPaymentRequest:
    """Input contract for rent payment."""
    class_id: str
    seat_id: int
    correlation_id: str  # The specific rent obligation (seat + cycle) to satisfy
    idempotency_key: str  # Identifies THIS payment command; stable on replay
    payment_amount: Decimal | None = None  # None → pay full remaining principal


def _award_satisfaction_perks(settings: RentSettings, seat: Seat, correlation_id: str) -> int:
    """Grant the configured PERK hall-pass entitlements for a satisfied rent obligation."""
    grants = settings.get_satisfaction_benefit_grants()
    actor_seat_id = ledger_service.resolve_class_authority_seat_id(seat.class_id)
    awarded = 0
    for grant in grants:
        # Phase-1 closed schema guarantees entitlement_type == HALL_PASS.
        if grant["entitlement_type"] != "HALL_PASS":
            continue
        entitlement_service.grant_hall_passes(
            seat,
            grant["quantity"],
            actor_seat_id=actor_seat_id,
            correlation_id=correlation_id,
            acquisition_type="PERK",
            trigger_id=f"rent-perk:{correlation_id}",
        )
        awarded += grant["quantity"]
    return awarded


def pay_rent(
    request: RentPaymentRequest,
    *,
    context: FEATContext,
) -> RentPaymentResult:
    """Satisfy a single rent obligation atomically. Idempotent on replay."""
    class_id = request.class_id
    seat_id = request.seat_id
    correlation_id = request.correlation_id
    idempotency_key = request.idempotency_key

    if not class_id or not seat_id or not correlation_id:
        raise ValueError("pay_rent requires class_id, seat_id, and correlation_id")
    if not idempotency_key:
        raise ValueError("pay_rent requires a command idempotency_key")

    # Phase 1: Verification (read-only)
    assessment = obligations_service.get_assessment_for_correlation(correlation_id)
    if assessment is None:
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_ASSESSMENT",
            error_message=f"No rent assessment for correlation {correlation_id}",
        )
    # This FEAT settles rent-domain obligations: the RENT principal and the
    # LATE_FEE that arose from a delinquent rent. Both resolve their amount from
    # the same RentSettings policy; only RENT carries satisfaction PERKs.
    if assessment.obligation_type not in ("RENT", "LATE_FEE"):
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="NOT_RENT_DOMAIN",
            error_message=f"Obligation {correlation_id} is not a rent-domain obligation",
        )
    if assessment.class_id != class_id or assessment.seat_id != seat_id:
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="SCOPE_MISMATCH",
            error_message="Assessment does not belong to this seat/class",
        )

    # A waiver fully closes the obligation regardless of payment.
    if obligations_service.check_idempotency_satisfaction(correlation_id, "WAIVED"):
        return RentPaymentResult(
            success=True, correlation_id=correlation_id, already_satisfied=True,
            fully_paid=True,
        )

    seat = Seat.query.filter_by(id=seat_id, class_id=class_id).first()
    if seat is None:
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_SEAT", error_message="Seat not found in class scope",
        )

    # Resolve the policy THIS OBLIGATION WAS ASSESSED UNDER, not whatever is
    # current. Paying rent settles a liability the student already incurred, so
    # its terms — the incremental-payment allowance and the satisfaction perks —
    # come from the row the assessment froze (DOM-POL-001 §VII: an already-created
    # fact does not re-read the reference library). `rent_settings` is append-only,
    # so a teacher who edits rent between assessment and payment mints a new row;
    # reading the current one here would settle the old bill on the new contract.
    settings = None
    if assessment.policy_uuid:
        settings = RentSettings.query.filter_by(
            policy_uuid=assessment.policy_uuid
        ).first()
    if settings is None:
        # Pre-freeze assessments carry no policy_uuid; fall back to the class's
        # current policy so legacy obligations remain payable.
        settings = get_rent_settings(class_id)
    if settings is None:
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_SETTINGS", error_message="Rent settings not found",
        )

    assessed_amount = obligations_service.resolve_assessment_amount(assessment)
    if assessed_amount <= Decimal("0.00"):
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="ZERO_AMOUNT",
            error_message="Assessed rent amount resolves to zero",
        )

    # Paid-to-date is the sum of prior PAYMENT ledger magnitudes for this obligation.
    paid_before = obligations_service.get_paid_magnitude(correlation_id)
    remaining_before = assessed_amount - paid_before
    if remaining_before <= Decimal("0.00"):
        # Already fully satisfied by prior payments — no re-charge, no re-grant.
        return RentPaymentResult(
            success=True, correlation_id=correlation_id, already_satisfied=True,
            fully_paid=True, remaining_after=Decimal("0.00"),
        )

    # Resolve THIS command's payment amount.
    #   * None            → settle the full remaining principal.
    #   * >= remaining    → settle the remaining principal (never overpay).
    #   * < remaining     → lawful only when incremental payment is enabled.
    allow_incremental = bool(getattr(settings, "allow_incremental_payment", False))
    if request.payment_amount is None:
        this_payment = remaining_before
    else:
        requested = Decimal(str(request.payment_amount))
        if requested <= Decimal("0.00"):
            return RentPaymentResult(
                success=False, correlation_id=correlation_id,
                error_code="INVALID_AMOUNT",
                error_message="Payment amount must be positive",
            )
        if requested >= remaining_before:
            this_payment = remaining_before
        elif allow_incremental:
            this_payment = requested
        else:
            return RentPaymentResult(
                success=False, correlation_id=correlation_id,
                error_code="PARTIAL_NOT_ALLOWED",
                error_message="Partial rent payments are not enabled for this class",
            )

    # Affordability guard: no overdraft on the rent principal slice being paid now.
    available = ledger_service.get_available_balance(seat_id, class_id, "checking")
    if available < this_payment:
        return RentPaymentResult(
            success=False, correlation_id=correlation_id,
            error_code="INSUFFICIENT_FUNDS",
            error_message=f"Checking balance {available} < payment {this_payment}",
        )

    # Phase 2: Mutation (single atomic transaction owned by this FEAT)

    # (a) Post the rent principal debit via the canonical idempotent write path.
    #     The ledger key is COMMAND-owned (the payment request's idempotency_key),
    #     so a replay of the same command returns the same ledger row while a
    #     distinct command posts a distinct partial debit.
    authority_seat_id = ledger_service.resolve_class_authority_seat_id(class_id)
    transaction, _created = ledger_service.create_pending_transaction_idempotent(
        idempotency_key=f"rent-payment:{idempotency_key}:principal",
        seat_id=seat_id,
        class_id=class_id,
        target_seat_id=authority_seat_id,
        actor_seat_id=seat_id,
        mechanism="self",
        user_id=seat.user_id,
        amount=-this_payment,
        account_type="checking",
        type="rent_payment",
        description=(
            f"Late fee payment (obligation {correlation_id})"
            if assessment.obligation_type == "LATE_FEE"
            else f"Rent payment (cycle obligation {correlation_id})"
        ),
    )

    # (b) Record the immutable PAYMENT satisfaction linked to that ledger row.
    #     PAYMENT dedupes on ledger_transaction_id, so replaying the same command
    #     yields the same PAYMENT event; partial payments each get their own row
    #     while sharing this obligation's correlation. This is the Obligations
    #     DOMAIN command invoked in THIS FEAT's single context — never the
    #     FEAT-OBL-003 executor (INV-ARC-000 / -021 / -006).
    satisfy_obligation(
        SatisfyObligationRequest(
            correlation_id=correlation_id,
            class_id=class_id,
            seat_id=seat_id,
            method="PAYMENT",
            ledger_transaction_id=transaction.id,
        ),
        context=None,
    )

    # (c) Grant the configured PERK entitlements ONCE — only on the command that
    #     transitions the obligation from underpaid to fully paid.
    fully_paid = (paid_before + this_payment) >= assessed_amount
    newly_fully_paid = fully_paid and (paid_before < assessed_amount) and _created
    # Satisfaction PERKs are a RENT benefit only; settling a LATE_FEE grants none.
    passes_awarded = (
        _award_satisfaction_perks(settings, seat, correlation_id)
        if newly_fully_paid and assessment.obligation_type == "RENT" else 0
    )

    remaining_after = max(Decimal("0.00"), assessed_amount - (paid_before + this_payment))
    return RentPaymentResult(
        success=True,
        correlation_id=correlation_id,
        transaction_id=transaction.id,
        amount_paid=this_payment,
        remaining_after=remaining_after,
        fully_paid=fully_paid,
        passes_awarded=passes_awarded,
    )


@dataclass
class RentBillPaymentResult:
    """Outcome of settling a whole rent bill (rent principal + its late fees)."""
    success: bool = False
    rent_correlation_id: str | None = None
    amount_paid: Decimal = Decimal("0.00")  # total settled across the lineage by this command
    remaining_after: Decimal = Decimal("0.00")  # group balance still outstanding
    fully_paid: bool = False  # True iff the whole lineage is now satisfied
    passes_awarded: int = 0
    per_obligation: list = field(default_factory=list)  # RentPaymentResult per settled obligation
    error_code: str | None = None
    error_message: str | None = None


def _bill_obligations_in_order(class_id: str, seat_id: int, rent_correlation_id: str):
    """The bill's obligations, settlement order: rent principal, then its late
    fees oldest-first. Late fees are located via the lawful source_correlation_id
    reference (never by parsing a correlation string)."""
    rent = obligations_service.get_assessment_for_correlation(rent_correlation_id)
    ordered = []
    if rent is not None:
        ordered.append(rent)
    for fee in obligations_service.get_obligations_arising_from(rent_correlation_id):
        if fee.obligation_type == "LATE_FEE":
            ordered.append(fee)
    return ordered


def pay_rent_bill(
    class_id: str,
    seat_id: int,
    rent_correlation_id: str,
    *,
    idempotency_key: str,
    payment_amount: Decimal | None,
    context: FEATContext,
) -> RentBillPaymentResult:
    """Settle a rent bill as ONE lineage: the rent principal and the late fees
    that arose from it. From the student's perspective this is a single bill;
    mechanically each obligation keeps its own correlation and its own immutable
    PAYMENT events. Satisfaction is defined over the whole lineage — the bill is
    settled once every obligation under it is covered.

    A payment is applied rent-principal-first, then late fees oldest-first. Each
    slice is a per-obligation command whose key is derived from this command's
    key and the obligation's correlation (stable on replay, distinct per
    obligation) — never a counted sequence. ``payment_amount=None`` settles the
    full group balance; a smaller amount is a partial bill payment (lawful only
    when the class enables incremental payment).
    """
    obligations = _bill_obligations_in_order(class_id, seat_id, rent_correlation_id)
    if not obligations:
        return RentBillPaymentResult(
            success=False, rent_correlation_id=rent_correlation_id,
            error_code="NO_ASSESSMENT",
            error_message=f"No rent bill for correlation {rent_correlation_id}",
        )

    # Remaining balance per obligation, in settlement order.
    slices = []
    group_remaining = Decimal("0.00")
    for ob in obligations:
        assessed = obligations_service.resolve_assessment_amount(ob)
        paid = obligations_service.get_paid_magnitude(ob.correlation_id)
        remaining = assessed - paid
        if remaining < Decimal("0.00"):
            remaining = Decimal("0.00")
        slices.append((ob, remaining))
        group_remaining += remaining

    if group_remaining <= Decimal("0.00"):
        return RentBillPaymentResult(
            success=True, rent_correlation_id=rent_correlation_id,
            fully_paid=True, remaining_after=Decimal("0.00"),
        )

    if payment_amount is None:
        budget = group_remaining
    else:
        budget = Decimal(str(payment_amount))
        if budget <= Decimal("0.00"):
            return RentBillPaymentResult(
                success=False, rent_correlation_id=rent_correlation_id,
                error_code="INVALID_AMOUNT", error_message="Payment amount must be positive",
            )
        if budget > group_remaining:
            budget = group_remaining

    # Allocate the budget across obligations in order (rent first, then late fees).
    results: list[RentPaymentResult] = []
    total_paid = Decimal("0.00")
    passes = 0
    remaining_budget = budget
    for ob, remaining in slices:
        if remaining_budget <= Decimal("0.00"):
            break
        if remaining <= Decimal("0.00"):
            continue
        slice_amount = remaining if remaining <= remaining_budget else remaining_budget
        # Per-obligation command key: a FIXED-LENGTH digest of (bill command key,
        # obligation correlation). Command-owned and stable on replay (a pure
        # function of stable inputs), distinct per obligation, and never a counted
        # sequence. Hashing keeps the downstream ledger key within its length
        # bound regardless of how long the correlations are.
        sub_key = "billpay:" + hashlib.sha256(
            f"{idempotency_key}:{ob.correlation_id}".encode()
        ).hexdigest()[:24]
        sub = pay_rent(
            RentPaymentRequest(
                class_id=class_id,
                seat_id=seat_id,
                correlation_id=ob.correlation_id,
                idempotency_key=sub_key,
                payment_amount=slice_amount,
            ),
            context=context,
        )
        results.append(sub)
        if not sub.success:
            return RentBillPaymentResult(
                success=False, rent_correlation_id=rent_correlation_id,
                error_code=sub.error_code, error_message=sub.error_message,
                per_obligation=results,
            )
        total_paid += sub.amount_paid
        passes += sub.passes_awarded
        remaining_budget -= sub.amount_paid

    remaining_after = max(Decimal("0.00"), group_remaining - total_paid)
    return RentBillPaymentResult(
        success=True,
        rent_correlation_id=rent_correlation_id,
        amount_paid=total_paid,
        remaining_after=remaining_after,
        fully_paid=remaining_after <= Decimal("0.00"),
        passes_awarded=passes,
        per_obligation=results,
    )


@requires_feat_context("FEAT-OBL-001")
def execute_rent_bill_payment(
    class_id: str,
    seat_id: int,
    rent_correlation_id: str,
    *,
    idempotency_key: str,
    payment_amount: Decimal | None = None,
) -> RentBillPaymentResult:
    """Public FEAT interface: settle a rent bill (rent principal + its late fees)
    as one lineage, atomically and idempotently. See ``pay_rent_bill``."""
    return pay_rent_bill(
        class_id, seat_id, rent_correlation_id,
        idempotency_key=idempotency_key,
        payment_amount=payment_amount,
        context=None,
    )


@requires_feat_context("FEAT-OBL-001")
def execute_rent_payment(
    class_id: str,
    seat_id: int,
    correlation_id: str,
    *,
    idempotency_key: str,
    payment_amount: Decimal | None = None,
) -> RentPaymentResult:
    """Public FEAT interface for rent payment.

    Callable from the student rent route and from tests.

    Args:
        class_id, seat_id: canonical scope of the obligation.
        correlation_id: the specific rent obligation (seat + cycle) to satisfy.
        idempotency_key: identifies THIS payment command and is stable on replay.
            It keys the ledger write, so replaying the same command returns the
            same outcome while a distinct command posts a distinct partial debit.
            ``requires_feat_context`` also binds it to the FEAT context.
        payment_amount: None settles the full remaining principal; a smaller value
            is a partial payment (lawful only when the class enables incremental
            payment). Records the PAYMENT event and grants satisfaction PERKs on
            the transition to fully paid — all atomically.
    """
    request = RentPaymentRequest(
        class_id=class_id,
        seat_id=seat_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payment_amount=payment_amount,
    )
    return pay_rent(request, context=None)
