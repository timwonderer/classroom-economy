"""Store & Entitlements-owned insurance-claim persistence contracts.

This module is the canonical authority for the *existence, status, basis, and
decision* of an insurance claim (DOM-STORE-001 / FEAT-STOR-003). It owns the
``InsuranceClaim`` lifecycle: ``SUBMITTED → APPROVED/REJECTED``.

Design invariants (see FEAT-STOR-003 §XII / §XVII):

* A claim is correlated to an insurance entitlement lineage but is NEVER
  represented by an ``EntitlementEvent``. Creating or deciding a claim does
  **not** write a ``CONSUMED`` event — the entitlement stays ``GRANTED`` so
  multiple claims may be filed under one active policy.
* Terminal decisions are immutable: only a ``SUBMITTED`` claim may transition.
* No mutable counters. Allowance / weekly-payout / period-payout figures are
  derived by *reading* claim history (a later step), never stored as counters.
* The claim records only product-specific submitted facts. Frozen policy terms
  live in the entitlement/policy lineage, not on the claim.

These functions perform ORM mutations and therefore MUST be invoked inside an
active FEAT context (enforced by ``app.feats.base``). They are the domain layer
composed by FEAT orchestrators, not a public route surface.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from typing import Iterable, Optional
import uuid

from app.extensions import db
from app.models import (
    EntitlementEvent,
    InsuranceClaim,
    InsuranceClaimProductivityDate,
)
from app.utils.canonical_temporal_resolver import utc_now


# Canonical claim lifecycle states.
SUBMITTED = "SUBMITTED"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
TERMINAL_STATES = frozenset({APPROVED, REJECTED})

_INSURANCE_ENTITLEMENT_TYPE = "INSURANCE"
_TERMINAL_ENTITLEMENT_EVENTS = ("CONSUMED", "EXPIRED", "REVOKED")


class InsuranceClaimServiceError(Exception):
    """Base error for the insurance-claim persistence contract."""


class ClaimEntitlementInvalid(InsuranceClaimServiceError):
    """The referenced entitlement lineage is missing, wrong-type, or terminal."""


class ClaimIdempotencyConflict(InsuranceClaimServiceError):
    """The correlation_id already exists for a different claim context."""


class ClaimNotFound(InsuranceClaimServiceError):
    """No claim exists for the given (claim_id, class_id)."""


class ClaimAlreadyDecided(InsuranceClaimServiceError):
    """Attempted to decide a claim that is already in a terminal state."""


class ProductivityDateConflict(InsuranceClaimServiceError):
    """A class-local date already participates in a PRODUCTIVITY claim lifecycle.

    Enforces the settled one-date-one-lifecycle invariant: within one entitlement
    a date lives in at most one claim regardless of SUBMITTED/APPROVED/REJECTED.
    Rejection does not free the date.
    """


class ProductivityAdjudicationError(InsuranceClaimServiceError):
    """A per-date adjudication is malformed (e.g. adjusted hours without a note)."""


def _validate_active_insurance_entitlement(
    *, class_id: str, entitlement_id: str, target_seat_id: int
) -> EntitlementEvent:
    """Validate the entitlement lineage through the owning Store domain.

    Confirms a GRANTED INSURANCE event exists for the (entitlement_id, class_id,
    target_seat_id) tuple and that the lineage carries no terminal event. Returns
    the GRANTED event so callers can reference its immutable payload.
    """
    granted_event = (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.target_seat_id == target_seat_id,
            EntitlementEvent.event_type == "GRANTED",
        )
        .first()
    )
    if granted_event is None:
        raise ClaimEntitlementInvalid(
            f"No GRANTED entitlement {entitlement_id} for seat {target_seat_id} in class {class_id}"
        )
    if granted_event.entitlement_type != _INSURANCE_ENTITLEMENT_TYPE:
        raise ClaimEntitlementInvalid(
            f"Entitlement {entitlement_id} is {granted_event.entitlement_type}, not INSURANCE"
        )

    terminal_event = (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type.in_(_TERMINAL_ENTITLEMENT_EVENTS),
        )
        .first()
    )
    if terminal_event is not None:
        raise ClaimEntitlementInvalid(
            f"Entitlement {entitlement_id} already terminal: {terminal_event.event_type}"
        )
    return granted_event


def create_claim(
    *,
    class_id: str,
    entitlement_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    correlation_id: str,
    claim_basis: dict,
    submitted_at: Optional[datetime] = None,
) -> InsuranceClaim:
    """Create a SUBMITTED insurance claim against an active entitlement lineage.

    Idempotent on ``correlation_id``: replaying with the same correlation and the
    same (class_id, entitlement_id, target_seat_id) returns the existing claim;
    a mismatch raises :class:`ClaimIdempotencyConflict`.

    Raises :class:`ClaimEntitlementInvalid` if the entitlement lineage does not
    validate through the owning domain.
    """
    if not isinstance(claim_basis, dict):
        raise InsuranceClaimServiceError("claim_basis must be a dict of submitted facts")
    if not correlation_id:
        raise InsuranceClaimServiceError("correlation_id is required for idempotent submission")

    existing = (
        db.session.query(InsuranceClaim)
        .filter(InsuranceClaim.correlation_id == correlation_id)
        .first()
    )
    if existing is not None:
        if (
            existing.class_id != class_id
            or existing.entitlement_id != entitlement_id
            or existing.target_seat_id != target_seat_id
        ):
            raise ClaimIdempotencyConflict(
                f"correlation_id {correlation_id} already exists for a different claim context"
            )
        return existing

    _validate_active_insurance_entitlement(
        class_id=class_id,
        entitlement_id=entitlement_id,
        target_seat_id=target_seat_id,
    )

    claim = InsuranceClaim(
        claim_id=str(uuid.uuid4()),
        class_id=class_id,
        entitlement_id=entitlement_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        status=SUBMITTED,
        correlation_id=correlation_id,
        claim_basis=claim_basis,
        submitted_at=submitted_at or utc_now(),
    )
    db.session.add(claim)
    db.session.flush()
    return claim


def get_claim(claim_id: str, *, class_id: str) -> Optional[InsuranceClaim]:
    """Return a single class-scoped claim, or ``None``."""
    return (
        db.session.query(InsuranceClaim)
        .filter(
            InsuranceClaim.claim_id == claim_id,
            InsuranceClaim.class_id == class_id,
        )
        .first()
    )


def list_claims_for_entitlement(
    *,
    class_id: str,
    entitlement_id: str,
    target_seat_id: Optional[int] = None,
    statuses: Optional[Iterable[str]] = None,
) -> list[InsuranceClaim]:
    """List claims for one entitlement lineage, newest first.

    Optionally narrowed to a target seat and/or a set of lifecycle states. This
    read is the basis for later derived projections (weekly claimed hours,
    payouts, remaining allowance) — all computed from immutable claim history.
    """
    query = db.session.query(InsuranceClaim).filter(
        InsuranceClaim.class_id == class_id,
        InsuranceClaim.entitlement_id == entitlement_id,
    )
    if target_seat_id is not None:
        query = query.filter(InsuranceClaim.target_seat_id == target_seat_id)
    if statuses is not None:
        query = query.filter(InsuranceClaim.status.in_(list(statuses)))
    return query.order_by(
        InsuranceClaim.submitted_at.desc(), InsuranceClaim.claim_id.desc()
    ).all()


def decide_claim(
    *,
    claim_id: str,
    class_id: str,
    decided_by_seat_id: int,
    approved: bool,
    decided_at: Optional[datetime] = None,
    decision_note: Optional[str] = None,
    result_amount: Optional[Decimal] = None,
    payroll_event_id: Optional[int] = None,
    ledger_transaction_id: Optional[int] = None,
) -> InsuranceClaim:
    """Transition a SUBMITTED claim to a terminal APPROVED/REJECTED state.

    Terminal states are immutable: deciding a claim that is not ``SUBMITTED``
    raises :class:`ClaimAlreadyDecided`. Downstream lineage references
    (``result_amount``, ``payroll_event_id``, ``ledger_transaction_id``) are only
    recorded on approval; they remain ``NULL`` for rejections and for claims that
    have not yet been decided.
    """
    claim = get_claim(claim_id, class_id=class_id)
    if claim is None:
        raise ClaimNotFound(f"Claim {claim_id} not found in class {class_id}")
    if claim.status != SUBMITTED:
        raise ClaimAlreadyDecided(
            f"Claim {claim_id} is already terminal ({claim.status}); decisions are immutable"
        )

    claim.status = APPROVED if approved else REJECTED
    claim.decided_by_seat_id = decided_by_seat_id
    claim.decided_at = decided_at or utc_now()
    claim.decision_note = decision_note
    if approved:
        claim.result_amount = result_amount
        claim.payroll_event_id = payroll_event_id
        claim.ledger_transaction_id = ledger_transaction_id

    db.session.add(claim)
    db.session.flush()
    return claim


# ---------------------------------------------------------------------------
# PRODUCTIVITY claim dates (normalized child rows)
# ---------------------------------------------------------------------------
#
# A PRODUCTIVITY claim asserts one or more class-local loss-dates. Each date is a
# normalized ``InsuranceClaimProductivityDate`` row, NOT a JSON list on the parent
# claim. ``student_claimed_hours`` is immutable submitted truth;
# ``teacher_approved_hours`` / ``adjustment_note`` / ``recognized_payout`` are set
# at adjudication. Weekly/period projections are always re-derived from these rows.


def add_productivity_claim_dates(
    *,
    claim: InsuranceClaim,
    dates: Iterable[tuple],
) -> list[InsuranceClaimProductivityDate]:
    """Attach asserted PRODUCTIVITY loss-dates to a SUBMITTED claim.

    ``dates`` is an iterable of ``(claim_date: date, student_claimed_hours,
    student_explanation: str)`` triples. ``student_explanation`` is required,
    student-authored evidence (never fabricated or backfilled). Rows are created
    with adjudication fields NULL. Idempotent replay: if a row for ``(claim_id,
    claim_date)`` already exists, it is returned unchanged (submitted hours and
    explanation are never rewritten).

    Raises :class:`ProductivityDateConflict` if a date is already used by a
    *different* claim under the same entitlement (the ``UNIQUE(entitlement_id,
    claim_date)`` invariant). The DB constraint is the concurrency backstop; this
    pre-check turns the common case into a clean domain error.
    """
    created: list[InsuranceClaimProductivityDate] = []
    for claim_date, student_claimed_hours, student_explanation in dates:
        if not isinstance(claim_date, date):
            raise InsuranceClaimServiceError(
                f"claim_date must be a datetime.date, got {claim_date!r}"
            )
        hours = Decimal(str(student_claimed_hours))
        if hours < Decimal("0"):
            raise InsuranceClaimServiceError("student_claimed_hours must be non-negative")
        explanation = (student_explanation or "").strip()
        if not explanation:
            raise InsuranceClaimServiceError(
                "student_explanation is required for every PRODUCTIVITY claim date"
            )

        # Idempotent replay within the same case.
        same_case = (
            db.session.query(InsuranceClaimProductivityDate)
            .filter(
                InsuranceClaimProductivityDate.claim_id == claim.claim_id,
                InsuranceClaimProductivityDate.claim_date == claim_date,
            )
            .first()
        )
        if same_case is not None:
            created.append(same_case)
            continue

        # A date already claimed under this entitlement (any status) is taken.
        taken = (
            db.session.query(InsuranceClaimProductivityDate)
            .filter(
                InsuranceClaimProductivityDate.entitlement_id == claim.entitlement_id,
                InsuranceClaimProductivityDate.claim_date == claim_date,
            )
            .first()
        )
        if taken is not None:
            raise ProductivityDateConflict(
                f"Date {claim_date.isoformat()} already backs claim {taken.claim_id} "
                f"under entitlement {claim.entitlement_id}"
            )

        row = InsuranceClaimProductivityDate(
            claim_id=claim.claim_id,
            entitlement_id=claim.entitlement_id,
            class_id=claim.class_id,
            claim_date=claim_date,
            student_claimed_hours=hours,
            student_explanation=explanation,
        )
        db.session.add(row)
        created.append(row)

    db.session.flush()
    return created


def list_productivity_dates_for_claim(
    claim_id: str, *, class_id: str
) -> list[InsuranceClaimProductivityDate]:
    """All asserted date rows for one claim case, ascending by date."""
    return (
        db.session.query(InsuranceClaimProductivityDate)
        .filter(
            InsuranceClaimProductivityDate.claim_id == claim_id,
            InsuranceClaimProductivityDate.class_id == class_id,
        )
        .order_by(InsuranceClaimProductivityDate.claim_date.asc())
        .all()
    )


def list_productivity_dates_for_entitlement(
    *, class_id: str, entitlement_id: str
) -> list[InsuranceClaimProductivityDate]:
    """All asserted date rows across every claim under one entitlement lineage.

    The basis for derived projections (date-allowance used, weekly claimed hours,
    period recognized-payout consumption) — always computed from history, never a
    stored counter.
    """
    return (
        db.session.query(InsuranceClaimProductivityDate)
        .filter(
            InsuranceClaimProductivityDate.class_id == class_id,
            InsuranceClaimProductivityDate.entitlement_id == entitlement_id,
        )
        .order_by(InsuranceClaimProductivityDate.claim_date.asc())
        .all()
    )


class ProductivityDateWithStatus:
    """A PRODUCTIVITY date row paired with its parent claim's lifecycle status.

    Immutable read projection used to compute the state-sensitive weekly hours
    basis (SUBMITTED = student claimed, APPROVED = teacher approved, REJECTED = 0)
    without the caller re-joining child rows to parent claims.
    """

    __slots__ = ("claim_date", "student_claimed_hours", "teacher_approved_hours", "status")

    def __init__(self, claim_date, student_claimed_hours, teacher_approved_hours, status):
        self.claim_date = claim_date
        self.student_claimed_hours = student_claimed_hours
        self.teacher_approved_hours = teacher_approved_hours
        self.status = status


def list_productivity_dates_with_status_for_entitlement(
    *, class_id: str, entitlement_id: str
) -> list[ProductivityDateWithStatus]:
    """Asserted date rows joined to their parent claim status for one entitlement.

    Powers the weekly claimed-hours projection: each date's contribution depends
    on the owning claim's lifecycle state, which is not stored on the child row.
    """
    rows = (
        db.session.query(
            InsuranceClaimProductivityDate.claim_date,
            InsuranceClaimProductivityDate.student_claimed_hours,
            InsuranceClaimProductivityDate.teacher_approved_hours,
            InsuranceClaim.status,
        )
        .join(
            InsuranceClaim,
            InsuranceClaimProductivityDate.claim_id == InsuranceClaim.claim_id,
        )
        .filter(
            InsuranceClaimProductivityDate.class_id == class_id,
            InsuranceClaimProductivityDate.entitlement_id == entitlement_id,
        )
        .order_by(InsuranceClaimProductivityDate.claim_date.asc())
        .all()
    )
    return [
        ProductivityDateWithStatus(
            claim_date=claim_date,
            student_claimed_hours=student_claimed_hours,
            teacher_approved_hours=teacher_approved_hours,
            status=status,
        )
        for claim_date, student_claimed_hours, teacher_approved_hours, status in rows
    ]


def sum_recognized_payout_for_entitlement(
    *, class_id: str, entitlement_id: str
) -> Decimal:
    """Σ of persisted ``recognized_payout`` across the entitlement's date history.

    Period payout consumption for PRODUCTIVITY is the sum of immutable recognized
    payouts, never a reconstruction from live pay rate.
    """
    total = Decimal("0.00")
    for row in list_productivity_dates_for_entitlement(
        class_id=class_id, entitlement_id=entitlement_id
    ):
        if row.recognized_payout is not None:
            total += row.recognized_payout
    return total


def adjudicate_productivity_claim_dates(
    *,
    claim_id: str,
    class_id: str,
    adjudications: dict,
) -> list[InsuranceClaimProductivityDate]:
    """Record per-date adjudication for a PRODUCTIVITY claim being approved.

    ``adjudications`` maps a ``claim_date`` (``datetime.date``) to a dict of:

    * ``teacher_approved_hours`` — adjudicated hours (defaults to the immutable
      submitted hours when omitted);
    * ``adjustment_note`` — REQUIRED iff approved hours differ from submitted
      hours (including a reject-to-zero of a single date);
    * ``recognized_payout`` — the immutable economic result to persist.

    Every asserted date row for the claim MUST appear in ``adjudications``.
    ``student_claimed_hours`` is never rewritten.

    Raises :class:`ProductivityAdjudicationError` on a missing note where hours
    differ, or on an incomplete/extra adjudication set.
    """
    rows = list_productivity_dates_for_claim(claim_id, class_id=class_id)
    if not rows:
        raise ProductivityAdjudicationError(
            f"Claim {claim_id} has no productivity date rows to adjudicate"
        )

    by_date = {row.claim_date: row for row in rows}
    if set(adjudications.keys()) != set(by_date.keys()):
        raise ProductivityAdjudicationError(
            "Adjudication set must cover exactly the claim's asserted dates "
            f"(expected {sorted(d.isoformat() for d in by_date)}, "
            f"got {sorted(d.isoformat() for d in adjudications)})"
        )

    for claim_date, row in by_date.items():
        entry = adjudications[claim_date]
        approved_raw = entry.get("teacher_approved_hours")
        approved_hours = (
            row.student_claimed_hours
            if approved_raw is None
            else Decimal(str(approved_raw))
        )
        if approved_hours < Decimal("0"):
            raise ProductivityAdjudicationError("teacher_approved_hours must be non-negative")
        # Downward-only adjudication: the teacher recognizes at most what the
        # student asserted. Approving MORE than the immutable submitted hours would
        # let adjudication author a claim the student never made, so it is rejected
        # outright (never silently clamped — that would blur teacher intent).
        if approved_hours > row.student_claimed_hours:
            raise ProductivityAdjudicationError(
                f"Date {claim_date.isoformat()}: approved hours ({approved_hours}) "
                f"exceed the student's claimed hours ({row.student_claimed_hours}); "
                f"teacher adjudication is downward-only"
            )

        note = entry.get("adjustment_note")
        if approved_hours != row.student_claimed_hours and not (note and note.strip()):
            raise ProductivityAdjudicationError(
                f"Date {claim_date.isoformat()}: approved hours ({approved_hours}) "
                f"differ from claimed ({row.student_claimed_hours}) but no "
                f"adjustment_note was provided"
            )

        payout_raw = entry.get("recognized_payout")
        recognized_payout = (
            None if payout_raw is None else Decimal(str(payout_raw))
        )

        row.teacher_approved_hours = approved_hours
        row.adjustment_note = note
        row.recognized_payout = recognized_payout
        db.session.add(row)

    db.session.flush()
    return rows
