"""
Obligation View Models — Cross-Domain Composition

Derives presentation-ready obligation status by composing:
- Obligations domain: PAYMENT event references (ledger_transaction_id)
- Ledger domain: authoritative Transaction amounts
- Per DOM-OBL-001 §VIII: paid_amount = sum(Ledger amounts from PAYMENT events)

This is NOT a domain service. It is a composition layer that joins two
authoritative sources for presentation/read-model use.

Routes and templates call this layer to build complete obligation views.
Obligations and Ledger services remain isolated and own their own facts.
"""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass, replace
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import ObligationAssessment, Transaction, BillCycle, Seat, ClassEconomy, IdentityProfile, RentSettings


@dataclass(frozen=True)
class ObligationPaymentStatus:
    """Complete payment status derived from Obligations + Ledger facts."""
    correlation_id: str
    is_satisfied: bool
    is_outstanding: bool
    is_past_due: bool
    total_paid: Decimal
    amount_waived: bool


def get_obligation_payment_status(
    correlation_id: str,
    class_id: str,
    assessed_amount: Decimal | None = None,
) -> ObligationPaymentStatus | None:
    """
    Derive complete payment status by composing Obligations and Ledger truth.

    Per DOM-OBL-001 §VIII:
    - Retrieves PAYMENT events from assessment_events (Obligations domain)
    - Reads Transaction amounts from Ledger domain via ledger_transaction_id FK
    - Sums authoritative Ledger amounts to compute total_paid
    - Derives satisfaction: (paid_amount >= assessed_amount) OR (has_waiver)

    Args:
        correlation_id: Identifies the individual liability
        class_id: Scope for multi-tenancy
        assessed_amount: If provided, used for satisfaction computation

    Returns:
        Complete payment status, or None if assessment not found
    """
    from app.services import obligations_service

    # Step 1: Retrieve the ASSESSMENT event from Obligations domain
    assessment = obligations_service.get_assessment_for_correlation(correlation_id)
    if not assessment:
        return None

    # Step 2: Retrieve all PAYMENT and WAIVED events from Obligations domain
    satisfaction_events = obligations_service.get_satisfaction_events(correlation_id)

    # Step 3: Compose with Ledger domain - sum authoritative Transaction amounts
    total_paid = Decimal('0.00')
    has_waiver = False

    for event in satisfaction_events:
        if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
            # CROSS-DOMAIN READ: Ledger provides authoritative monetary truth
            # (per DOM-OBL-001 §XI: Obligations consumes Ledger for settlement truth)
            txn = db.session.get(Transaction, event.ledger_transaction_id)
            if txn and txn.status != 'void':
                total_paid += Decimal(str(txn.amount))
        elif event.event_type == 'WAIVED':
            has_waiver = True

    # Step 4: Derive satisfaction per DOM-OBL-001 §VIII
    if assessed_amount is None:
        assessed_amount = Decimal('0.00')

    is_satisfied = has_waiver or (total_paid >= assessed_amount)
    is_outstanding = not is_satisfied
    is_past_due = (
        is_outstanding and assessment.due_at
        and db.session.query(db.func.now()).scalar() > assessment.due_at
    )

    return ObligationPaymentStatus(
        correlation_id=correlation_id,
        is_satisfied=is_satisfied,
        is_outstanding=is_outstanding,
        is_past_due=is_past_due,
        total_paid=total_paid,
        amount_waived=has_waiver,
    )


def get_total_paid_for_obligation(
    correlation_id: str,
    class_id: str,
) -> Decimal:
    """
    Convenience: get just the total paid amount for an obligation.

    Routes that only need payment total (not full status) can call this
    instead of get_obligation_payment_status and extracting the amount.

    Returns 0.00 if obligation not found.
    """
    status = get_obligation_payment_status(correlation_id, class_id)
    if not status:
        return Decimal('0.00')
    return status.total_paid


# ============================================================================
# Generic Obligation View Models (Any obligation_type: RENT, INSURANCE_PREMIUM, etc.)
# ============================================================================

@dataclass(frozen=True)
class StudentObligationView:
    """Generic student view of any obligation type (RENT, INSURANCE_PREMIUM, FINE, FEE, etc.).

    Answers: "What does this student owe right now, how much have they satisfied,
    when do they move to the next cycle?"

    All fields are derived from obligation_service facts + bill_cycles + ClassConfig.
    Phase 6-7 VERIFIED: All template access goes through view.* namespace only.
    """

    obligation_type: str
    seat_id: int
    class_id: str
    current_block: str  # Period identifier (e.g., 'A', 'B', or class-level identifier)

    # Current period (OWE phase) — Primary status dict
    current_period: dict  # {due_date, grace_end, amount_due, amount_paid, amount_waived, balance, is_paid, is_waived, is_past_due, is_preview, days_until_due, days_overdue, is_late, rent_is_active, total_due, remaining_amount}

    # Period status by block/identifier — keyed dict for multi-period access
    period_status: dict  # {block_id: {same fields as current_period}}

    # Prior obligations (arrears)
    prior_obligations: list  # [{period, amount, status, due_date, is_past_due}]

    # Ledger history (payment/waiver events)
    payment_history: list  # [{date, amount, type, status, correlation_id}]

    # Active waivers for this obligation type
    active_waivers: list  # List of waiver events

    # Computed totals
    totals: dict  # {total_owed, total_paid_all_time, total_waived}

    # Configuration (from ClassConfig, not domain-specific settings)
    settings: dict  # {amount_expected, late_fee, grace_period_days, frequency}

    # Status counts for display (e.g., rent_status_counts)
    status_counts: dict  # {SATISFIED, OUTSTANDING, PAST_DUE}

    # Phase 1 display formatting (audit violations: student_rent.html line 142)
    display_current_due_date: str | None = None  # Pre-formatted as "%B %d, %Y" or None
    display_amount_due: str | None = None  # Pre-formatted as "$X.XX"
    display_total_due: str | None = None  # Pre-formatted as "$X.XX"
    display_amount_paid: str | None = None  # Pre-formatted as "$X.XX"
    display_remaining_amount: str | None = None  # Pre-formatted as "$X.XX"


@dataclass(frozen=True)
class ClassObligationSummary:
    """Generic teacher view: status of all students in one class for one obligation type.

    Answers: "Which students OWE, which have SATISFIED, which have MOVED ON?"
    """

    class_id: str
    obligation_type: str
    summary_date: datetime

    # Roll-up counts
    status_breakdown: dict  # {up_to_date, outstanding, past_due_grace, past_due_overdue}

    # Per-student summary
    student_rows: list  # [{seat_id, student_name, status, due_date, amount_due, amount_paid, balance, days_overdue, is_waived}]

    # Phase 1 display formatting (audit violations: admin_rent_settings.html lines 178, 191)
    display_total_paid: str = "$0.00"  # Pre-formatted sum of all payments
    display_total_unpaid: str = "$0.00"  # Pre-formatted sum of all outstanding
    current_student_count: int = 0  # Count of students current on rent (up_to_date + outstanding)
    behind_student_count: int = 0  # Count of students behind on rent (past_due_grace + past_due_overdue)


def build_rent_policy_projection(
    settings: RentSettings | None,
    *,
    due_date,
    coverage_due_date=None,
    upcoming_due_date=None,
    now_utc: datetime | None = None,
    total_paid: Decimal = Decimal('0.00'),
    has_waiver: bool = False,
) -> dict:
    """Compute the shared rent projection used by the view and payment route."""
    now_utc = now_utc or datetime.now(timezone.utc)
    amount_due = Decimal(str(settings.rent_amount)) if settings and settings.rent_amount is not None else Decimal('0.00')
    grace_period_days = int(settings.grace_period_days) if settings and settings.grace_period_days is not None else 0
    grace_end = due_date + timedelta(days=grace_period_days) if due_date else None
    late_fee = Decimal('0.00')
    if grace_end and now_utc > grace_end and total_paid < amount_due:
        late_fee = Decimal(str(settings.late_penalty_amount)) if settings and settings.late_penalty_amount is not None else Decimal('0.00')
    total_due = amount_due + late_fee
    remaining_amount = max(Decimal('0.00'), total_due - total_paid)
    rent_is_active = bool(coverage_due_date and now_utc >= coverage_due_date)
    if not rent_is_active and upcoming_due_date and settings and settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start = upcoming_due_date - timedelta(days=settings.bill_preview_days)
        rent_is_active = now_utc >= preview_start and now_utc < upcoming_due_date
    is_satisfied = has_waiver or (total_paid >= total_due)
    is_past_due = (not is_satisfied) and bool(grace_end and now_utc > grace_end)
    is_preview = (not is_satisfied) and bool(due_date and now_utc < due_date)
    return {
        'amount_due': amount_due,
        'grace_end': grace_end,
        'late_fee': late_fee,
        'total_due': total_due,
        'remaining_amount': remaining_amount,
        'rent_is_active': rent_is_active,
        'is_satisfied': is_satisfied,
        'is_past_due': is_past_due,
        'is_preview': is_preview,
        'is_preview_period': is_preview,
    }


def _resolve_rent_settings_for_policy_uuid(policy_uuid: str | None) -> RentSettings | None:
    if not policy_uuid:
        return None
    return db.session.query(RentSettings).filter_by(policy_uuid=policy_uuid).first()


def build_empty_student_obligation_view(
    seat_id: int,
    class_id: str,
    obligation_type: str,
    current_block: str = 'A',
) -> StudentObligationView:
    """Return a valid empty view for surfaces that need to render a no-assessment state."""
    return StudentObligationView(
        obligation_type=obligation_type,
        seat_id=seat_id,
        class_id=class_id,
        current_block=current_block,
        current_period={
            'due_date': None,
            'grace_end': None,
            'amount_due': Decimal('0.00'),
            'amount_paid': Decimal('0.00'),
            'amount_waived': False,
            'balance': Decimal('0.00'),
            'remaining_amount': Decimal('0.00'),
            'total_paid': Decimal('0.00'),
            'total_due': Decimal('0.00'),
            'is_paid': False,
            'is_waived': False,
            'is_past_due': False,
            'is_late': False,
            'is_preview': False,
            'is_preview_period': False,
            'rent_is_active': False,
            'days_until_due': None,
            'days_overdue': None,
        },
        period_status={},
        prior_obligations=[],
        payment_history=[],
        active_waivers=[],
        totals={
            'total_owed': Decimal('0.00'),
            'total_paid_all_time': Decimal('0.00'),
            'total_waived': 0,
        },
        settings={
            'amount_expected': Decimal('0.00'),
            'late_fee': None,
            'grace_period_days': 0,
            'frequency': 'monthly',
            'frequency_type': 'monthly',
            'allow_incremental_payment': False,
            'custom_frequency_value': None,
            'custom_frequency_unit': None,
        },
        status_counts={'SATISFIED': 0, 'OUTSTANDING': 0, 'PAST_DUE': 0},
    )


def build_student_obligation_view(
    seat_id: int,
    class_id: str,
    obligation_type: str,
    current_block: str = 'A',  # Period identifier
) -> StudentObligationView | None:
    """
    Construct a complete obligation view for one student, any obligation type.

    Composes:
    - All assessments for this (seat, class, obligation_type)
    - Satisfaction events (PAYMENT, WAIVED)
    - Bill cycles for temporal boundaries
    - ClassConfig for grace_period
    - Ledger for authoritative payment amounts

    Returns None if no assessments found.
    """
    from app.services import obligations_service

    # Step 1: Get class-scoped rent settings for the shared rent projection
    class_econ = db.session.query(ClassEconomy).filter_by(class_id=class_id).first()
    if not class_econ:
        return None

    # Step 2: Get all assessments for this (seat, class, obligation_type)
    assessments = obligations_service.get_assessment_events_for_seat_class(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type=obligation_type,
    )

    if not assessments:
        return None

    # Step 3: Separate into ASSESSMENT and (PAYMENT/WAIVED) events
    assessment_events = [a for a in assessments if a.event_type == 'ASSESSMENT']
    if not assessment_events:
        return None

    # Step 4: Process each assessment to derive satisfaction
    current_period = {}
    period_status = {}
    prior_obligations = []
    payment_history_all = []
    active_waivers = []
    total_paid_all_time = Decimal('0.00')
    total_waived_count = 0
    status_counts = {'SATISFIED': 0, 'OUTSTANDING': 0, 'PAST_DUE': 0}

    # Assume most recent ASSESSMENT is "current period"
    current_assessment = assessment_events[-1] if assessment_events else None
    current_rent_settings = None
    if current_assessment and current_assessment.bill_cycle:
        current_rent_settings = _resolve_rent_settings_for_policy_uuid(current_assessment.bill_cycle.policy_uuid)

    for idx, assessment in enumerate(assessment_events):
        # Get satisfaction events for this assessment
        satisfaction_events = obligations_service.get_satisfaction_events(assessment.correlation_id)

        # Compute total_paid from PAYMENT events via Ledger
        total_paid = Decimal('0.00')
        has_waiver = False
        payment_events_for_assessment = []

        for event in satisfaction_events:
            if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
                txn = db.session.get(Transaction, event.ledger_transaction_id)
                if txn and txn.status != 'void':
                    total_paid += Decimal(str(txn.amount))
                    payment_history_all.append({
                        'date': event.timestamp,
                        'amount': Decimal(str(txn.amount)),
                        'type': 'PAYMENT',
                        'status': 'completed',
                        'correlation_id': assessment.correlation_id,
                    })
                    payment_events_for_assessment.append(event)
            elif event.event_type == 'WAIVED':
                has_waiver = True
                total_waived_count += 1
                active_waivers.append(event)
                payment_history_all.append({
                    'date': event.timestamp,
                    'amount': Decimal('0.00'),
                    'type': 'WAIVED',
                    'status': 'completed',
                    'correlation_id': assessment.correlation_id,
                })

        total_paid_all_time += total_paid

        # Get bill_cycle for this assessment to find due_date
        bill_cycle = None
        if assessment.bill_cycle_id:
            bill_cycle = db.session.get(BillCycle, assessment.bill_cycle_id)

        due_date = bill_cycle.next_assessment_at if bill_cycle else assessment.timestamp
        rent_settings = _resolve_rent_settings_for_policy_uuid(getattr(bill_cycle, 'policy_uuid', None))
        projection = build_rent_policy_projection(
            rent_settings if obligation_type == 'RENT' else None,
            due_date=due_date,
            now_utc=datetime.now(timezone.utc),
            total_paid=total_paid,
            has_waiver=has_waiver,
        )
        amount_due = projection['amount_due'] if obligation_type == 'RENT' else Decimal('0.00')
        grace_end = projection['grace_end']
        late_fee = projection['late_fee']
        remaining_amount = projection['remaining_amount']
        is_satisfied = projection['is_satisfied']
        is_past_due = projection['is_past_due']
        is_preview = projection['is_preview']
        balance = (amount_due + late_fee) - total_paid if obligation_type == 'RENT' else (Decimal('0.00') - total_paid)

        # Update status counts
        if is_satisfied:
            status_counts['SATISFIED'] += 1
        elif is_past_due:
            status_counts['PAST_DUE'] += 1
        else:
            status_counts['OUTSTANDING'] += 1

        days_until_due = None
        if is_preview and due_date:
            delta = due_date - now_utc
            days_until_due = delta.days

        days_overdue = None
        if is_past_due and grace_end:
            delta = now_utc - grace_end
            days_overdue = delta.days

        period_info = {
            'due_date': due_date,
            'grace_end': grace_end,
            'amount_due': amount_due,
            'amount_paid': total_paid,
            'amount_waived': has_waiver,
            'balance': balance,
            'remaining_amount': remaining_amount,
            'total_paid': total_paid,
            'total_due': amount_due + late_fee if obligation_type == 'RENT' else amount_due,  # Alias for template compatibility
            'is_paid': remaining_amount <= Decimal('0.00'),
            'is_waived': has_waiver,
            'is_past_due': is_past_due,
            'is_late': is_past_due,  # Alias for template
            'is_preview': is_preview,
            'is_preview_period': is_preview,  # Alias for template
            'rent_is_active': projection['rent_is_active'],
            'days_until_due': days_until_due,
            'days_overdue': days_overdue,
            'late_fee': late_fee,
        }

        # If this is the current assessment, set as current_period
        if assessment == current_assessment:
            current_period = period_info
            # Add current period to period_status keyed by current_block
            period_status[current_block] = period_info
        else:
            # Prior obligation
            prior_obligations.append({
                'period': assessment.timestamp.strftime('%B %Y') if assessment.timestamp else 'Unknown',
                'amount': amount_due,
                'status': 'paid' if period_info['is_paid'] else ('waived' if has_waiver else 'outstanding'),
                'due_date': due_date,
                'is_past_due': is_past_due,
            })

    # Sort payment_history by date descending
    payment_history_all.sort(key=lambda x: x['date'], reverse=True)

    # Build settings dict (from ClassConfig, not rent/insurance settings)
    settings = {
        'amount_expected': (
            Decimal(str(current_rent_settings.rent_amount))
            if obligation_type == 'RENT' and current_rent_settings and current_rent_settings.rent_amount is not None
            else Decimal('0.00')
        ),
        'late_fee': Decimal(str(current_rent_settings.late_penalty_amount)) if current_rent_settings and current_rent_settings.late_penalty_amount is not None else None,
        'grace_period_days': current_rent_settings.grace_period_days if current_rent_settings else 0,
        'frequency': current_rent_settings.frequency_type if current_rent_settings else 'monthly',
        'frequency_type': current_rent_settings.frequency_type if current_rent_settings else 'monthly',
        'allow_incremental_payment': bool(current_rent_settings.allow_incremental_payment) if current_rent_settings else False,
        'custom_frequency_value': current_rent_settings.custom_frequency_value if current_rent_settings else None,
        'custom_frequency_unit': current_rent_settings.custom_frequency_unit if current_rent_settings else None,
    }

    # Compute totals
    total_owed = Decimal('0.00')
    if current_period:
        total_owed += current_period.get('balance', Decimal('0.00'))
    for prior in prior_obligations:
        if prior['status'] == 'outstanding':
            total_owed += prior['amount']

    totals = {
        'total_owed': total_owed,
        'total_paid_all_time': total_paid_all_time,
        'total_waived': total_waived_count,
    }

    return StudentObligationView(
        obligation_type=obligation_type,
        seat_id=seat_id,
        class_id=class_id,
        current_block=current_block,
        current_period=current_period,
        period_status=period_status,
        prior_obligations=prior_obligations,
        payment_history=payment_history_all,
        active_waivers=active_waivers,
        totals=totals,
        settings=settings,
        status_counts=status_counts,
    )


def build_class_obligation_summary(
    class_id: str,
    obligation_type: str,
) -> ClassObligationSummary | None:
    """
    Construct a summary view of all students' obligations in a class.

    For each seat in class:
    - Call build_student_obligation_view()
    - Extract status
    - Aggregate into status_breakdown buckets

    Returns ClassObligationSummary with roll-up counts and per-student rows.
    """
    from app.services import obligations_service

    # Step 1: List all seats in this class
    class_econ = db.session.query(ClassEconomy).filter_by(class_id=class_id).first()
    if not class_econ:
        return None

    seats = db.session.query(Seat).filter_by(class_id=class_econ.class_id).all()
    if not seats:
        seats = []

    # Step 2: For each seat, build view and extract status
    student_rows = []
    status_counts = {
        'up_to_date': 0,
        'outstanding': 0,
        'past_due_grace': 0,
        'past_due_overdue': 0,
    }

    for seat in seats:
        view = build_student_obligation_view(seat.id, class_id, obligation_type)
        if not view:
            # No obligations for this seat yet
            continue

        current = view.current_period
        if not current:
            continue

        # Map to status bucket
        if current.get('is_paid') or current.get('is_waived'):
            status = 'up_to_date'
            status_counts['up_to_date'] += 1
        elif current.get('is_preview'):
            status = 'outstanding'
            status_counts['outstanding'] += 1
        elif current.get('is_past_due'):
            # TODO: Distinguish between grace period and truly overdue
            # For now, lump all past_due together
            status = 'past_due_overdue'
            status_counts['past_due_overdue'] += 1
        else:
            status = 'outstanding'
            status_counts['outstanding'] += 1

        # Get student name from IdentityProfile
        profile = db.session.query(IdentityProfile).filter_by(seat_id=seat.id).first()
        if profile:
            student_name = f"{profile.first_name} {profile.last_name}".strip()
        else:
            student_name = f"Seat {seat.id}"

        student_rows.append({
            'seat_id': seat.id,
            'student_name': student_name,
            'status': status,
            'due_date': current.get('due_date'),
            'amount_due': current.get('amount_due', Decimal('0.00')),
            'amount_paid': current.get('amount_paid', Decimal('0.00')),
            'balance': current.get('balance', Decimal('0.00')),
            'days_overdue': current.get('days_overdue'),
            'is_waived': current.get('is_waived', False),
        })

    now_utc = datetime.now(timezone.utc)

    return ClassObligationSummary(
        class_id=class_id,
        obligation_type=obligation_type,
        summary_date=now_utc,
        status_breakdown=status_counts,
        student_rows=student_rows,
    )


# ============================================================================
# Rent-Specific View Models (Phase 5: Read Models and Projections)
# ============================================================================

@dataclass(frozen=True)
class RentAssessmentView:
    """Single rent obligation assessment with derived status."""
    correlation_id: str
    assessment_id: int
    seat_id: int
    class_id: str
    due_at: object  # datetime
    assessed_amount: Decimal
    is_satisfied: bool
    is_outstanding: bool
    is_past_due: bool
    total_paid: Decimal
    amount_waived: bool
    payment_events: list
    waiver_event: object  # ObligationAssessment or None


@dataclass(frozen=True)
class RentStatusView:
    """Aggregated rent status for a seat in a class."""
    seat_id: int
    class_id: str
    all_assessments: list[RentAssessmentView]
    current_period_assessment: RentAssessmentView | None
    current_period_satisfied: bool
    active_waivers: list[object]  # List of WAIVED events
    total_paid_all_periods: Decimal
    total_assessed_all_periods: Decimal
    payment_history: list[object]  # Chronological list of events


def get_rent_assessments_for_seat_class(
    seat_id: int,
    class_id: str,
) -> list[RentAssessmentView]:
    """
    Get all rent ASSESSMENT events for a seat in a class with derived status.

    Per DOM-OBL-001: Returns immutable assessment facts with computed satisfaction.
    Returns in chronological order (created_at ascending).

    Args:
        seat_id: The seat receiving rent obligations
        class_id: The class scope

    Returns:
        List of RentAssessmentView objects
    """
    from app.services import obligations_service

    # Retrieve all rent ASSESSMENT events for this seat/class
    assessments = obligations_service.get_assessment_events_for_seat_class(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type='RENT'
    )

    result = []
    for assessment in assessments:
        if assessment.event_type != 'ASSESSMENT':
            continue

        # Get satisfaction events for this assessment
        satisfaction_events = obligations_service.get_satisfaction_events(assessment.correlation_id)

        # Compute paid amount from PAYMENT events via Ledger
        total_paid = Decimal('0.00')
        payment_events = []
        has_waiver = False
        waiver_event = None

        for event in satisfaction_events:
            if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
                # Read Ledger truth via FK
                txn = db.session.get(Transaction, event.ledger_transaction_id)
                if txn and txn.status != 'void':
                    total_paid += Decimal(str(txn.amount))
                payment_events.append(event)
            elif event.event_type == 'WAIVED':
                has_waiver = True
                waiver_event = event

        # Derive satisfaction
        assessed_amount = assessment.assessed_at or Decimal('0.00')
        is_satisfied = has_waiver or (total_paid >= Decimal(str(assessed_amount)))
        is_outstanding = not is_satisfied

        # Temporal check for past-due (caller can also check this via due_at)
        is_past_due = (
            is_outstanding
            and assessment.due_at
            and db.session.query(db.func.now()).scalar() > assessment.due_at
        )

        view = RentAssessmentView(
            correlation_id=assessment.correlation_id,
            assessment_id=assessment.id,
            seat_id=seat_id,
            class_id=class_id,
            due_at=assessment.due_at,
            assessed_amount=Decimal(str(assessed_amount)),
            is_satisfied=is_satisfied,
            is_outstanding=is_outstanding,
            is_past_due=is_past_due,
            total_paid=total_paid,
            amount_waived=has_waiver,
            payment_events=payment_events,
            waiver_event=waiver_event,
        )
        result.append(view)

    return result


def get_rent_status_projection(
    seat_id: int,
    class_id: str,
    current_period_due_at: object = None,
) -> RentStatusView:
    """
    Get aggregated rent status for a seat in a class.

    Composes:
    - All rent ASSESSMENT events
    - Payment/waiver history
    - Current period identification
    - Derived satisfaction state

    Args:
        seat_id: The seat
        class_id: The class scope
        current_period_due_at: Optional datetime to identify "current" period for display

    Returns:
        Complete rent status projection
    """
    assessments = get_rent_assessments_for_seat_class(seat_id, class_id)

    # Find active waivers
    active_waivers = [a.waiver_event for a in assessments if a.waiver_event]

    # Aggregate totals
    total_paid = sum(a.total_paid for a in assessments)
    total_assessed = sum(a.assessed_amount for a in assessments)

    # Identify current period (if provided)
    current_period_assessment = None
    if current_period_due_at:
        for a in assessments:
            if a.due_at == current_period_due_at:
                current_period_assessment = a
                break

    # Build chronological payment history from all events
    payment_history = []
    for assessment in assessments:
        payment_history.extend(assessment.payment_events)
        if assessment.waiver_event:
            payment_history.append(assessment.waiver_event)

    # Sort by created_at
    payment_history.sort(key=lambda e: e.created_at if hasattr(e, 'created_at') else '', reverse=True)

    return RentStatusView(
        seat_id=seat_id,
        class_id=class_id,
        all_assessments=assessments,
        current_period_assessment=current_period_assessment,
        current_period_satisfied=(current_period_assessment.is_satisfied if current_period_assessment else False),
        active_waivers=active_waivers,
        total_paid_all_periods=total_paid,
        total_assessed_all_periods=total_assessed,
        payment_history=payment_history,
    )


# ============================================================================
# Phase 1 Display Formatting Helpers (audit violations: pre-format dates/amounts)
# ============================================================================

def add_display_formatting_to_student_obligation_view(
    view: StudentObligationView | None,
) -> StudentObligationView | None:
    """
    Add pre-formatted display fields to StudentObligationView.

    Eliminates template-level date/currency formatting (audit violations:
    student_rent.html line 142 strftime, admin_rent_settings.html nested ORM access).

    Returns a new view with display fields populated.
    """
    if view is None:
        return view

    # Format current period dates and amounts
    display_due_date = None
    if view.current_period and view.current_period.get('due_date'):
        due_date = view.current_period['due_date']
        if isinstance(due_date, datetime):
            display_due_date = due_date.strftime("%B %d, %Y")

    display_amount_due = "$0.00"
    if view.current_period and view.current_period.get('amount_due') is not None:
        amount = Decimal(str(view.current_period['amount_due']))
        display_amount_due = f"${amount:.2f}"

    display_total_due = "$0.00"
    if view.current_period and view.current_period.get('total_due') is not None:
        amount = Decimal(str(view.current_period['total_due']))
        display_total_due = f"${amount:.2f}"

    display_amount_paid = "$0.00"
    if view.current_period and view.current_period.get('amount_paid') is not None:
        amount = Decimal(str(view.current_period['amount_paid']))
        display_amount_paid = f"${amount:.2f}"

    display_remaining = "$0.00"
    if view.current_period and view.current_period.get('remaining_amount') is not None:
        amount = Decimal(str(view.current_period['remaining_amount']))
        display_remaining = f"${amount:.2f}"

    # Create new view with display fields populated using dataclasses.replace
    return replace(
        view,
        display_current_due_date=display_due_date,
        display_amount_due=display_amount_due,
        display_total_due=display_total_due,
        display_amount_paid=display_amount_paid,
        display_remaining_amount=display_remaining,
    )


def add_display_formatting_to_class_obligation_summary(
    summary: ClassObligationSummary | None,
) -> ClassObligationSummary | None:
    """
    Add pre-formatted display fields to ClassObligationSummary.

    Pre-formats totals and student counts for display (audit violations:
    admin_rent_settings.html lines 178, 191 ORM property aggregation in template).

    Returns a new summary with display fields populated.
    """
    if summary is None:
        return summary

    # Compute display totals from status_breakdown and student_rows
    total_paid = Decimal('0.00')
    total_unpaid = Decimal('0.00')
    current_student_count = 0
    behind_student_count = 0

    for row in summary.student_rows or []:
        if row.get('amount_paid'):
            total_paid += Decimal(str(row['amount_paid']))
        if row.get('balance') and row['balance'] > 0:
            total_unpaid += Decimal(str(row['balance']))

        # Count students by status (mirrors template filtering at lines 337, 365)
        status = row.get('status')
        if status in ['up_to_date', 'outstanding']:
            current_student_count += 1
        elif status in ['past_due_grace', 'past_due_overdue']:
            behind_student_count += 1

    display_total_paid = f"${total_paid:.2f}"
    display_total_unpaid = f"${total_unpaid:.2f}"

    # Create new summary with display fields using dataclasses.replace
    return replace(
        summary,
        display_total_paid=display_total_paid,
        display_total_unpaid=display_total_unpaid,
        current_student_count=current_student_count,
        behind_student_count=behind_student_count,
    )
