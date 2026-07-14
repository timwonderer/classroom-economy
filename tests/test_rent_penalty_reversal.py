"""
Tests for rent penalty reversal and cycle rate locking.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_sysadmin, seed_canonical_admin
from app import db
from app.hash_utils import get_random_salt, hash_username
from app.feats.base import FEATContext
from app.models import (
    User,
    UserRole,
    ClassEconomy,
    IdentityProfile,
    RentSettings,
    Seat,
    Transaction,
    ObligationAssessment,
)
from app.services.obligations_service import record_rent_payment, record_rent_waiver
from app.routes.student import (
    RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
    _get_locked_rent_amount_for_class_cycle,
    _is_student_coverage_period_paid,
)
from tests.helpers.class_scope import make_student_identity
from tests.helpers.canonical_session import set_canonical_context

def _has_active_rent_waiver(student_id, class_id, coverage_due_date):
    from app.models import Seat
    from app.routes.student import _has_active_rent_waiver_v2
    seat = Seat.query.filter_by(user_id=student_id, class_id=class_id).first()
    if not seat:
        return False
    return _has_active_rent_waiver_v2(seat.id, class_id, coverage_due_date)

def _is_student_coverage_period_paid_wrapper(settings, student_id, block, class_id, coverage_due_date):
    from app.models import Seat
    seat = Seat.query.filter_by(user_id=student_id, class_id=class_id).first()
    if not seat:
        return False
    return _is_student_coverage_period_paid(settings, seat.id, class_id, coverage_due_date)



def _login_admin(client, user_id, class_id):
    teacher_seat = Seat.query.filter_by(user_id=user_id, class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )


def _make_admin_with_block(join_code="LOCKA1", block="A", suffix="rv"):
    from tests.helpers.class_scope import create_class_scope, make_student_identity
    from app.models import RentPolicyVersion

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"rent-reversal:admin:{join_code}"):
        admin = seed_canonical_admin(f"rent_admin_{suffix}_{join_code.lower()}", "TESTSECRET123456").user
        db.session.flush()

        economy = create_class_scope(teacher_user=admin, join_code=join_code)
        teacher_seat = Seat.query.filter_by(class_id=economy.class_id, role="teacher").first()
        assert teacher_seat is not None
        teacher_profile = IdentityProfile.query.filter_by(seat_id=teacher_seat.id).first()
        if teacher_profile is None:
            teacher_profile = IdentityProfile(profile_type="teacher", first_name="Teacher", last_name="T")
            teacher_profile.seat_id = teacher_seat.id
            db.session.add(teacher_profile)

        settings = RentSettings(
            class_id=economy.class_id,
            rent_amount=Decimal("100.00"),
            frequency_type="monthly",
            grace_period_days=3,
            late_penalty_amount=Decimal("10.00"),
            late_penalty_type="once",
        )
        db.session.add(settings)
        db.session.flush()
        version = settings.create_policy_version()
        db.session.add(version)
        db.session.flush()
        settings.active_version_id = version.id
        settings.next_version_id = None
        db.session.flush()

    return admin, settings


def _make_student(suffix="s", class_id=None):
    if not class_id:
        raise ValueError("class_id is required to resolve the canonical class scope")
    return make_student_identity(class_id=class_id, first_name="Test", last_name="R")


def _add_payment(student, user_id, class_id, amount_paid, late_fee, payment_date, coverage_due_date, *, is_void=False):
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_id).first()
    assert seat is not None
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    assert settings is not None and settings.active_version_id is not None
    with FEATContext("FEAT-LED-001", idempotency_key=f"rent-reversal:payment:{seat.id}:{payment_date.isoformat()}"):
        transaction = Transaction(
            seat_id=seat.id,
            class_id=seat.class_id,
            user_id=seat.user_id,
            amount=-amount_paid,
            timestamp=payment_date,
            account_type="checking",
            type="Rent Payment",
            description="Rent payment",
            is_void=is_void,
        )
        db.session.add(transaction)
        db.session.flush()
        payment = record_rent_payment(
            seat_id=seat.id,
            class_id=seat.class_id,
            period="A",
            amount_paid=amount_paid,
            period_month=payment_date.month,
            period_year=payment_date.year,
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            was_late=late_fee > Decimal("0.00"),
            late_fee_charged=late_fee,
            coverage_start_time=coverage_due_date,
            coverage_end_time=coverage_due_date,
            cycle_idempotency_key=f"rent-reversal:cycle:{seat.id}:{coverage_due_date.isoformat()}",
            rent_policy_version_id=settings.active_version_id,
            transaction_id=transaction.id,
        )
        payment.satisfaction.satisfied_at = payment_date
        db.session.flush()
    return payment


def test_locked_rate_uses_first_valid_payer_base(client):
    admin, settings = _make_admin_with_block("LOCKR1", suffix="first")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    student_a = _make_student("a", class_id=settings.class_id)
    student_b = _make_student("b", class_id=settings.class_id)

    _add_payment(student_a, admin.id, settings.class_id, Decimal("100.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage)
    _add_payment(student_b, admin.id, settings.class_id, Decimal("150.00"), Decimal("0.00"), datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc), coverage)

    assert _get_locked_rent_amount_for_class_cycle(settings.class_id, coverage) == Decimal("100.00")


def test_locked_rate_is_policy_version_based(client):
    admin, settings = _make_admin_with_block("LOCKRV", suffix="void")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    student_a = _make_student("va", class_id=settings.class_id)
    student_b = _make_student("vb", class_id=settings.class_id)

    _add_payment(student_a, admin.id, settings.class_id, Decimal("80.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage, is_void=True)
    _add_payment(student_b, admin.id, settings.class_id, Decimal("120.00"), Decimal("0.00"), datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc), coverage)

    assert _get_locked_rent_amount_for_class_cycle(settings.class_id, coverage) == Decimal("100.00")


def test_waiver_marks_coverage_period_as_paid(client):
    admin, settings = _make_admin_with_block("WAIV1", suffix="waiver")
    student = _make_student("waived", class_id=settings.class_id)
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    with FEATContext("FEAT-IDEN-001", idempotency_key="rent-reversal:waiver:WAIV1"):
        record_rent_waiver(
            seat_id=student.id,
            class_id=settings.class_id,
            waiver_start_date=coverage - timedelta(days=1),
            waiver_end_date=coverage + timedelta(days=5),
            periods_count=1,
            created_by_user_id=admin.id,
        )

    assert _has_active_rent_waiver(student.id, settings.class_id, coverage) is True
    assert _is_student_coverage_period_paid_wrapper(settings, student.id, "A", settings.class_id, coverage) is True


def test_reverse_cycle_penalties_refunds_only_misapplied_fees(client, monkeypatch):
    admin, settings = _make_admin_with_block("REVFEE", suffix="reverse")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routes.admin.utc_now', lambda: datetime(2026, 3, 15, tzinfo=timezone.utc))
    on_time_student = _make_student("ontime", class_id=settings.class_id)
    late_student = _make_student("late", class_id=settings.class_id)

    _add_payment(
        on_time_student,
        admin.id,
        settings.class_id,
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
        coverage,
    )
    _add_payment(
        late_student,
        admin.id,
        settings.class_id,
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        coverage,
    )

    with FEATContext("FEAT-ADMN-001", idempotency_key="rent-reversal:settings:REVFEE"):
        settings.rent_amount = Decimal("150.00")
        settings.updated_at = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
        db.session.flush()

    _login_admin(client, admin.id, settings.class_id)
    response = client.post('/admin/rent/reverse-cycle-penalties')

    assert response.status_code == 302

    refund_txns = Transaction.query.filter_by(
        class_id=settings.class_id,
        type="Rent Late Fee Reversal",
    ).all()
    assert len(refund_txns) == 1
    assert refund_txns[0].user_id == on_time_student.user_id
    assert refund_txns[0].amount == Decimal("10.00")

    on_time_payment = ObligationAssessment.query.filter_by(
        seat_id=on_time_student.id,
        class_id=settings.class_id,
        obligation_type="RENT",
    ).first()
    late_payment = ObligationAssessment.query.filter_by(
        seat_id=late_student.id,
        class_id=settings.class_id,
        obligation_type="RENT",
    ).first()
    assert on_time_payment is not None
    assert late_payment is not None
    assert on_time_payment.satisfaction is not None
    assert late_payment.satisfaction is not None
    assert on_time_payment.satisfaction.late_fee_charged == Decimal("0.00")
    assert on_time_payment.satisfaction.was_late is False
    assert late_payment.satisfaction.late_fee_charged == Decimal("10.00")
    assert late_payment.satisfaction.was_late is True
