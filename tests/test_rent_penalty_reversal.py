"""
Tests for rent penalty reversal and cycle rate locking.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from tests.helpers.v2_fixtures import make_admin
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope, make_student_seat
from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import (
    Admin, ClassEconomy, IdentityProfile, RentPayment,
    RentSettings, RentWaiver, Seat, Student, Transaction, TransactionStatus,
)
from app.services.obligations_service import record_rent_payment, record_rent_waiver
from app.services.obligations_service import get_paid_rent_assessments_for_cycle
from app.routes.student import (
    RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
    _get_locked_rent_amount_for_join_code_cycle,
    _is_student_coverage_period_paid,
)

def _has_active_rent_waiver(seat_id, class_id, coverage_due_date):
    from app.routes.student import _has_active_rent_waiver_v2
    return _has_active_rent_waiver_v2(seat_id, class_id, coverage_due_date)

def _is_student_coverage_period_paid_wrapper(settings, seat_id, class_id, coverage_due_date):
    return _is_student_coverage_period_paid(settings, seat_id, class_id, coverage_due_date)


def _login_admin(client, admin, join_code, class_id):
    from app.models import ClassEconomy
    class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
    login_admin(
        client,
        admin.id,
        join_code,
        user_id=class_row.user_id if class_row else None,
        class_id=class_id,
    )


def _make_admin_with_block(join_code="LOCKA1", block="A", suffix="rv"):
    admin = make_admin(f"rent_admin_{suffix}_{join_code.lower()}", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    class_row = create_class_scope(
        teacher=admin,
        join_code=join_code,
        block=block,
        create_claimed_teacher_block=True,
    )
    db.session.flush()

    settings = RentSettings(
        class_id=class_row.class_id,
        block=block,
        is_enabled=True,
        rent_amount=Decimal("100.00"),
        frequency_type="monthly",
        grace_period_days=3,
        late_penalty_amount=Decimal("10.00"),
        late_penalty_type="once",
    )
    db.session.add(settings)
    db.session.commit()
    version = settings.create_policy_version()
    db.session.add(version)
    db.session.flush()
    settings.active_version_id = version.id
    db.session.commit()
    return admin, settings, class_row


def _make_student_seat_in_class(class_row, block="A", suffix="s"):
    """Create a Seat (with auto-User + IdentityProfile) enrolled in class_row."""
    seat = make_student_seat(
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        block=block,
        first_name="Test",
        last_name=suffix.upper(),
    )
    student = Student(
        identity_profile=seat.identity_profile,
        block=block,
        salt=get_random_salt(),
        username_hash=hash_username(f"student_{uuid4().hex[:8]}", get_random_salt()),
        class_id=class_row.class_id,
        join_code=class_row.join_code,
    )
    db.session.add(student)
    db.session.flush()
    return seat


def _add_payment(seat, class_row, amount_paid, late_fee, payment_date, coverage_due_date):
    settings = RentSettings.query.filter_by(class_id=class_row.class_id).first()
    payment = record_rent_payment(
        seat_id=seat.id,
        class_id=class_row.class_id,
        period="A",
        amount_paid=amount_paid,
        period_month=coverage_due_date.month,
        period_year=coverage_due_date.year,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=late_fee > Decimal("0.00"),
        late_fee_charged=late_fee,
        coverage_start_time=coverage_due_date,
        coverage_end_time=coverage_due_date,
        transaction_id=None,
        rent_policy_version_id=settings.active_version_id,
    )
    payment.amount_snap = amount_paid
    payment.satisfaction.satisfied_at = payment_date
    db.session.add(payment.satisfaction)
    db.session.add(Transaction(
        seat_id=seat.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        type="Rent Payment",
        amount=-amount_paid,
        amount_cents=int(-amount_paid * 100),
        timestamp=payment_date,
        description="Rent payment",
        status=TransactionStatus.POSTED,
        account_type='checking',
    ))
    db.session.flush()
    return payment


def test_locked_rate_uses_active_policy_version(client):
    admin, _settings, class_row = _make_admin_with_block("LOCKR1", suffix="first")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    seat_a = _make_student_seat_in_class(class_row, suffix="a")
    seat_b = _make_student_seat_in_class(class_row, suffix="b")

    _settings.rent_amount = Decimal("250.00")
    db.session.commit()

    _add_payment(seat_a, class_row, Decimal("100.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage)
    _add_payment(seat_b, class_row, Decimal("150.00"), Decimal("0.00"), datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc), coverage)
    db.session.commit()

    assert _get_locked_rent_amount_for_join_code_cycle("LOCKR1", coverage) == Decimal("100.00")


def test_locked_rate_ignores_void_transactions(client):
    admin, _settings, class_row = _make_admin_with_block("LOCKRV", suffix="void")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    seat_a = _make_student_seat_in_class(class_row, suffix="va")
    seat_b = _make_student_seat_in_class(class_row, suffix="vb")

    _add_payment(seat_a, class_row, Decimal("80.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage)
    void_txn = Transaction.query.filter_by(seat_id=seat_a.id, join_code="LOCKRV", type="Rent Payment").first()
    void_txn.is_void = True
    _add_payment(seat_b, class_row, Decimal("120.00"), Decimal("0.00"), datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc), coverage)
    db.session.commit()

    assert _get_locked_rent_amount_for_join_code_cycle("LOCKRV", coverage) == Decimal("100.00")


def test_waiver_marks_coverage_period_as_paid(client):
    admin, settings, class_row = _make_admin_with_block("WAIV1", suffix="waiver")
    seat = _make_student_seat_in_class(class_row, suffix="waived")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    record_rent_waiver(
        seat_id=seat.id,
        class_id=class_row.class_id,
        waiver_start_date=coverage - timedelta(days=1),
        waiver_end_date=coverage + timedelta(days=5),
        periods_count=1,
    )
    db.session.commit()

    assert _has_active_rent_waiver(seat.id, class_row.class_id, coverage) is True
    assert _is_student_coverage_period_paid_wrapper(settings, seat.id, class_row.class_id, coverage) is True


def test_reverse_cycle_penalties_refunds_only_misapplied_fees(client, monkeypatch):
    admin, settings, class_row = _make_admin_with_block("REVFEE", suffix="reverse")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routes.admin.utc_now', lambda: datetime(2026, 3, 15, tzinfo=timezone.utc))
    seat_on_time = _make_student_seat_in_class(class_row, suffix="ontime")
    seat_late = _make_student_seat_in_class(class_row, suffix="late")

    _add_payment(
        seat_on_time,
        class_row,
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
        coverage,
    )
    _add_payment(
        seat_late,
        class_row,
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        coverage,
    )
    db.session.commit()

    settings.rent_amount = Decimal("150.00")
    settings.updated_at = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = class_row.user_id
        sess['current_class_id'] = class_row.class_id
        sess['current_join_code'] = class_row.join_code
        sess['class_id'] = class_row.class_id
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
    _login_admin(client, admin, "REVFEE", class_row.class_id)
    response = client.post('/admin/rent/reverse-cycle-penalties', data={'settings_block': 'A'})

    assert response.status_code == 302

    refund_txns = Transaction.query.filter_by(
        join_code="REVFEE",
        type="Rent Late Fee Reversal",
    ).all()
    assert len(refund_txns) == 1
    assert refund_txns[0].seat_id == seat_on_time.id
    assert refund_txns[0].amount == Decimal("10.00")

    on_time_assessment = next(
        assessment for assessment in get_paid_rent_assessments_for_cycle(
            class_row.class_id,
            coverage.month,
            coverage.year,
            seat_ids=[seat_on_time.id],
        )
        if assessment.seat_id == seat_on_time.id
    )
    late_assessment = next(
        assessment for assessment in get_paid_rent_assessments_for_cycle(
            class_row.class_id,
            coverage.month,
            coverage.year,
            seat_ids=[seat_late.id],
        )
        if assessment.seat_id == seat_late.id
    )
    assert on_time_assessment.satisfaction.late_fee_charged == Decimal("0.00")
    assert on_time_assessment.satisfaction.was_late is False
    assert late_assessment.satisfaction.late_fee_charged == Decimal("10.00")
    assert late_assessment.satisfaction.was_late is True
