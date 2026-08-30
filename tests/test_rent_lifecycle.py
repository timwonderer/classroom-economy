"""End-to-end Rent lifecycle tests (canonical entitlement path).

Covers the corrected rent architecture:

  RentSettings (schedule intent)
    -> rent_schedule_service (class-local date arithmetic)
    -> canonical temporal resolver (class-local-date -> UTC materialization only)
    -> BillCycle (resolved concrete instants, materialized ONCE)
    -> reconcile_rent (FEAT-OBL-002, instant comparison, idempotent)
    -> rent_payment_feat (FEAT-OBL-001, Ledger + PAYMENT + PERK grant atomically)

Key invariants asserted:
  - Reconciliation creates cycle 1 + one RENT ASSESSMENT per claimed student,
    idempotently (re-run is a NOOP producing no duplicates).
  - A later RentSettings change does NOT retroactively move an already
    materialized cycle's three boundaries (INV-CORE-000 non-retroactivity).
  - Catch-up advances to cycle 2 and expires the prior cycle's PERK hall passes
    at the rent boundary.
  - rent_payment_feat posts the ledger debit, records the PAYMENT event, and
    grants the configured PERK hall passes; replay is idempotent; and it refuses
    to overdraft (INSUFFICIENT_FUNDS).

Uses the canonical test initializer (SPEC-TEST-001) and injects
``reference_time_utc`` rather than reading any wall clock (SPEC-TIME-001).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import BillCycle, ObligationAssessment, EntitlementEvent
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from app.feats.rent_payment_feat import execute_rent_payment, execute_rent_bill_payment
from app.services import obligations_service
from tests.helpers.classroom_initializer import initialize
from tests.helpers.class_domain import enable_class_feature, customize_rent_settings
from tests.helpers.ledger import create_ledger_idempotent_transaction


def _fund_seat(classroom, student, amount=Decimal("100.00")):
    """Fund a seat's checking so rent/late-fee payments can settle."""
    seat_id = student.seat.id
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
        create_ledger_idempotent_transaction(
            idempotency_key=f"fund-seat:{seat_id}",
            seat_id=seat_id,
            class_id=classroom.class_id,
            user_id=student.user.id,
            amount=amount,
            account_type="checking",
            type="payroll",
            description="Test funding",
        )


# Deterministic reference instants (all UTC). Class default tz is
# America/Los_Angeles, so a Jan-1 12:00 UTC instant is still Jan 1 class-local.
_FIRST_DUE = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_INITIAL = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_T_BEFORE_BOUNDARY = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
_T_AFTER_BOUNDARY = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)

_HALL_PASS_GRANTS = [{"entitlement_type": "HALL_PASS", "quantity": 2}]


def _setup_rent_class(classroom):
    """Enable rent and configure a deterministic monthly schedule + PERK grants.

    Must be called inside an app context. Customizes the canonical, already
    provisioned RentSettings row (one-rent-policy-per-class invariant).
    """
    enable_class_feature(class_id=classroom.class_id, feature="rent")
    settings = customize_rent_settings(
        classroom.class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=_FIRST_DUE,
        grace_period_days=3,
        rent_amount=Decimal("50.00"),
        satisfaction_benefits=_HALL_PASS_GRANTS,
        # Late fees OFF by default in this baseline (amount == 0 is the disable
        # signal, matching v1). Late-fee tests opt in with an explicit penalty
        # amount so cycle-mechanics tests stay isolated from late-fee accrual.
        late_penalty_amount=Decimal("0.00"),
    )
    return settings


def _rent_assessments(class_id):
    return (
        ObligationAssessment.query.filter_by(
            class_id=class_id, obligation_type="RENT", event_type="ASSESSMENT"
        )
        .order_by(ObligationAssessment.id.asc())
        .all()
    )


def _bill_cycles(class_id):
    return (
        BillCycle.query.filter_by(class_id=class_id)
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def _active_perk_hall_passes(class_id, seat_id):
    """GRANTED PERK HALL_PASS entitlement events with no terminal event yet."""
    granted = (
        EntitlementEvent.query.filter_by(
            class_id=class_id,
            target_seat_id=seat_id,
            entitlement_type="HALL_PASS",
            acquisition_type="PERK",
            event_type="GRANTED",
        )
        .all()
    )
    active = []
    for ev in granted:
        terminal = EntitlementEvent.query.filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_id == ev.entitlement_id,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        ).first()
        if terminal is None:
            active.append(ev)
    return active


class TestRentReconciliation:
    def test_initial_reconcile_creates_cycle_and_assessments(self, app):
        """First reconcile creates cycle 1 + one RENT ASSESSMENT per claimed seat."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)

            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_INITIAL
            )

            assert result.reason == "CREATED_INITIAL"
            assert result.cycles_created == [1]

            cycles = _bill_cycles(classroom.class_id)
            assert len(cycles) == 1
            assert cycles[0].cycle_number == 1
            assert cycles[0].grace_boundary_at is not None

            assessments = _rent_assessments(classroom.class_id)
            roster_size = len(classroom.students)
            assert roster_size > 0
            assert len(assessments) == roster_size
            # correlation lineage per DOM-OBL-001 convention.
            for a in assessments:
                assert a.correlation_id.endswith(":cycle:1")
                assert a.policy_uuid is not None

    def test_reconcile_is_idempotent(self, app):
        """Re-running reconcile before the boundary is a NOOP with no duplicates."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            first_cycles = len(_bill_cycles(classroom.class_id))
            first_assessments = len(_rent_assessments(classroom.class_id))

            second = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )

            assert second.reason == "NOOP"
            assert second.cycles_created == []
            assert second.assessments_created == 0
            assert len(_bill_cycles(classroom.class_id)) == first_cycles
            assert len(_rent_assessments(classroom.class_id)) == first_assessments

    def test_settings_change_does_not_move_existing_cycle_boundaries(self, app):
        """A later RentSettings change must not retroactively move cycle 1 boundaries."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)

            cycle1 = _bill_cycles(classroom.class_id)[0]
            frozen_boundary = cycle1.cycle_boundary_at
            frozen_next = cycle1.next_assessment_at
            frozen_grace = cycle1.grace_boundary_at

            # Mutate the schedule intent AFTER the cycle was materialized.
            customize_rent_settings(
                classroom.class_id,
                frequency_type="weekly",
                due_day_of_month=15,
                grace_period_days=10,
            )

            # Re-run reconcile still BEFORE the persisted boundary -> NOOP.
            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )
            assert result.reason == "NOOP"

            db.session.refresh(cycle1)
            assert cycle1.cycle_boundary_at == frozen_boundary
            assert cycle1.next_assessment_at == frozen_next
            assert cycle1.grace_boundary_at == frozen_grace

    def test_catchup_advances_cycle_and_expires_prior_perks(self, app):
        """Catch-up creates cycle 2 and expires the prior cycle's PERK hall passes."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            correlation_id = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            # Fund the seat and pay cycle-1 rent so PERK hall passes exist.
            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"fund-seat:{seat_id}",
                    seat_id=seat_id,
                    class_id=classroom.class_id,
                    user_id=student.user.id,
                    amount=Decimal("100.00"),
                    account_type="checking",
                    type="payroll",
                    description="Test funding",
                )
            pay = execute_rent_payment(
                classroom.class_id, seat_id, correlation_id,
                idempotency_key=f"rent-pay:{correlation_id}:cmd",
            )
            assert pay.success is True
            assert pay.passes_awarded == 2
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 2

            # Advance past the cycle-1 boundary -> cycle 2 + prior-cycle expiry.
            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_AFTER_BOUNDARY
            )

            assert 2 in result.cycles_created
            assert result.perks_expired >= 2
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 0


class TestRentPayment:
    def test_pay_rent_posts_debit_records_payment_and_grants_perks(self, app):
        """Happy path: ledger debit + PAYMENT event + PERK hall-pass grants."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            correlation_id = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"fund-seat:{seat_id}",
                    seat_id=seat_id,
                    class_id=classroom.class_id,
                    user_id=student.user.id,
                    amount=Decimal("100.00"),
                    account_type="checking",
                    type="payroll",
                    description="Test funding",
                )

            result = execute_rent_payment(
                classroom.class_id, seat_id, correlation_id,
                idempotency_key=f"rent-pay:{correlation_id}:cmd",
            )

            assert result.success is True, result.error_message
            assert result.already_satisfied is False
            assert result.amount_paid == Decimal("50.00")
            assert result.passes_awarded == 2
            assert result.transaction_id is not None

            payment = ObligationAssessment.query.filter_by(
                correlation_id=correlation_id, event_type="PAYMENT"
            ).first()
            assert payment is not None
            assert payment.ledger_transaction_id == result.transaction_id

            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 2

    def test_pay_rent_is_idempotent_on_replay(self, app):
        """Replaying a satisfied obligation neither re-charges nor re-grants."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            correlation_id = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
                create_ledger_idempotent_transaction(
                    idempotency_key=f"fund-seat:{seat_id}",
                    seat_id=seat_id,
                    class_id=classroom.class_id,
                    user_id=student.user.id,
                    amount=Decimal("100.00"),
                    account_type="checking",
                    type="payroll",
                    description="Test funding",
                )

            first = execute_rent_payment(
                classroom.class_id, seat_id, correlation_id,
                idempotency_key=f"rent-pay:{correlation_id}:cmd",
            )
            assert first.success is True

            payment_count_before = ObligationAssessment.query.filter_by(
                correlation_id=correlation_id, event_type="PAYMENT"
            ).count()
            perks_before = len(_active_perk_hall_passes(classroom.class_id, seat_id))

            # Same command key → a true replay of the same payment command.
            second = execute_rent_payment(
                classroom.class_id, seat_id, correlation_id,
                idempotency_key=f"rent-pay:{correlation_id}:cmd",
            )

            assert second.success is True
            assert second.already_satisfied is True

            payment_count_after = ObligationAssessment.query.filter_by(
                correlation_id=correlation_id, event_type="PAYMENT"
            ).count()
            assert payment_count_after == payment_count_before == 1
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == perks_before

    def test_pay_rent_refuses_to_overdraft(self, app):
        """An unfunded seat cannot pay rent (no overdraft on principal)."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            correlation_id = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            result = execute_rent_payment(
                classroom.class_id, seat_id, correlation_id,
                idempotency_key=f"rent-pay:{correlation_id}:cmd",
            )

            assert result.success is False
            assert result.error_code == "INSUFFICIENT_FUNDS"
            # No PAYMENT event and no PERK grants on refusal.
            assert ObligationAssessment.query.filter_by(
                correlation_id=correlation_id, event_type="PAYMENT"
            ).first() is None
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 0


def _late_fee_assessments(class_id, seat_id):
    return (
        ObligationAssessment.query.filter_by(
            class_id=class_id, seat_id=seat_id,
            obligation_type="LATE_FEE", event_type="ASSESSMENT",
        )
        .order_by(ObligationAssessment.id.asc())
        .all()
    )


class TestRentLateFees:
    """Late fees are their own immutable obligations that ARISE FROM delinquent rent."""

    def test_late_fee_assessed_once_past_grace_when_rent_unpaid(self, app):
        """Past grace with unpaid rent → one LATE_FEE obligation with its own
        correlation and a lawful source_correlation_id back to the rent."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )

            assert result.late_fees_created >= 1
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"
            late = _late_fee_assessments(classroom.class_id, seat_id)
            assert len(late) == 1
            # Own identity; lineage is a persisted reference, never string-parsed.
            assert late[0].correlation_id == f"{rent_corr}:late:1"
            assert late[0].source_correlation_id == rent_corr
            assert late[0].bill_cycle_id is not None
            # Amount resolves to the configured penalty, not the rent principal.
            assert obligations_service.resolve_assessment_amount(late[0]) == Decimal("10.00")

    def test_late_fee_once_is_idempotent(self, app):
        """Re-running reconcile past grace does not duplicate the once late fee."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)
            again = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )

            assert again.late_fees_created == 0
            assert len(_late_fee_assessments(classroom.class_id, seat_id)) == 1

    def test_no_late_fee_when_rent_paid(self, app):
        """A seat that paid its rent accrues no late fee, even past grace."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            _fund_seat(classroom, student)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"
            paid = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd",
            )
            assert paid.fully_paid is True

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)

            assert len(_late_fee_assessments(classroom.class_id, seat_id)) == 0

    def test_late_fee_recurring_accrues_multiple_periods(self, app):
        """Recurring penalty accrues one obligation per elapsed frequency window."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("5.00"),
                late_penalty_type="recurring",
                late_penalty_frequency_days=3,
            )
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            # Jan 15 is ~11 days past a Jan-4 grace boundary → several 3-day windows.
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)

            late = _late_fee_assessments(classroom.class_id, seat_id)
            assert len(late) >= 2
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"
            # Sequential, well-formed correlations; all share the lawful source ref.
            for n, a in enumerate(late, start=1):
                assert a.correlation_id == f"{rent_corr}:late:{n}"
                assert a.source_correlation_id == rent_corr

    def test_late_fee_disabled_when_penalty_amount_zero(self, app):
        """No penalty configured (amount 0) → no late fee obligations at all."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id, late_penalty_amount=Decimal("0.00"),
            )
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            result = execute_reconcile_rent(
                classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY
            )

            assert result.late_fees_created == 0
            assert len(_late_fee_assessments(classroom.class_id, seat_id)) == 0

    def test_late_fee_obligation_is_payable(self, app):
        """A LATE_FEE obligation can be settled through the payment FEAT; it grants
        no satisfaction PERKs (those are a RENT-only benefit)."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)
            _fund_seat(classroom, student)

            late = _late_fee_assessments(classroom.class_id, seat_id)[0]
            result = execute_rent_payment(
                classroom.class_id, seat_id, late.correlation_id,
                idempotency_key=f"late-pay:{late.correlation_id}:cmd",
            )

            assert result.success is True, result.error_message
            assert result.fully_paid is True
            assert result.amount_paid == Decimal("10.00")
            assert result.passes_awarded == 0  # late fee grants no perks
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 0


class TestRentPartialPayments:
    """Partial payments accumulate under ONE obligation correlation."""

    def test_partial_payments_share_one_correlation_and_satisfy(self, app):
        """REQUIRED regression: multiple PAYMENT events may share one assessment
        correlation, and their magnitudes sum to satisfy the obligation."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id, allow_incremental_payment=True,
            )
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            _fund_seat(classroom, student)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            first = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd-1",
                payment_amount=Decimal("20.00"),
            )
            second = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd-2",
                payment_amount=Decimal("30.00"),
            )

            assert first.success is True and first.fully_paid is False
            assert first.amount_paid == Decimal("20.00")
            assert second.success is True and second.fully_paid is True
            assert second.amount_paid == Decimal("30.00")

            payments = ObligationAssessment.query.filter_by(
                correlation_id=rent_corr, event_type="PAYMENT"
            ).all()
            # Two PAYMENT events, ONE shared correlation.
            assert len(payments) == 2
            assert {p.correlation_id for p in payments} == {rent_corr}
            assert obligations_service.get_paid_magnitude(rent_corr) == Decimal("50.00")

    def test_partial_grants_perks_only_on_fully_paid_transition(self, app):
        """PERKs are awarded exactly once, on the command that completes payment."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id, allow_incremental_payment=True,
            )
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            _fund_seat(classroom, student)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            first = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd-1",
                payment_amount=Decimal("20.00"),
            )
            assert first.passes_awarded == 0
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 0

            second = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd-2",
                payment_amount=Decimal("30.00"),
            )
            assert second.passes_awarded == 2
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == 2

    def test_partial_rejected_when_incremental_disabled(self, app):
        """A sub-total payment is refused when the class disables incremental pay."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id, allow_incremental_payment=False,
            )
            student = classroom.students[0]
            seat_id = student.seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            _fund_seat(classroom, student)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            result = execute_rent_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"rent-pay:{rent_corr}:cmd",
                payment_amount=Decimal("20.00"),
            )

            assert result.success is False
            assert result.error_code == "PARTIAL_NOT_ALLOWED"
            assert ObligationAssessment.query.filter_by(
                correlation_id=rent_corr, event_type="PAYMENT"
            ).first() is None


class TestRentViewLateFees:
    """The RENT student view surfaces late fees as a SEPARATE grouped list,
    never folded into the rent principal's remaining balance."""

    def test_rent_view_surfaces_late_fees_separately(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            from app.services.obligation_view_model import build_student_obligation_view

            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
            )
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)

            view = build_student_obligation_view(
                seat_id=seat_id, class_id=classroom.class_id, obligation_type="RENT",
            )

            # Rent principal remaining is unchanged by the late fee (not folded in).
            assert view.current_period["remaining_amount"] == Decimal("50.00")
            # Late fee surfaced as its own grouped row with lawful lineage.
            assert len(view.late_fees) == 1
            fee = view.late_fees[0]
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"
            assert fee["source_correlation_id"] == rent_corr
            assert fee["amount_due"] == Decimal("10.00")
            assert fee["is_paid"] is False
            assert view.late_fees_total_due == Decimal("10.00")

    def test_rent_view_has_no_late_fees_when_none_assessed(self, app):
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            from app.services.obligation_view_model import build_student_obligation_view

            _setup_rent_class(classroom)  # baseline: late fees off
            seat_id = classroom.students[0].seat.id

            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)

            view = build_student_obligation_view(
                seat_id=seat_id, class_id=classroom.class_id, obligation_type="RENT",
            )

            assert view.late_fees == []
            assert view.late_fees_total_due == Decimal("0.00")


class TestRentBillGroupPayment:
    """A rent bill (rent principal + its late fees) settles as one lineage."""

    def _prime_bill_with_late_fee(self, app, classroom):
        """Assess cycle-1 rent + a $10 once late fee for students[0]; fund the seat."""
        _setup_rent_class(classroom)
        customize_rent_settings(
            classroom.class_id,
            late_penalty_amount=Decimal("10.00"),
            late_penalty_type="once",
        )
        student = classroom.students[0]
        seat_id = student.seat.id
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
        execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)
        _fund_seat(classroom, student)
        return student, seat_id

    def test_full_bill_payment_settles_rent_and_late_fee(self, app):
        """Paying the bill in full satisfies both obligations; rent grants perks,
        the late fee grants none; the group is fully paid."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            student, seat_id = self._prime_bill_with_late_fee(app, classroom)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            result = execute_rent_bill_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"bill:{rent_corr}:cmd",
            )

            assert result.success is True, result.error_message
            assert result.fully_paid is True
            assert result.amount_paid == Decimal("60.00")  # 50 rent + 10 late fee
            assert result.passes_awarded == 2               # rent perks only
            assert result.remaining_after == Decimal("0.00")

            # Both obligations satisfied under their own correlations.
            assert obligations_service.get_paid_magnitude(rent_corr) == Decimal("50.00")
            assert obligations_service.get_paid_magnitude(f"{rent_corr}:late:1") == Decimal("10.00")

    def test_partial_bill_payment_applies_rent_first(self, app):
        """A partial bill payment settles the rent principal before any late fee."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            _setup_rent_class(classroom)
            customize_rent_settings(
                classroom.class_id,
                late_penalty_amount=Decimal("10.00"),
                late_penalty_type="once",
                allow_incremental_payment=True,
            )
            student = classroom.students[0]
            seat_id = student.seat.id
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_INITIAL)
            execute_reconcile_rent(classroom.class_id, reference_time_utc=_T_BEFORE_BOUNDARY)
            _fund_seat(classroom, student)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            # Pay $55 of the $60 bill: rent ($50) fully, late fee ($10) partially ($5).
            result = execute_rent_bill_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"bill:{rent_corr}:cmd",
                payment_amount=Decimal("55.00"),
            )

            assert result.success is True, result.error_message
            assert result.fully_paid is False
            assert result.amount_paid == Decimal("55.00")
            assert result.remaining_after == Decimal("5.00")
            assert obligations_service.get_paid_magnitude(rent_corr) == Decimal("50.00")
            assert obligations_service.get_paid_magnitude(f"{rent_corr}:late:1") == Decimal("5.00")

    def test_bill_payment_replay_is_idempotent(self, app):
        """Replaying the same bill command neither re-charges nor re-grants."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            student, seat_id = self._prime_bill_with_late_fee(app, classroom)
            rent_corr = f"rent:{classroom.class_id}:{seat_id}:cycle:1"

            first = execute_rent_bill_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"bill:{rent_corr}:cmd",
            )
            assert first.fully_paid is True

            payments_before = ObligationAssessment.query.filter(
                ObligationAssessment.event_type == "PAYMENT",
                ObligationAssessment.correlation_id.in_([rent_corr, f"{rent_corr}:late:1"]),
            ).count()
            perks_before = len(_active_perk_hall_passes(classroom.class_id, seat_id))

            second = execute_rent_bill_payment(
                classroom.class_id, seat_id, rent_corr,
                idempotency_key=f"bill:{rent_corr}:cmd",
            )

            assert second.success is True
            assert second.fully_paid is True
            assert second.amount_paid == Decimal("0.00")

            payments_after = ObligationAssessment.query.filter(
                ObligationAssessment.event_type == "PAYMENT",
                ObligationAssessment.correlation_id.in_([rent_corr, f"{rent_corr}:late:1"]),
            ).count()
            assert payments_after == payments_before
            assert len(_active_perk_hall_passes(classroom.class_id, seat_id)) == perks_before
