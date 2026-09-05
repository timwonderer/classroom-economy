"""
FEAT-STOR-003: Insurance Claim Lifecycle (v2.0)

Orchestrates the complete insurance claim lifecycle on the first-class
``InsuranceClaim`` entity (DOM-STORE-001):

- Submission: resolve the immutable insurance policy governing the entitlement,
  create/idempotently return an ``InsuranceClaim(status=SUBMITTED)``. The
  entitlement is NOT consumed.
- Resolution: teacher adjudication transitions the claim SUBMITTED → APPROVED /
  REJECTED. Approval coordinates exactly one compensatory Ledger effect.

Lifecycle authority lives on ``InsuranceClaim``, never on an ``EntitlementEvent``:
filing or deciding a claim does NOT write a ``CONSUMED`` event. The insurance
entitlement stays ``GRANTED`` until its real coverage boundary, so multiple claims
may be filed under one active policy. Terminal claim decisions are immutable, and
at most one claim lifecycle may back a given source transaction.

Claim eligibility and economics come from the **immutable insurance policy**
(``insurance_policies``), resolved via the GRANTED entitlement's ``policy_uuid``
(``_resolve_claim_policy``). Because a policy edit produces a *new* ``policy_uuid``,
the exact row referenced by the entitlement is the frozen contract — there is no
separate snapshot. The entitlement proves acquisition; the policy provides the
terms (INV-ARC-009). No claim runtime reads any copied ``frozen_contract`` payload.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional
from datetime import date, datetime, timedelta
import uuid

from app.extensions import db
from app.feats.base import requires_feat_context, get_correlation_id
from app.models import Seat, EntitlementEvent, Transaction
from app.services.context_resolver import CanonicalContext
from app.services import ledger_service
from app.services import insurance_claim_service
from app.services import insurance_eligibility_contract as eligibility
from app.services import insurance_definition_service as insurance_defs


class InsuranceClaimPolicyError(Exception):
    """The immutable insurance policy backing a claim could not be resolved.

    Raised (fail-closed) when a claimed insurance entitlement lacks a `policy_uuid`
    reference, or that `policy_uuid` does not resolve to a policy in the claim's
    class boundary. Claim authority is the immutable `insurance_policies` row — the
    entitlement proves acquisition, the policy provides the terms.
    """


def _resolve_claim_policy(entitlement_id, *, class_id, seat_id):
    """Resolve the immutable insurance policy that governs a claimed entitlement.

    The GRANTED insurance entitlement carries the `policy_uuid` of the exact
    immutable definition purchased; that row is the sole claim-time authority for
    coverage terms, ceilings, reimbursement, and claim limits. Terms are NEVER
    read from the entitlement payload (no snapshot) — the entitlement proves
    acquisition, the policy provides the terms (INV-ARC-009).

    Fails closed: a missing grant, a missing `policy_uuid`, or a policy that does
    not exist in this class (wrong-class resolution returns None) raises.
    """
    grant = (
        EntitlementEvent.query
        .filter_by(
            entitlement_id=entitlement_id,
            class_id=class_id,
            target_seat_id=seat_id,
            entitlement_type="INSURANCE",
            event_type="GRANTED",
        )
        .first()
    )
    if grant is None:
        raise InsuranceClaimPolicyError(
            f"No INSURANCE grant for entitlement {entitlement_id} in class {class_id}"
        )
    policy_uuid = (grant.payload or {}).get("policy_uuid")
    if not policy_uuid:
        raise InsuranceClaimPolicyError(
            f"Entitlement {entitlement_id} carries no policy_uuid reference"
        )
    policy = insurance_defs.get_insurance_definition(policy_uuid, class_id=class_id)
    if policy is None:
        raise InsuranceClaimPolicyError(
            f"Insurance policy {policy_uuid} not found in class {class_id}"
        )
    return policy
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    ensure_utc,
)
from app.models import _quantize_currency, PayrollSettings, PolicyVersion, ClassEconomy
from app.services.economic_engine import require_ready_base, EconomicEngineNotReady
from app.services.attendance_service import (
    calculate_worked_attendance_seconds_for_date,
)
from app.payroll import get_daily_limit_seconds

_TRANSACTION_INSURANCE_TYPE = "TRANSACTION"
_PRODUCTIVITY_INSURANCE_TYPE = "PRODUCTIVITY"


@dataclass
class _CoverageTerms:
    """Derived (never stored) economic terms for one entitlement coverage cycle.

    Reconstructed purely from the policy_terms contract snapshot plus the GRANTED
    event's timestamp — the current InsurancePolicy is never re-read. Absent
    renewal machinery in CTH, an INSURANCE entitlement has exactly ONE coverage
    period beginning at its grant, so period-scoped sums/counts span the whole
    entitlement lineage. When renewal events are introduced, re-scope to
    ``[period_start, next_renewal)``.
    """

    coverage_start_utc: datetime
    coverage_week_equivalent: Decimal
    period_claim_allowance: int
    maximum_policy_payout: Decimal


def _add_one_calendar_month(d: date) -> date:
    """Class-local calendar-month step, clamping the day to the target month end."""
    if d.month == 12:
        year, month = d.year + 1, 1
    else:
        year, month = d.year, d.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _class_local_date(canonical_context: CanonicalContext, ts_utc: datetime) -> date:
    """Class-local (CLE) calendar date of a UTC instant."""
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="current_evaluation_day",
        reference_time_utc=ensure_utc(ts_utc),
    )
    return evaluation.evaluation_date


def _filing_deadline_end_utc(
    canonical_context: CanonicalContext,
    transaction_ts_utc: datetime,
    claim_window_days: int,
) -> datetime:
    """UTC instant at the END of class-local date ``D + N`` (inclusive filing).

    A transaction on class-local date ``D`` with ``claim_window_days = N`` may be
    filed through the end of class-local date ``D + N`` (calendar-day semantics,
    NOT 7×24h). The returned instant is the exclusive upper bound: a submission is
    timely iff ``submitted_at < deadline_end_utc``.
    """
    txn_date = _class_local_date(canonical_context, transaction_ts_utc)
    deadline_date = txn_date + timedelta(days=int(claim_window_days))
    boundaries = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="evaluation_day_boundaries",
        evaluation_date=deadline_date,
    )
    return boundaries.boundary_end_utc


def _coverage_week_equivalent(
    *,
    policy_terms,
    coverage_start_utc: datetime,
    canonical_context: CanonicalContext,
) -> Decimal:
    """Scale the weekly cadence to the coverage period's length.

    A weekly cycle is exactly ``1`` week-equivalent; a monthly cycle is
    ``covered_days / 7`` measured in class-local calendar days. Shared by every
    product type (TRANSACTION claim-count, PRODUCTIVITY date-count) so the period
    scaling stays identical across the policy_terms subsets.
    """
    freq = (policy_terms.charge_frequency or "WEEKLY").strip().upper()
    if freq == "MONTHLY":
        start_date = _class_local_date(canonical_context, coverage_start_utc)
        next_renewal = _add_one_calendar_month(start_date)
        covered_days = (next_renewal - start_date).days
        return Decimal(covered_days) / Decimal("7")
    # Weekly coverage (and any fail-safe) is exactly one week-equivalent.
    return Decimal("1")


def _maximum_policy_payout(policy_terms) -> Decimal:
    """Period payout ceiling: policy_terms premium × policy_terms payout multiple.

    Identical for every monetary product — the period payout capacity is the
    premium actually charged for one coverage cycle times the policy_terms multiple.
    """
    premium = policy_terms.premium or Decimal("0.00")
    payout_multiple = policy_terms.payout_multiple or Decimal("0")
    return _quantize_currency(premium * payout_multiple)


def _derive_coverage_terms(
    *,
    policy_terms,
    granted_event: EntitlementEvent,
    canonical_context: CanonicalContext,
) -> _CoverageTerms:
    """Reconstruct the coverage-cycle economics from the policy_terms snapshot."""
    coverage_start_utc = ensure_utc(granted_event.timestamp)
    week_equiv = _coverage_week_equivalent(
        policy_terms=policy_terms,
        coverage_start_utc=coverage_start_utc,
        canonical_context=canonical_context,
    )

    maximum_policy_payout = _maximum_policy_payout(policy_terms)

    claims_per_week = policy_terms.claims_per_week_equivalent or Decimal("0")
    period_claim_allowance = int(math.ceil(claims_per_week * week_equiv))

    return _CoverageTerms(
        coverage_start_utc=coverage_start_utc,
        coverage_week_equivalent=week_equiv,
        period_claim_allowance=period_claim_allowance,
        maximum_policy_payout=maximum_policy_payout,
    )


def _sum_approved_payouts(class_id: str, entitlement_id: str) -> Decimal:
    """Σ of APPROVED result_amounts under one entitlement coverage period."""
    approved = insurance_claim_service.list_claims_for_entitlement(
        class_id=class_id,
        entitlement_id=entitlement_id,
        statuses=[insurance_claim_service.APPROVED],
    )
    total = Decimal("0.00")
    for claim in approved:
        if claim.result_amount is not None:
            total += claim.result_amount
    return _quantize_currency(total)


def _enforce_transaction_submission(
    *,
    canonical_context: CanonicalContext,
    policy_terms,
    granted_event: EntitlementEvent,
    claim_subject: dict,
    submitted_at: datetime,
    replay_key: str,
) -> Optional["InsuranceClaimSubmissionResult"]:
    """Gate a TRANSACTION claim at submission.

    Order (SPEC): eligible transaction → within filing window → claim allowance
    available → period payout capacity available. Returns a failure result on the
    first failed gate, or ``None`` when the claim may be created. All enforcement
    reads the policy_terms contract and immutable claim history — never the live policy.
    """
    entitlement_id = granted_event.entitlement_id
    class_id = canonical_context.class_id
    seat_id = canonical_context.seat_id

    transaction_id = claim_subject.get("transaction_id")
    if transaction_id is None:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="INVALID_CLAIM_SUBJECT",
            error_message="TRANSACTION insurance claims require a transaction_id",
        )

    source_transaction = db.session.get(Transaction, transaction_id)

    # (a) System-law eligibility of the source transaction.
    verdict = eligibility.evaluate_transaction_claim_basis(
        source_transaction, class_id=class_id, covered_seat_id=seat_id
    )
    if not verdict.eligible:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="INELIGIBLE_TRANSACTION",
            error_message=f"{verdict.reason_code}: {verdict.detail}",
        )

    coverage_terms = _derive_coverage_terms(
        policy_terms=policy_terms, granted_event=granted_event, canonical_context=canonical_context
    )

    # (b) Coverage interval + filing window (class-local calendar days).
    source_ts_utc = ensure_utc(source_transaction.timestamp)
    if source_ts_utc < coverage_terms.coverage_start_utc:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="TRANSACTION_OUTSIDE_COVERAGE",
            error_message="Source transaction predates the purchased coverage",
        )
    deadline_end_utc = _filing_deadline_end_utc(
        canonical_context, source_ts_utc, policy_terms.claim_window_days
    )
    if ensure_utc(submitted_at) >= deadline_end_utc:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="CLAIM_WINDOW_EXCEEDED",
            error_message="Filing window for this transaction has closed",
        )

    # (c) Claim-allowance — count EVERY claim lifecycle (SUBMITTED+APPROVED+REJECTED)
    #     under this coverage period. Serialize concurrent submissions on the
    #     GRANTED row so two cannot both take the last slot.
    db.session.query(EntitlementEvent).filter(
        EntitlementEvent.event_id == granted_event.event_id
    ).with_for_update().first()

    existing = insurance_claim_service.list_claims_for_entitlement(
        class_id=class_id,
        entitlement_id=entitlement_id,
        target_seat_id=seat_id,
    )
    # A same-correlation replay is the same lifecycle, not an additional draw.
    consumed = sum(1 for claim in existing if claim.correlation_id != replay_key)
    if consumed >= coverage_terms.period_claim_allowance:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="CLAIM_LIMIT_EXCEEDED",
            error_message=(
                f"Claim allowance exhausted "
                f"({consumed}/{coverage_terms.period_claim_allowance} for this period)"
            ),
        )

    # (d) Period payout capacity — only APPROVED payouts consume it.
    remaining = coverage_terms.maximum_policy_payout - _sum_approved_payouts(
        class_id, entitlement_id
    )
    if remaining <= Decimal("0.00"):
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="CLAIM_ALLOWANCE_EXHAUSTED",
            error_message="No remaining period payout capacity",
        )

    return None


@dataclass
class _ProductivityClaimedDate:
    """One parsed, validated asserted loss-date from a PRODUCTIVITY submission."""

    claim_date: date
    student_claimed_hours: Decimal
    # Required student-authored evidence for this date. Never fabricated, never
    # derived — it is the student's own account of the asserted loss.
    student_explanation: str


def _parse_productivity_dates(
    claim_subject: dict,
    *,
    canonical_context: CanonicalContext,
    coverage_start_utc: datetime,
    submitted_at: datetime,
) -> tuple[list[_ProductivityClaimedDate], Optional["InsuranceClaimSubmissionResult"]]:
    """Parse and validate ``claimed_dates`` from a PRODUCTIVITY claim subject.

    Expected shape::

        {
          "claimed_dates": [
            {"date": "YYYY-MM-DD", "hours": "2.0", "explanation": "..."}, ...
          ],
          "additional_information": "optional claim-wide free text"
        }

    Each asserted date must be a real class-local calendar date that is not before
    the coverage start and not in the future (class-local), with strictly positive
    hours **and** a required non-empty ``explanation`` (the student's own account of
    the loss — evidentiary, never fabricated). The claim-wide
    ``additional_information`` is optional; when present it must be a string and is
    persisted as-is on ``InsuranceClaim.claim_basis`` (no parent column).
    PRODUCTIVITY has **no** filing window (the policy_terms contract intentionally omits
    ``claim_window_days``), so past dates within coverage never expire. Returns
    ``(parsed_dates, None)`` on success or ``([], failure_result)`` on the first
    malformed/ineligible entry. Duplicate dates within one submission are rejected.
    """
    raw_dates = claim_subject.get("claimed_dates")
    if not isinstance(raw_dates, list) or not raw_dates:
        return [], InsuranceClaimSubmissionResult(
            success=False,
            error_code="INVALID_CLAIM_BASIS",
            error_message="PRODUCTIVITY claims require a non-empty claimed_dates list",
        )

    # Optional claim-wide additional information (Option 1: lives in claim_basis
    # JSON, no parent column). Validate type only; empty/absent is allowed.
    additional_information = claim_subject.get("additional_information")
    if additional_information is not None and not isinstance(additional_information, str):
        return [], InsuranceClaimSubmissionResult(
            success=False,
            error_code="INVALID_CLAIM_BASIS",
            error_message="additional_information must be a string when provided",
        )

    coverage_start_date = _class_local_date(canonical_context, coverage_start_utc)
    today_local = _class_local_date(canonical_context, ensure_utc(submitted_at))

    parsed: list[_ProductivityClaimedDate] = []
    seen: set[date] = set()
    for entry in raw_dates:
        if not isinstance(entry, dict):
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message="Each claimed_dates entry must be an object",
            )
        raw_date = entry.get("date")
        try:
            claim_date = date.fromisoformat(str(raw_date))
        except (ValueError, TypeError):
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message=f"Invalid claimed date {raw_date!r} (expected YYYY-MM-DD)",
            )

        if claim_date in seen:
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message=f"Duplicate claimed date {claim_date.isoformat()} in submission",
            )
        seen.add(claim_date)

        if claim_date < coverage_start_date:
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="PRODUCTIVITY_DATE_NOT_ELIGIBLE",
                error_message=f"Date {claim_date.isoformat()} predates the purchased coverage",
            )
        if claim_date > today_local:
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="PRODUCTIVITY_DATE_NOT_ELIGIBLE",
                error_message=f"Date {claim_date.isoformat()} is in the future",
            )

        try:
            hours = Decimal(str(entry.get("hours")))
        except (InvalidOperation, TypeError, ValueError):
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message=f"Invalid hours for date {claim_date.isoformat()}",
            )
        if hours <= Decimal("0"):
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message=f"Hours for date {claim_date.isoformat()} must be positive",
            )

        raw_explanation = entry.get("explanation")
        explanation = raw_explanation.strip() if isinstance(raw_explanation, str) else ""
        if not explanation:
            return [], InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_BASIS",
                error_message=(
                    f"A short explanation is required for date {claim_date.isoformat()}"
                ),
            )

        parsed.append(
            _ProductivityClaimedDate(
                claim_date=claim_date,
                student_claimed_hours=hours,
                student_explanation=explanation,
            )
        )

    parsed.sort(key=lambda d: d.claim_date)
    return parsed, None


def _enforce_productivity_submission(
    *,
    canonical_context: CanonicalContext,
    policy_terms,
    granted_event: EntitlementEvent,
    parsed_dates: list["_ProductivityClaimedDate"],
) -> tuple[Optional["InsuranceClaimSubmissionResult"], dict]:
    """Gate a PRODUCTIVITY claim's asserted dates against the two-resource rule.

    Resource 1 (date-count allowance): the number of *distinct class-local dates*
    that may be claimed in the period is
    ``ceil(policy_terms.claimable_dates_per_week_equivalent × week_equivalent)``. The
    metered unit for PRODUCTIVITY is the DATE, not the claim case. Already-claimed
    distinct dates (any status, from immutable child-row history) plus the new
    dates must not exceed the allowance.

    Resource 2 (period payout capacity): ``premium × payout_multiple`` minus the Σ
    of persisted ``recognized_payout``; zero remaining fails the submission.

    ``expected_weekly_hours`` is **not** an authorization limit — it is economic
    normalization plus advisory guidance. This gate therefore never rejects a claim
    for exceeding it; instead it computes an *advisory* weekly-guidance flag set
    (derived, non-authoritative) that is surfaced to the student at submission and
    the teacher at review. The daily limit (when configured) remains a real hard
    boundary.

    Concurrent submissions serialize on the GRANTED row so two cannot both take the
    last date slot; the ``UNIQUE(entitlement_id, claim_date)`` constraint is the
    structural backstop.

    Returns ``(failure_or_None, advisory_flags)``. ``advisory_flags`` is always a
    dict (possibly with an empty warning list); it is only meaningful when the
    failure is ``None``.
    """
    class_id = canonical_context.class_id
    entitlement_id = granted_event.entitlement_id
    seat_id = canonical_context.seat_id

    # (0) Economic Engine readiness. PRODUCTIVITY economics are defined off the CWI
    #     base (expected_weekly_hours × pay rate). The feature-enablement boundary
    #     already refuses to enable insurance for an unready class; this execution
    #     check is defense in depth so a migrated/corrupt enabled-but-unready class
    #     still fails closed rather than operating on a NULL base input.
    try:
        base = require_ready_base(class_id)
    except EconomicEngineNotReady as exc:
        return (
            InsuranceClaimSubmissionResult(
                success=False,
                error_code="ECONOMIC_ENGINE_NOT_READY",
                error_message=exc.reason,
            ),
            {},
        )

    week_equiv = _coverage_week_equivalent(
        policy_terms=policy_terms,
        coverage_start_utc=ensure_utc(granted_event.timestamp),
        canonical_context=canonical_context,
    )
    dates_per_week = policy_terms.claimable_dates_per_week_equivalent or Decimal("0")
    date_allowance = int(math.ceil(dates_per_week * week_equiv))

    # Serialize concurrent date draws on the GRANTED entitlement row.
    db.session.query(EntitlementEvent).filter(
        EntitlementEvent.event_id == granted_event.event_id
    ).with_for_update().first()

    existing_rows = insurance_claim_service.list_productivity_dates_for_entitlement(
        class_id=class_id, entitlement_id=entitlement_id
    )
    existing_dates = {row.claim_date for row in existing_rows}
    new_dates = {d.claim_date for d in parsed_dates}
    # A same-date replay is not an additional draw; only genuinely new dates count.
    prospective = len(existing_dates | new_dates)
    if prospective > date_allowance:
        return (
            InsuranceClaimSubmissionResult(
                success=False,
                error_code="CLAIM_ALLOWANCE_EXHAUSTED",
                error_message=(
                    f"Date allowance exhausted "
                    f"({prospective}/{date_allowance} distinct dates for this period)"
                ),
            ),
            {},
        )

    remaining = _maximum_policy_payout(policy_terms) - (
        insurance_claim_service.sum_recognized_payout_for_entitlement(
            class_id=class_id, entitlement_id=entitlement_id
        )
    )
    if remaining <= Decimal("0.00"):
        return (
            InsuranceClaimSubmissionResult(
                success=False,
                error_code="CLAIM_ALLOWANCE_EXHAUSTED",
                error_message="No remaining period payout capacity",
            ),
            {},
        )

    # (Req 3) Per-date daily capacity. A claimed loss cannot exceed the class's
    # remaining daily productivity capacity after time actually worked. Only
    # applies when a daily limit is configured; absent a cap, no per-day limit is
    # invented for PRODUCTIVITY. This IS a hard boundary.
    daily_failure = _enforce_productivity_daily_capacity(
        canonical_context=canonical_context,
        seat_id=seat_id,
        class_id=class_id,
        parsed_dates=parsed_dates,
    )
    if daily_failure is not None:
        return daily_failure, {}

    # Advisory (NOT a gate): aggregate weekly guidance. expected_weekly_hours is
    # economic normalization + guidance, so exceeding it never blocks a claim. We
    # compute a derived, non-authoritative flag set comparing
    # (actual_worked_week + claimed_week) against expected_weekly_hours per canonical
    # week, surfaced to the student now and the teacher at review.
    advisory_flags = _compute_productivity_weekly_advisory(
        canonical_context=canonical_context,
        seat_id=seat_id,
        class_id=class_id,
        entitlement_id=entitlement_id,
        parsed_dates=parsed_dates,
        expected_weekly_hours=base.expected_weekly_hours,
    )
    return None, advisory_flags


def _week_start(day: date) -> date:
    """Monday-anchored week bucket, matching the canonical period resolver."""
    return day - timedelta(days=day.weekday())


def _projected_weekly_hours_for_status(row) -> Decimal:
    """State-sensitive weekly contribution of a persisted PRODUCTIVITY date.

    SUBMITTED counts the student-claimed hours; APPROVED counts the teacher-approved
    hours (defaulting to student-claimed when no explicit adjustment was recorded);
    REJECTED contributes nothing to the weekly-hours projection (it still consumes
    its date, but frees weekly-hours capacity).
    """
    if row.status == insurance_claim_service.SUBMITTED:
        return row.student_claimed_hours or Decimal("0")
    if row.status == insurance_claim_service.APPROVED:
        approved = row.teacher_approved_hours
        if approved is None:
            approved = row.student_claimed_hours
        return approved or Decimal("0")
    return Decimal("0")


def _enforce_productivity_daily_capacity(
    *,
    canonical_context: CanonicalContext,
    seat_id: int,
    class_id: str,
    parsed_dates: list["_ProductivityClaimedDate"],
) -> Optional["InsuranceClaimSubmissionResult"]:
    """Req 3: claimed loss-time ≤ remaining daily capacity after time worked.

    The daily limit is the canonical ``get_daily_limit_seconds`` authority, keyed by
    the class ``section`` (block). When no limit is configured the resolver returns
    ``None`` and PRODUCTIVITY imposes no per-day ceiling. The worked duration is an
    authoritative attendance read for the exact class-local date — PRODUCTIVITY
    never interprets AttendanceSession rows itself.
    """
    class_row = db.session.get(ClassEconomy, class_id)
    block = class_row.section if class_row is not None else None
    daily_cap_seconds = get_daily_limit_seconds(block, class_id=class_id)
    if daily_cap_seconds is None:
        return None

    for claimed in parsed_dates:
        worked_seconds = calculate_worked_attendance_seconds_for_date(
            seat_id, class_id, claimed.claim_date, ctx=canonical_context
        )
        remaining_seconds = max(0, daily_cap_seconds - worked_seconds)
        claimed_seconds = claimed.student_claimed_hours * Decimal("3600")
        if claimed_seconds > Decimal(remaining_seconds):
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="PRODUCTIVITY_DAILY_LIMIT_EXCEEDED",
                error_message=(
                    f"Claimed hours for {claimed.claim_date.isoformat()} exceed the "
                    f"remaining daily capacity after time worked"
                ),
            )
    return None


def _compute_productivity_weekly_advisory(
    *,
    canonical_context: CanonicalContext,
    seat_id: int,
    class_id: str,
    entitlement_id: str,
    parsed_dates: list["_ProductivityClaimedDate"],
    expected_weekly_hours: Decimal,
) -> dict:
    """Derive an ADVISORY (non-authoritative) weekly-guidance flag set.

    This never gates a submission — ``expected_weekly_hours`` is economic
    normalization plus guidance, not an authorization limit. For each canonical
    (Monday-anchored) week touched by the submission we compute the aggregate

        actual_worked_week + claimed_week

    and compare it with ``expected_weekly_hours`` (per the settled model, the
    guidance comparison is aggregate — worked hours PLUS claimed hours, not a
    remaining-capacity subtraction). ``claimed_week`` sums the existing persisted
    claimed/approved contribution for that week (per lifecycle status) plus the new
    genuinely-added dates in this submission. ``actual_worked_week`` sums
    authoritative attendance across the seven class-local days of the week.

    The returned dict is derived state only — the caller surfaces it in
    ``eligibility_flags`` but MUST NOT persist it as eligibility truth. Shape::

        {
          "expected_weekly_hours": "40.00",
          "weekly_guidance_exceeded": bool,
          "weekly_guidance_warnings": [
            {"week_start": "YYYY-MM-DD",
             "worked_hours": "...",
             "claimed_hours": "...",
             "projected_hours": "...",
             "expected_weekly_hours": "..."},
            ...
          ],
        }
    """
    existing = insurance_claim_service.list_productivity_dates_with_status_for_entitlement(
        class_id=class_id, entitlement_id=entitlement_id
    )
    existing_dates = {row.claim_date for row in existing}

    claimed_by_week: dict[date, Decimal] = {}
    for row in existing:
        wk = _week_start(row.claim_date)
        claimed_by_week[wk] = (
            claimed_by_week.get(wk, Decimal("0"))
            + _projected_weekly_hours_for_status(row)
        )
    for claimed in parsed_dates:
        if claimed.claim_date in existing_dates:
            continue  # replay of an already-persisted date; already counted above
        wk = _week_start(claimed.claim_date)
        claimed_by_week[wk] = (
            claimed_by_week.get(wk, Decimal("0")) + claimed.student_claimed_hours
        )

    # Restrict advisory to weeks this submission actually touches.
    touched_weeks = {_week_start(d.claim_date) for d in parsed_dates}

    warnings: list[dict] = []
    for wk in sorted(touched_weeks):
        worked_seconds = 0
        for offset in range(7):
            day = wk + timedelta(days=offset)
            worked_seconds += calculate_worked_attendance_seconds_for_date(
                seat_id, class_id, day, ctx=canonical_context
            )
        worked_hours = (Decimal(worked_seconds) / Decimal("3600")).quantize(Decimal("0.01"))
        claimed_hours = claimed_by_week.get(wk, Decimal("0"))
        projected = worked_hours + claimed_hours
        if projected > expected_weekly_hours:
            warnings.append(
                {
                    "week_start": wk.isoformat(),
                    "worked_hours": str(worked_hours),
                    "claimed_hours": str(claimed_hours),
                    "projected_hours": str(projected),
                    "expected_weekly_hours": str(expected_weekly_hours),
                }
            )

    return {
        "expected_weekly_hours": str(expected_weekly_hours),
        "weekly_guidance_exceeded": bool(warnings),
        "weekly_guidance_warnings": warnings,
    }


class InsuranceClaimError(Exception):
    """Raised when insurance claim validation or execution fails."""
    pass


@dataclass
class InsuranceClaimSubmissionResult:
    """Result of a successful insurance claim submission."""
    success: bool
    claim_id: Optional[str] = None
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
    claim_id: Optional[str] = None
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
        InsuranceClaimSubmissionResult with claim_id or error
    """
    return _submit_insurance_claim_impl(
        canonical_context=canonical_context,
        entitlement_id=entitlement_id,
        claim_subject=claim_subject,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-STOR-003")
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

        # 3. Resolve the immutable insurance policy that governs this entitlement.
        #    Claim eligibility/economics come from the policy definition (the
        #    entitlement's policy_uuid), never from a payload snapshot. Fails
        #    closed on a missing/unresolvable policy.
        try:
            policy_terms = _resolve_claim_policy(
                entitlement_id,
                class_id=canonical_context.class_id,
                seat_id=canonical_context.seat_id,
            )
        except InsuranceClaimPolicyError as e:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="POLICY_UNRESOLVABLE",
                error_message=str(e),
            )

        # Temporal anchor for submission (class-local).
        temporal_context = canonical_temporal_resolver(
            CLASS_LEVEL_EVALUATION,
            canonical_execution_context=canonical_context,
            primitive="current_time",
        )

        if not temporal_context:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="TEMPORAL_CONTEXT_ERROR",
                error_message="Cannot determine temporal context",
            )
        now = temporal_context.canonical_now_utc

        # 4. Validate claim subject structure
        if not isinstance(claim_subject, dict):
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="INVALID_CLAIM_SUBJECT",
                error_message="Claim subject must be a dictionary",
            )

        replay_key = correlation_id or idempotency_key or f"corr_{uuid.uuid4().hex}"

        # 5. One transaction may back at most one claim lifecycle. A replay under the
        #    SAME correlation is not a duplicate (create_claim returns the prior claim).
        subject_transaction_id = claim_subject.get("transaction_id")
        if subject_transaction_id is not None:
            existing_claims = insurance_claim_service.list_claims_for_entitlement(
                class_id=canonical_context.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=canonical_context.seat_id,
            )
            for prior in existing_claims:
                if prior.correlation_id == replay_key:
                    continue  # idempotent replay; handled by create_claim below
                if (prior.claim_basis or {}).get("transaction_id") == subject_transaction_id:
                    return InsuranceClaimSubmissionResult(
                        success=False,
                        error_code="DUPLICATE_CLAIM_SUBJECT",
                        error_message=(
                            f"Transaction {subject_transaction_id} already backs "
                            f"claim {prior.claim_id}"
                        ),
                    )

        # 6. TRANSACTION economics + eligibility (Step 6). Enforced against the
        #    policy_terms contract and immutable claim history — never the live policy.
        eligibility_flags = {
            "count_limit_exceeded": False,
            "period_limit_exceeded": False,
            "claim_window_exceeded": False,
        }

        parsed_productivity_dates: list[_ProductivityClaimedDate] = []

        if policy_terms.insurance_type == _TRANSACTION_INSURANCE_TYPE:
            enforcement = _enforce_transaction_submission(
                canonical_context=canonical_context,
                policy_terms=policy_terms,
                granted_event=granted_event,
                claim_subject=claim_subject,
                submitted_at=now,
                replay_key=replay_key,
            )
            if enforcement is not None:
                return enforcement
        elif policy_terms.insurance_type == _PRODUCTIVITY_INSURANCE_TYPE:
            # PRODUCTIVITY: the claim asserts one or more class-local loss-dates.
            # Parse/validate the dates, then gate them against the two-resource rule
            # (date-count allowance + period payout capacity). No filing window.
            parsed_productivity_dates, parse_failure = _parse_productivity_dates(
                claim_subject,
                canonical_context=canonical_context,
                coverage_start_utc=ensure_utc(granted_event.timestamp),
                submitted_at=now,
            )
            if parse_failure is not None:
                return parse_failure
            enforcement, advisory_flags = _enforce_productivity_submission(
                canonical_context=canonical_context,
                policy_terms=policy_terms,
                granted_event=granted_event,
                parsed_dates=parsed_productivity_dates,
            )
            if enforcement is not None:
                return enforcement
            # Advisory weekly guidance is derived, non-authoritative state. It is
            # surfaced to the student now (and the teacher at review) but is NOT
            # persisted as eligibility truth.
            eligibility_flags.update(advisory_flags)

        # 7. Create (or idempotently return) the SUBMITTED claim. The entitlement is
        #    NOT consumed — it stays GRANTED so further claims may be filed.
        try:
            claim = insurance_claim_service.create_claim(
                class_id=canonical_context.class_id,
                entitlement_id=entitlement_id,
                target_seat_id=canonical_context.seat_id,
                actor_seat_id=canonical_context.seat_id,
                correlation_id=replay_key,
                claim_basis=claim_subject,
                submitted_at=now,
            )
        except insurance_claim_service.ClaimIdempotencyConflict as e:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="IDEMPOTENCY_CONFLICT",
                error_message=str(e),
            )
        except insurance_claim_service.ClaimEntitlementInvalid as e:
            return InsuranceClaimSubmissionResult(
                success=False,
                error_code="ENTITLEMENT_INVALID",
                error_message=str(e),
            )

        # 7b. Attach normalized PRODUCTIVITY date rows (immutable submitted hours).
        #     Idempotent on replay; the UNIQUE(entitlement_id, claim_date) invariant
        #     is the structural backstop against a concurrent duplicate date.
        if policy_terms.insurance_type == _PRODUCTIVITY_INSURANCE_TYPE:
            try:
                insurance_claim_service.add_productivity_claim_dates(
                    claim=claim,
                    dates=[
                        (d.claim_date, d.student_claimed_hours, d.student_explanation)
                        for d in parsed_productivity_dates
                    ],
                )
            except insurance_claim_service.ProductivityDateConflict as e:
                return InsuranceClaimSubmissionResult(
                    success=False,
                    error_code="PRODUCTIVITY_DATE_NOT_ELIGIBLE",
                    error_message=str(e),
                )

        return InsuranceClaimSubmissionResult(
            success=True,
            claim_id=claim.claim_id,
            correlation_id=claim.correlation_id,
            entitlement_id=entitlement_id,
            submitted_at=claim.submitted_at,
            eligibility_flags=eligibility_flags,
        )

    except Exception as e:
        return InsuranceClaimSubmissionResult(
            success=False,
            error_code="INTERNAL_ERROR",
            error_message=f"Submission failed: {str(e)}",
        )


def _resolve_hourly_pay_rate(class_id: str) -> Decimal:
    """Class-global hourly pay rate ($/hour) from active PayrollSettings.

    ``PayrollSettings.pay_rate`` is stored per-minute; the hourly wage is ×60. This
    is a *payroll fact* read at adjudication time — the resulting per-date
    ``recognized_payout`` is then persisted immutably, so a later rate change never
    retroactively re-values a settled PRODUCTIVITY claim.
    """
    setting = (
        PayrollSettings.query.filter(
            PayrollSettings.class_id == class_id,
            PayrollSettings.availability_state == 'IN_USE',
            PayrollSettings.block.is_(None),
        )
        .order_by(PayrollSettings.updated_at.desc(), PayrollSettings.id.desc())
        .first()
    )
    per_minute = Decimal(setting.pay_rate) if (setting and setting.pay_rate) else Decimal("0.25")
    return per_minute * Decimal("60")


@dataclass
class ProductivityDateReview:
    """Read-only per-date review context for a PRODUCTIVITY claim.

    All fields are pure reads. ``student_explanation`` is the student's immutable
    submitted evidence. ``worked_week_seconds``, ``expected_weekly_hours`` and
    ``guidance_exceeded`` are DERIVED advisory guidance (aggregate
    ``worked_week + claimed_week`` vs ``expected_weekly_hours``) — never an
    authorization limit and never persisted. ``teacher_approved_hours`` /
    ``adjustment_note`` echo any prior adjudication (NULL while SUBMITTED).
    """

    claim_date: date
    student_claimed_hours: Decimal
    student_explanation: str
    already_worked_seconds: int
    worked_week_seconds: int
    claimed_week_hours: Decimal
    expected_weekly_hours: Optional[Decimal]
    guidance_exceeded: bool
    teacher_approved_hours: Optional[Decimal]
    adjustment_note: Optional[str]


@dataclass
class ProductivityReviewContext:
    """Full teacher-review context for a PRODUCTIVITY claim.

    ``additional_information`` is the optional claim-wide free text the student
    supplied (lives in ``InsuranceClaim.claim_basis``; Option 1, no parent column).
    ``dates`` is the ordered per-date review list. ``guidance_exceeded`` is the
    claim-level roll-up of the per-week advisory (True iff any touched week's
    ``worked_week + claimed_week`` exceeds ``expected_weekly_hours``).
    """

    additional_information: Optional[str]
    expected_weekly_hours: Optional[Decimal]
    guidance_exceeded: bool
    dates: list["ProductivityDateReview"]


def build_productivity_review_context(
    claim, *, canonical_context: CanonicalContext
) -> "ProductivityReviewContext":
    """Surface teacher-review context for a SUBMITTED PRODUCTIVITY claim.

    Pairs each asserted date's immutable student-claimed hours and required
    explanation with the authoritative worked duration for that class-local date,
    plus a DERIVED aggregate weekly-guidance signal (``worked_week + claimed_week``
    vs ``expected_weekly_hours``). The guidance is advisory only — it never gates
    approval. This is a pure read: it performs no adjudication and writes nothing
    (stops well before MANUAL_CREDIT).
    """
    class_id = canonical_context.class_id
    seat_id = claim.target_seat_id

    # expected_weekly_hours is the CWI normalization base; when the engine is not
    # ready we still render the review without guidance rather than failing.
    try:
        expected_weekly_hours = require_ready_base(class_id).expected_weekly_hours
    except EconomicEngineNotReady:
        expected_weekly_hours = None

    rows = insurance_claim_service.list_productivity_dates_for_claim(
        claim.claim_id, class_id=class_id
    )

    # Cache worked-seconds per canonical week (7-day sum) so multiple dates in the
    # same week don't re-read attendance.
    worked_week_cache: dict[date, int] = {}

    def _worked_week_seconds(wk: date) -> int:
        if wk not in worked_week_cache:
            total = 0
            for offset in range(7):
                total += calculate_worked_attendance_seconds_for_date(
                    seat_id, class_id, wk + timedelta(days=offset), ctx=canonical_context
                )
            worked_week_cache[wk] = total
        return worked_week_cache[wk]

    # Claimed hours per week within THIS claim (student-claimed).
    claimed_week: dict[date, Decimal] = {}
    for row in rows:
        wk = _week_start(row.claim_date)
        claimed_week[wk] = claimed_week.get(wk, Decimal("0")) + (
            row.student_claimed_hours or Decimal("0")
        )

    review: list[ProductivityDateReview] = []
    any_exceeded = False
    for row in rows:
        wk = _week_start(row.claim_date)
        worked_seconds = calculate_worked_attendance_seconds_for_date(
            seat_id, class_id, row.claim_date, ctx=canonical_context
        )
        worked_week_seconds = _worked_week_seconds(wk)
        claimed_week_hours = claimed_week.get(wk, Decimal("0"))
        guidance_exceeded = False
        if expected_weekly_hours is not None:
            worked_week_hours = Decimal(worked_week_seconds) / Decimal("3600")
            guidance_exceeded = (
                worked_week_hours + claimed_week_hours > expected_weekly_hours
            )
        any_exceeded = any_exceeded or guidance_exceeded
        review.append(
            ProductivityDateReview(
                claim_date=row.claim_date,
                student_claimed_hours=row.student_claimed_hours,
                student_explanation=row.student_explanation,
                already_worked_seconds=worked_seconds,
                worked_week_seconds=worked_week_seconds,
                claimed_week_hours=claimed_week_hours,
                expected_weekly_hours=expected_weekly_hours,
                guidance_exceeded=guidance_exceeded,
                teacher_approved_hours=row.teacher_approved_hours,
                adjustment_note=row.adjustment_note,
            )
        )

    additional_information = (claim.claim_basis or {}).get("additional_information")
    return ProductivityReviewContext(
        additional_information=additional_information,
        expected_weekly_hours=expected_weekly_hours,
        guidance_exceeded=any_exceeded,
        dates=review,
    )


def _approve_productivity_claim(
    *,
    canonical_context: CanonicalContext,
    claim,
    policy_terms,
    teacher_seat,
    override_reason: str | None,
    date_adjustments: dict | None,
    idempotency_key: str | None,
) -> InsuranceClaimResolutionResult:
    """Approve a PRODUCTIVITY claim: adjudicate each date, then one MANUAL_CREDIT.

    Per-date ``recognized_payout`` = ``approved_hours × hourly_rate ×
    reimbursement_percentage / 100``, clamped cumulatively (dates ascending) to the
    remaining period payout capacity (``premium × payout_multiple`` minus the Σ of
    ``recognized_payout`` already persisted under this entitlement). Teacher
    adjustments (``date_adjustments``) may lower a date's hours, but every adjusted
    date requires its own note (enforced by the service). The single compensatory
    monetary effect is posted through Productivity & Payroll (FEAT-PROD-003) as a
    ``manual_credit`` — Store never writes the payroll event or Ledger directly.
    """
    class_id = canonical_context.class_id
    entitlement_id = claim.entitlement_id

    if policy_terms.reimbursement_percentage is None:
        return InsuranceClaimResolutionResult(
            success=False,
            error_code="CLAIM_TYPE_UNSUPPORTED",
            error_message="PRODUCTIVITY contract carries no reimbursement_percentage",
        )

    rows = insurance_claim_service.list_productivity_dates_for_claim(
        claim.claim_id, class_id=class_id
    )
    if not rows:
        return InsuranceClaimResolutionResult(
            success=False,
            error_code="INVALID_CLAIM_BASIS",
            error_message="PRODUCTIVITY claim has no asserted date rows",
        )

    hourly_rate = _resolve_hourly_pay_rate(class_id)
    adjustments = date_adjustments or {}

    # Remaining period payout capacity BEFORE this claim's dates are recognized.
    remaining = _maximum_policy_payout(policy_terms) - (
        insurance_claim_service.sum_recognized_payout_for_entitlement(
            class_id=class_id, entitlement_id=entitlement_id
        )
    )
    if remaining <= Decimal("0.00"):
        return InsuranceClaimResolutionResult(
            success=False,
            error_code="CLAIM_ALLOWANCE_EXHAUSTED",
            error_message="No remaining period payout capacity",
        )

    # ── Phase A — validate + compute in memory (NO writes) ───────────────────
    # Every adjudication rule is checked here, before any money moves and before
    # any adjudication row is persisted. A downward-only breach or a missing note
    # aborts with nothing written, so the claim stays SUBMITTED and its date rows
    # keep NULL adjudication fields. The submission-time daily-cap eligibility is
    # NOT recomputed here — a lawfully filed claim is not retroactively invalidated
    # by later attendance; worked-duration reads are teacher context only.
    adjudications: dict = {}
    total_recognized = Decimal("0.00")
    for row in rows:  # rows are ascending by claim_date
        adj = adjustments.get(row.claim_date.isoformat(), {})
        approved_raw = adj.get("hours")
        approved_hours = (
            row.student_claimed_hours if approved_raw is None else Decimal(str(approved_raw))
        )
        note = adj.get("note")

        if approved_hours < Decimal("0"):
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="INVALID_ADJUDICATION",
                error_message=f"Adjusted hours for {row.claim_date.isoformat()} are negative",
            )
        # Downward-only: the teacher recognizes at most what the student asserted.
        # Enlarging a claim beyond the immutable submitted hours is rejected (never
        # silently clamped — clamping would blur teacher intent and make the audit
        # record ambiguous).
        if approved_hours > row.student_claimed_hours:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="ADJUSTMENT_EXCEEDS_CLAIM",
                error_message=(
                    f"Approved hours ({approved_hours}) for {row.claim_date.isoformat()} "
                    f"exceed the student's claimed hours ({row.student_claimed_hours}); "
                    f"teacher adjudication is downward-only"
                ),
            )
        # A downward adjustment requires an explicit per-date note so the reduction
        # is auditable.
        if approved_hours != row.student_claimed_hours and not (note and note.strip()):
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="ADJUSTMENT_NOTE_REQUIRED",
                error_message=(
                    f"Date {row.claim_date.isoformat()}: approved hours "
                    f"({approved_hours}) differ from claimed "
                    f"({row.student_claimed_hours}) but no adjustment note was provided"
                ),
            )

        gross = _quantize_currency(
            approved_hours * hourly_rate * policy_terms.reimbursement_percentage / Decimal("100")
        )
        recognized = _quantize_currency(min(gross, remaining))
        if recognized < Decimal("0.00"):
            recognized = Decimal("0.00")
        remaining -= recognized
        total_recognized += recognized

        adjudications[row.claim_date] = {
            "teacher_approved_hours": approved_hours,
            "adjustment_note": note,
            "recognized_payout": recognized,
        }

    total_recognized = _quantize_currency(total_recognized)

    # ── Phase B — monetary effect FIRST ──────────────────────────────────────
    # One compensatory MANUAL_CREDIT through Productivity & Payroll (never direct).
    # If it fails, we return BEFORE persisting any adjudication row and BEFORE the
    # claim leaves SUBMITTED. The FEAT transaction then commits nothing about this
    # approval: no teacher_approved_hours, no recognized_payout, no payroll/ledger
    # lineage. The entire approval unit is atomic, not merely the status field.
    payroll_event_id = None
    if total_recognized > Decimal("0.00"):
        payroll_version = (
            PolicyVersion.query.filter_by(
                class_id=class_id, domain="payroll", is_active=True
            ).first()
        )
        if payroll_version is None:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="PAYROLL_COMPENSATION_FAILED",
                error_message="No active payroll policy version to post MANUAL_CREDIT",
            )
        # Nested FEAT-PROD-003 shares this thread's correlation (atomicity guard).
        active_correlation = get_correlation_id()
        from app.feats.prod import _record_payroll_event_impl as record_payroll_event_command

        try:
            payroll_result = record_payroll_event_command(
                ctx=canonical_context,
                target_seat_id=claim.target_seat_id,
                payroll_event_type="manual_credit",
                correlation_id=active_correlation,
                idempotency_key=(
                    idempotency_key or f"FEAT-STOR-003:productivity-credit:{claim.claim_id}"
                ),
                policy_version_id=payroll_version.id,
                mechanism="system",
                amount=total_recognized,
                summary_json={
                    "description": (
                        f"Productivity insurance payout for claim {claim.claim_id}"
                    ),
                    "insurance_claim_id": claim.claim_id,
                    "entitlement_id": entitlement_id,
                },
            )
        except Exception as e:  # payroll/ledger coordination failure
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="PAYROLL_COMPENSATION_FAILED",
                error_message=f"MANUAL_CREDIT posting failed: {e}",
            )
        payroll_event_id = payroll_result.payroll_event.id

    # ── Phase C — persist adjudication + terminal APPROVED transition ─────────
    # Reached only after the money is posted. The service re-validates the
    # downward-only + note rules as defense in depth; because Phase A already
    # enforced them the persistence cannot fail on those grounds, so there is no
    # money-without-APPROVED window either.
    insurance_claim_service.adjudicate_productivity_claim_dates(
        claim_id=claim.claim_id,
        class_id=class_id,
        adjudications=adjudications,
    )

    insurance_claim_service.decide_claim(
        claim_id=claim.claim_id,
        class_id=class_id,
        decided_by_seat_id=teacher_seat.id,
        approved=True,
        decision_note=override_reason,
        result_amount=total_recognized,
        payroll_event_id=payroll_event_id,
    )

    db.session.flush()
    return InsuranceClaimResolutionResult(
        success=True,
        claim_id=claim.claim_id,
        decision="APPROVED",
        reimbursement_amount=total_recognized,
        ledger_transaction_id=None,
    )


def resolve_insurance_claim(
    *,
    canonical_context: CanonicalContext,
    claim_id: str,
    approved: bool,
    override_reason: str | None = None,
    date_adjustments: dict | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimResolutionResult:
    """
    Adjudicate a SUBMITTED insurance claim (approve or reject).

    Transitions the ``InsuranceClaim`` SUBMITTED → APPROVED / REJECTED. The
    insurance entitlement is NEVER consumed — no ``CONSUMED`` EntitlementEvent is
    written, and the entitlement stays ``GRANTED``. Approval coordinates exactly
    one compensatory monetary effect, whose id is recorded on the claim lineage
    (a Ledger transaction for TRANSACTION, a Payroll MANUAL_CREDIT for PRODUCTIVITY).

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role (teacher)
        claim_id: ID of the InsuranceClaim to adjudicate
        approved: True for approval, False for rejection
        override_reason: Optional decision note (recorded on the claim)
        date_adjustments: PRODUCTIVITY-only per-date teacher adjustments, keyed by
            ISO date string → {"hours": Decimal, "note": str}. A date whose approved
            hours differ from the submitted hours REQUIRES a note.
        idempotency_key: Optional replay guard for the compensatory effect

    Returns:
        InsuranceClaimResolutionResult with claim_id, decision, and lineage refs
    """
    return _resolve_insurance_claim_impl(
        canonical_context=canonical_context,
        claim_id=claim_id,
        approved=approved,
        override_reason=override_reason,
        date_adjustments=date_adjustments,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-STOR-003")
def _resolve_insurance_claim_impl(
    *,
    canonical_context: CanonicalContext,
    claim_id: str,
    approved: bool,
    override_reason: str | None = None,
    date_adjustments: dict | None = None,
    idempotency_key: str | None = None,
) -> InsuranceClaimResolutionResult:
    """Implementation of insurance claim resolution on the InsuranceClaim lifecycle."""
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

        # 2. Load the class-scoped claim. Lifecycle authority lives on InsuranceClaim.
        claim = insurance_claim_service.get_claim(
            claim_id, class_id=canonical_context.class_id
        )
        if claim is None:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="CLAIM_NOT_FOUND",
                error_message=f"Insurance claim {claim_id} not found",
            )

        # Terminal decisions are immutable — fail before any Ledger effect.
        if claim.status != insurance_claim_service.SUBMITTED:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="ALREADY_DECIDED",
                error_message=(
                    f"Claim {claim_id} is already terminal ({claim.status}); "
                    f"decisions are immutable"
                ),
            )

        entitlement_id = claim.entitlement_id
        claim_subject = claim.claim_basis or {}

        # 3. Resolve the immutable insurance policy governing this entitlement.
        #    Claim economics come from the policy definition, never a snapshot.
        try:
            policy_terms = _resolve_claim_policy(
                entitlement_id,
                class_id=canonical_context.class_id,
                seat_id=claim.target_seat_id,
            )
        except InsuranceClaimPolicyError as e:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="POLICY_UNRESOLVABLE",
                error_message=f"Insurance policy unresolvable: {e}",
            )
        insurance_policy_uuid = policy_terms.policy_uuid  # provenance

        # Get student seat for the compensatory Ledger effect.
        student_seat = db.session.get(Seat, claim.target_seat_id)
        if not student_seat:
            return InsuranceClaimResolutionResult(
                success=False,
                error_code="STUDENT_SEAT_NOT_FOUND",
                error_message="Student seat not found",
            )

        reimbursement_amount = Decimal("0.00")
        ledger_transaction_id = None

        if approved and policy_terms.insurance_type == _PRODUCTIVITY_INSURANCE_TYPE:
            # PRODUCTIVITY approval is date-metered: adjudicate each asserted loss
            # date, persist its immutable recognized_payout, and post ONE
            # MANUAL_CREDIT through Productivity & Payroll. No source transaction,
            # no direct Ledger effect.
            return _approve_productivity_claim(
                canonical_context=canonical_context,
                claim=claim,
                policy_terms=policy_terms,
                teacher_seat=teacher_seat,
                override_reason=override_reason,
                date_adjustments=date_adjustments,
                idempotency_key=idempotency_key,
            )

        if approved:
            # APPROVED path: derive reimbursement from the source transaction and
            # write exactly one compensatory Ledger effect. NO CONSUMED event.
            transaction_id = claim_subject.get("transaction_id")
            if transaction_id is None:
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="INVALID_CLAIM_SUBJECT",
                    error_message="Approved insurance claims require transaction_id",
                )

            source_transaction = db.session.get(Transaction, transaction_id)
            if not source_transaction or source_transaction.class_id != canonical_context.class_id:
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="INVALID_CLAIM_SUBJECT",
                    error_message="Claim transaction not found in this class",
                )

            # Reimbursement economics are read ONLY from the policy_terms snapshot. Monetary
            # products (TRANSACTION / PRODUCTIVITY) carry a reimbursement_percentage; the
            # loss is reimbursed at that policy_terms rate.
            if (policy_terms.insurance_type not in (_TRANSACTION_INSURANCE_TYPE, _PRODUCTIVITY_INSURANCE_TYPE)
                    or policy_terms.reimbursement_percentage is None):
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="CLAIM_TYPE_UNSUPPORTED",
                    error_message=(
                        f"Monetary reimbursement is not yet supported for "
                        f"insurance_type {policy_terms.insurance_type}"
                    ),
                )

            # Revalidate the transaction's structural eligibility at decision time —
            # facts may have changed post-submission (e.g. a linked item was revoked).
            verdict = eligibility.evaluate_transaction_claim_basis(
                source_transaction,
                class_id=canonical_context.class_id,
                covered_seat_id=claim.target_seat_id,
            )
            if not verdict.eligible:
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="INELIGIBLE_TRANSACTION",
                    error_message=f"{verdict.reason_code}: {verdict.detail}",
                )

            gross_loss = abs(source_transaction.amount or Decimal("0.00"))
            gross_reimbursement = _quantize_currency(
                gross_loss * policy_terms.reimbursement_percentage / Decimal("100")
            )
            if gross_reimbursement <= Decimal("0.00"):
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="INVALID_CLAIM_SUBJECT",
                    error_message="Claim transaction has no reimbursable amount",
                )

            reimbursement_amount = gross_reimbursement
            if policy_terms.insurance_type == _TRANSACTION_INSURANCE_TYPE:
                # CLAMP to remaining period capacity: maximum_policy_payout
                # (policy_terms premium × payout_multiple) minus Σ prior APPROVED payouts.
                # Exceeding the nominal reimbursement never invalidates a claim — the
                # policy pays only its remaining capacity. Zero capacity fails as
                # CLAIM_ALLOWANCE_EXHAUSTED rather than a zero-dollar approval. Later
                # submissions never retroactively deny an earlier claim.
                granted_event = (
                    db.session.query(EntitlementEvent)
                    .filter(
                        EntitlementEvent.entitlement_id == entitlement_id,
                        EntitlementEvent.class_id == canonical_context.class_id,
                        EntitlementEvent.event_type == "GRANTED",
                        EntitlementEvent.target_seat_id == claim.target_seat_id,
                    )
                    .first()
                )
                if granted_event is None:
                    return InsuranceClaimResolutionResult(
                        success=False,
                        error_code="ENTITLEMENT_INVALID",
                        error_message="GRANTED entitlement not found for this claim",
                    )
                coverage_terms = _derive_coverage_terms(
                    policy_terms=policy_terms,
                    granted_event=granted_event,
                    canonical_context=canonical_context,
                )
                remaining_period_payout = (
                    coverage_terms.maximum_policy_payout
                    - _sum_approved_payouts(canonical_context.class_id, entitlement_id)
                )
                if remaining_period_payout <= Decimal("0.00"):
                    return InsuranceClaimResolutionResult(
                        success=False,
                        error_code="CLAIM_ALLOWANCE_EXHAUSTED",
                        error_message="No remaining period payout capacity",
                    )
                reimbursement_amount = _quantize_currency(
                    min(gross_reimbursement, remaining_period_payout)
                )

            ledger_transaction, created = ledger_service.create_pending_transaction_idempotent(
                idempotency_key=idempotency_key or f"insurance-reimbursement:{claim_id}",
                seat_id=student_seat.id,
                class_id=canonical_context.class_id,
                target_seat_id=student_seat.id,
                actor_seat_id=teacher_seat.id,
                mechanism="system",
                user_id=student_seat.user_id,
                amount=reimbursement_amount,
                account_type="checking",
                type="insurance_reimbursement",
                description=f"Insurance reimbursement for transaction {transaction_id} (policy {insurance_policy_uuid})",
                original_transaction_id=source_transaction.id,
            )
            ledger_transaction_id = ledger_transaction.id

            # Transition the claim to APPROVED, recording the Ledger lineage.
            try:
                insurance_claim_service.decide_claim(
                    claim_id=claim_id,
                    class_id=canonical_context.class_id,
                    decided_by_seat_id=teacher_seat.id,
                    approved=True,
                    decision_note=override_reason,
                    result_amount=reimbursement_amount,
                    ledger_transaction_id=ledger_transaction_id,
                )
            except insurance_claim_service.ClaimAlreadyDecided as e:
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="ALREADY_DECIDED",
                    error_message=str(e),
                )

        else:
            # REJECTED path: transition the claim, no Ledger effect. NO CONSUMED event.
            try:
                insurance_claim_service.decide_claim(
                    claim_id=claim_id,
                    class_id=canonical_context.class_id,
                    decided_by_seat_id=teacher_seat.id,
                    approved=False,
                    decision_note=override_reason,
                )
            except insurance_claim_service.ClaimAlreadyDecided as e:
                return InsuranceClaimResolutionResult(
                    success=False,
                    error_code="ALREADY_DECIDED",
                    error_message=str(e),
                )

        db.session.flush()

        return InsuranceClaimResolutionResult(
            success=True,
            claim_id=claim_id,
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
