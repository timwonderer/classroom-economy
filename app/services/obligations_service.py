from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import (
    EntitlementEvent,
    InsuranceClaim,
    InsuranceEnrollment,
    ObligationAssessment,
    ObligationLifecycle,
    ObligationReversal,
    ObligationSatisfaction,
    RentPolicyVersion,
    RentSettings,
    Seat,
)
from app.utils.time import utc_now


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claim_assessment_key(claim_id: int) -> str:
    return f"insurance-claim:{claim_id}"


def _get_claim_assessment(assessment_key: str, seat_id: int, class_id: str) -> ObligationAssessment | None:
    return (
        ObligationAssessment.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            cycle_idempotency_key=assessment_key,
        )
        .order_by(ObligationAssessment.id.desc())
        .first()
    )


def _create_claim_assessment(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    claim_amount,
    incident_date,
    assessed_at,
) -> ObligationAssessment:
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_CLAIM",
        amount_snap=claim_amount,
        due_at=incident_date,
        assessed_at=assessed_at,
        cycle_idempotency_key=_claim_assessment_key(claim_id),
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=assessed_at,
        )
    )
    return assessment


def _require_claim_assessment(claim_id: int, seat_id: int, class_id: str) -> ObligationAssessment:
    key = _claim_assessment_key(claim_id)
    assessment = _get_claim_assessment(key, seat_id, class_id)
    if assessment is None:
        raise ValueError(f"Missing canonical claim assessment for insurance claim {claim_id}")
    return assessment


def _set_assessment_lifecycle(assessment: ObligationAssessment, *, status: str, updated_at):
    lifecycle = assessment.lifecycle
    if lifecycle is None:
        lifecycle = ObligationLifecycle(
            assessment_id=assessment.id,
            status=status,
            updated_at=updated_at,
        )
        db.session.add(lifecycle)
        return lifecycle
    lifecycle.status = status
    lifecycle.updated_at = updated_at
    return lifecycle


# ---------------------------------------------------------------------------
# Rent mutations
# ---------------------------------------------------------------------------

def record_rent_payment(
    *,
    seat_id: int,
    class_id: str,
    period: str,
    amount_paid,
    period_month: int,
    period_year: int,
    coverage_month: int,
    coverage_year: int,
    was_late: bool,
    late_fee_charged,
    coverage_start_time=None,
    coverage_end_time=None,
    cycle_idempotency_key: str | None = None,
    transaction_id: int | None = None,
    rent_policy_version_id: int,
) -> ObligationAssessment:
    """Record a rent payment as a canonical assessment + satisfaction.

    ``rent_policy_version_id`` is required.  ``amount_snap`` is set to the
    version's ``rent_amount`` (the policy-defined charge at assessment time).
    The actual payment amount lives on ``ObligationSatisfaction.amount_paid``
    and may differ (late fees, partial payments, etc.).

    V2 is a clean break — no legacy data exists, so every rent assessment
    must reference an immutable policy version.
    """
    now = utc_now()
    period_key = f"{coverage_year}-{coverage_month:02d}" if coverage_year is not None and coverage_month is not None else None

    version = db.session.get(RentPolicyVersion, rent_policy_version_id)
    if version is None:
        raise ValueError(f"RentPolicyVersion {rent_policy_version_id} not found")

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        obligation_type="RENT",
        amount_snap=version.rent_amount,
        assessed_at=now,
        period_key=period_key,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        rent_policy_version_id=rent_policy_version_id,
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="PAID",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=amount_paid,
            was_late=was_late,
            late_fee_charged=late_fee_charged,
            transaction_id=transaction_id,
            satisfied_at=now,
        )
    )
    return assessment


def record_rent_waiver(
    *,
    seat_id: int,
    class_id: str,
    waiver_start_date,
    waiver_end_date,
    periods_count: int,
    reason: str | None = None,
    created_by_seat_id: int | None = None,
    created_by_user_id: int | None = None,
) -> ObligationAssessment:
    """Record a rent waiver as a canonical assessment + reversal."""
    now = utc_now()
    if created_by_seat_id is None and created_by_user_id is not None:
        created_by_seat_id = (
            Seat.query.filter_by(class_id=class_id, role="teacher", user_id=created_by_user_id)
            .order_by(Seat.id.asc())
            .with_entities(Seat.id)
            .scalar()
        )
    if created_by_seat_id is None:
        created_by_seat_id = (
            Seat.query.filter_by(class_id=class_id, role="teacher")
            .order_by(Seat.id.asc())
            .with_entities(Seat.id)
            .scalar()
        )

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="RENT_WAIVER",
        amount_snap=Decimal("0.00"),
        due_at=waiver_start_date,
        assessed_at=now,
        coverage_start_time=waiver_start_date,
        coverage_end_time=waiver_end_date,
        cycle_idempotency_key=f"rent-waiver:{seat_id}:{class_id}:{waiver_start_date.isoformat()}",
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="REVERSED",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationReversal(
            assessment_id=assessment.id,
            reason=reason,
            reversed_at=now,
            reversed_by_seat_id=created_by_seat_id,
        )
    )
    return assessment


# ---------------------------------------------------------------------------
# Insurance mutations
# ---------------------------------------------------------------------------

def record_insurance_enrollment(
    *,
    seat_id: int,
    class_id: str,
    policy,
    purchase_date,
    next_payment_due,
    coverage_start_date,
) -> InsuranceEnrollment:
    """Record an insurance enrollment in canonical tables only."""
    enrollment = InsuranceEnrollment(
        seat_id=seat_id,
        class_id=class_id,
        policy_id=policy.id,
        status='active',
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=next_payment_due,
        coverage_start_date=coverage_start_date,
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_ENROLLMENT",
        amount_snap=0,
        due_at=next_payment_due,
        assessed_at=purchase_date,
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=purchase_date,
        )
    )
    return enrollment


def record_insurance_claim(
    *,
    enrollment_id: int,
    policy_id: int,
    seat_id: int,
    class_id: str,
    incident_date,
    description: str,
    claim_amount,
    claim_item: str | None,
    comments: str | None,
    transaction_id: int | None,
) -> InsuranceClaim:
    """Record an insurance claim.

    InsuranceClaim is retained as the claim metadata store until its columns
    are migrated onto assessment_events. The canonical assessment/lifecycle
    rows are created alongside it.
    """
    claim = InsuranceClaim(
        enrollment_id=enrollment_id,
        policy_id=policy_id,
        seat_id=seat_id,
        class_id=class_id,
        incident_date=incident_date,
        description=description,
        claim_amount=claim_amount,
        claim_item=claim_item,
        comments=comments,
        status='pending',
        transaction_id=transaction_id,
    )
    db.session.add(claim)
    db.session.flush()

    _create_claim_assessment(
        seat_id=seat_id,
        class_id=class_id,
        claim_id=claim.id,
        claim_amount=claim_amount,
        incident_date=incident_date,
        assessed_at=utc_now(),
    )
    return claim


def apply_claim_resolution(
    claim: InsuranceClaim,
    *,
    status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_user_id: int | None,
    processed_by_seat_id: int | None = None,
    processed_at,
    approved_amount=None,
):
    """Advance claim state and its canonical lifecycle."""
    claim.status = status
    claim.teacher_notes = teacher_notes
    claim.rejection_reason = rejection_reason if status == 'rejected' else None
    claim.processed_date = processed_at
    claim.processed_by_user_id = processed_by_user_id
    claim.approved_amount = approved_amount

    assessment = _require_claim_assessment(claim.id, claim.seat_id, claim.class_id)
    if processed_by_seat_id is None:
        if processed_by_user_id is not None:
            processed_by_seat_id = (
                Seat.query.filter_by(
                    class_id=claim.class_id,
                    role="teacher",
                    user_id=processed_by_user_id,
                )
                .order_by(Seat.id.asc())
                .with_entities(Seat.id)
                .scalar()
            )
        if processed_by_seat_id is None:
            processed_by_seat_id = (
                Seat.query.filter_by(class_id=claim.class_id, role="teacher")
                .order_by(Seat.id.asc())
                .with_entities(Seat.id)
                .scalar()
            )

    if status in {"approved", "paid"}:
        _set_assessment_lifecycle(assessment, status="PAID", updated_at=processed_at)
        if assessment.satisfaction is None:
            db.session.add(
                ObligationSatisfaction(
                    assessment_id=assessment.id,
                    method="PAYMENT",
                    amount_paid=approved_amount,
                    satisfied_at=processed_at,
                )
            )
        else:
            assessment.satisfaction.amount_paid = approved_amount
            assessment.satisfaction.satisfied_at = processed_at
    elif status == "rejected":
        _set_assessment_lifecycle(assessment, status="REVERSED", updated_at=processed_at)
        if assessment.reversal is None:
            db.session.add(
                ObligationReversal(
                    assessment_id=assessment.id,
                    reason=rejection_reason or teacher_notes,
                    reversed_at=processed_at,
                    reversed_by_seat_id=processed_by_seat_id,
                )
            )
        else:
            assessment.reversal.reason = rejection_reason or teacher_notes
            assessment.reversal.reversed_at = processed_at
            assessment.reversal.reversed_by_seat_id = processed_by_seat_id
    return claim


# ---------------------------------------------------------------------------
# Canonical read helpers
# ---------------------------------------------------------------------------

def has_rent_coverage(
    seat_id: int,
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> bool:
    """Check whether a seat has a PAID rent assessment for the given cycle."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .first()
    ) is not None


def get_rent_payments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> list[ObligationAssessment]:
    """Return all PAID rent assessments for a class + cycle."""
    return (
        ObligationAssessment.query
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .order_by(ObligationAssessment.assessed_at.asc())
        .all()
    )


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    *,
    limit: int | None = None,
) -> list[ObligationAssessment]:
    """Return rent assessments for a seat, newest first."""
    q = (
        ObligationAssessment.query
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
        )
        .order_by(ObligationAssessment.assessed_at.desc())
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def has_active_rent_waiver(
    seat_id: int,
    class_id: str,
    coverage_date,
) -> bool:
    """Check whether a seat has a canonical rent waiver covering the given date."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .first()
    ) is not None


def get_claim_status(claim_id: int) -> str | None:
    """Return the canonical lifecycle status for an insurance claim."""
    assessment = (
        ObligationAssessment.query
        .filter_by(
            obligation_type="INSURANCE_CLAIM",
            cycle_idempotency_key=_claim_assessment_key(claim_id),
        )
        .first()
    )
    if assessment is None:
        return None
    return assessment.lifecycle.status if assessment.lifecycle else None


# ---------------------------------------------------------------------------
# Rent read helpers (canonical replacements for legacy RentPayment/RentWaiver)
# ---------------------------------------------------------------------------

def get_paid_rent_assessments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
    *,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Return PAID rent assessments for a class + cycle, optionally filtered by seats.

    Each returned assessment has a loaded `satisfaction` relationship with
    `amount_paid`, `was_late`, `late_fee_charged`, `transaction_id`, and
    `satisfied_at` (the canonical equivalent of ``payment_date``).
    """
    from app.models import Transaction

    q = (
        ObligationAssessment.query
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .outerjoin(ObligationSatisfaction, ObligationSatisfaction.assessment_id == ObligationAssessment.id)
        .outerjoin(Transaction, Transaction.id == ObligationSatisfaction.transaction_id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
    )
    if seat_ids is not None:
        q = q.filter(ObligationAssessment.seat_id.in_(seat_ids))
    # Exclude assessments whose backing ledger transaction was voided
    q = q.filter(
        db.or_(
            ObligationSatisfaction.transaction_id.is_(None),
            Transaction.is_void.is_(False),
        )
    )
    return q.order_by(ObligationAssessment.assessed_at.asc()).all()


def get_waived_seat_ids_for_cycle(
    class_id: str,
    coverage_date,
    seat_ids: list[int],
) -> set[int]:
    """Return the set of seat_ids that have a canonical rent waiver covering ``coverage_date``."""
    rows = (
        db.session.query(ObligationAssessment.seat_id)
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.seat_id.in_(seat_ids),
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .all()
    )
    return {r[0] for r in rows}


def get_rent_waiver_for_seat(
    seat_id: int,
    class_id: str,
    coverage_date,
) -> ObligationAssessment | None:
    """Return the canonical rent waiver assessment covering ``coverage_date``, if any."""
    return (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .order_by(ObligationAssessment.assessed_at.desc())
        .first()
    )


def get_rent_waivers_for_seat(
    seat_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Return all rent waiver assessments for a seat, newest first."""
    return (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
        )
        .order_by(ObligationAssessment.assessed_at.desc())
        .all()
    )


def get_active_rent_waivers_for_class(
    class_id: str,
    *,
    coverage_date=None,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Return active rent-waiver assessments for a class at a point in time."""
    if coverage_date is None:
        coverage_date = utc_now()
    q = (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
    )
    if seat_ids is not None:
        q = q.filter(ObligationAssessment.seat_id.in_(seat_ids))
    return q.order_by(ObligationAssessment.assessed_at.desc()).all()


def remove_rent_waiver_assessment(assessment_id: int) -> ObligationAssessment | None:
    """Delete a canonical rent-waiver assessment and its derived rows."""
    assessment = db.session.get(ObligationAssessment, assessment_id)
    if assessment is None or assessment.obligation_type != "RENT_WAIVER":
        return None

    if assessment.reversal is not None:
        db.session.delete(assessment.reversal)
    if assessment.satisfaction is not None:
        db.session.delete(assessment.satisfaction)
    if assessment.lifecycle is not None:
        db.session.delete(assessment.lifecycle)
    db.session.delete(assessment)
    return assessment


def get_cycle_rent_amount(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> "Decimal | None":
    """Return the policy-defined rent amount for a cycle.

    Reads from the ``RentPolicyVersion`` attached to any assessment in the
    cycle.  Returns None only if no assessments exist for the cycle yet.
    """
    return get_cycle_rent_amount_from_version(class_id, coverage_month, coverage_year)


# ---------------------------------------------------------------------------
# Rent policy version helpers
# ---------------------------------------------------------------------------

def resolve_active_rent_policy_version(class_id: str) -> RentPolicyVersion | None:
    """Return the currently active rent policy version for a class.

    Every RentSettings row has an active version from creation.
    Returns None only if the class has no rent settings.
    """
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    if settings and settings.active_version_id:
        return db.session.get(RentPolicyVersion, settings.active_version_id)
    return None


def resolve_next_rent_policy_version(class_id: str) -> RentPolicyVersion | None:
    """Return the version scheduled for the next cycle.

    If ``RentSettings.next_version_id`` is set, returns that version.
    Otherwise returns None (no pending change).
    """
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    if settings and settings.next_version_id:
        return db.session.get(RentPolicyVersion, settings.next_version_id)
    return None


def activate_next_rent_policy_version(class_id: str) -> RentPolicyVersion | None:
    """Promote the next version to active at a cycle boundary.

    Called by the cycle-start FEAT or scheduled task.  Returns the newly
    activated version, or None if there was nothing to activate.
    """
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    if not settings or not settings.next_version_id:
        return None

    version = db.session.get(RentPolicyVersion, settings.next_version_id)
    if version is None:
        return None

    settings.active_version_id = version.id
    settings.next_version_id = None
    return version


def create_and_schedule_rent_policy_version(class_id: str) -> RentPolicyVersion | None:
    """Snapshot current RentSettings into a new version and schedule it for next cycle.

    Called after a teacher saves rent settings.  Creates an immutable
    ``RentPolicyVersion`` row and sets it as the ``next_version_id``.
    If there is no active version yet, also sets it as active immediately
    (first-time setup).
    """
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    if not settings:
        return None

    version = settings.create_policy_version()
    db.session.add(version)
    db.session.flush()

    settings.next_version_id = version.id

    # First-time setup: if no active version exists, activate immediately
    if settings.active_version_id is None:
        settings.active_version_id = version.id

    return version


def get_cycle_rent_amount_from_version(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> "Decimal | None":
    """Return the policy-defined rent amount for a cycle from assessment versions.

    Looks for any assessment in the cycle that has a ``rent_policy_version_id``
    and returns the version's ``rent_amount``.  Returns None if no versioned
    assessments exist (legacy data).
    """
    assessment = (
        ObligationAssessment.query
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationAssessment.rent_policy_version_id.isnot(None),
        )
        .first()
    )
    if assessment and assessment.rent_policy_version_id:
        version = db.session.get(RentPolicyVersion, assessment.rent_policy_version_id)
        if version:
            return version.rent_amount
    return None


def get_rent_policy_version_history(class_id: str) -> list[RentPolicyVersion]:
    """Return all rent policy versions for a class, newest first."""
    return (
        RentPolicyVersion.query
        .filter_by(class_id=class_id)
        .order_by(RentPolicyVersion.version_number.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Entitlement mutations
# ---------------------------------------------------------------------------

def record_entitlement_grant(
    *,
    seat_id: int,
    class_id: str,
    quantity: int,
    trigger_id: str | None = None,
    assessment_id: int | None = None,
) -> EntitlementEvent:
    """Record a GRANT entitlement event for obligation-linked perks (e.g., hall passes from rent)."""
    event = EntitlementEvent(
        seat_id=seat_id,
        class_id=class_id,
        assessment_id=assessment_id,
        trigger_id=trigger_id,
        quantity_delta=quantity,
        event_type="GRANT",
        occurred_at=utc_now(),
    )
    db.session.add(event)
    return event
