"""
Tests for rent penalty reversal and cycle rate locking.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import User, UserRole, Admin, ClassEconomy, IdentityProfile, RentPayment, RentSettings, RentWaiver, Seat, Transaction
from app.routes.student import (
    RENT_PAYMENT_MATCH_TOLERANCE_SECONDS,
    _get_locked_rent_amount_for_join_code_cycle,
    _is_student_coverage_period_paid,
)
from tests.helpers.class_scope import make_student_identity

def _has_active_rent_waiver(student_id, join_code, coverage_due_date):
    from app.models import ClassEconomy, Seat
    from app.routes.student import _has_active_rent_waiver_v2
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        return False
    seat = Seat.query.filter_by(user_id=student_id, class_id=class_row.class_id).first()
    if not seat:
        return False
    return _has_active_rent_waiver_v2(seat.id, class_row.class_id, coverage_due_date)

def _is_student_coverage_period_paid_wrapper(settings, student_id, block, join_code, coverage_due_date):
    from app.models import ClassEconomy, Seat
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        return False
    seat = Seat.query.filter_by(user_id=student_id, class_id=class_row.class_id).first()
    if not seat:
        return False
    return _is_student_coverage_period_paid(settings, seat.id, class_row.class_id, coverage_due_date)



def _login_admin(client, admin_id, join_code):
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin_id
        sess['current_join_code'] = join_code
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()


def _make_admin_with_block(join_code="LOCKA1", block="A", suffix="rv"):
    admin = make_admin(f"rent_admin_{suffix}_{join_code.lower()}", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    identity = IdentityProfile(profile_type='student', first_name='Teacher', last_name='T')
    db.session.add(identity)
    db.session.flush()

    db.session.add(ClassEconomy(
        join_code=join_code,
        user_id=admin.id,
    ))
    db.session.flush()
    class_id = db.session.query(ClassEconomy.class_id).filter_by(join_code=join_code).scalar()
    seat = Seat(
        class_id=class_id,
        join_code=join_code,
        block=block,
        block_identifier=block,
        role="teacher",
    )
    db.session.add(seat)
    db.session.flush()
    identity.seat_id = seat.id
    settings = RentSettings(join_code=join_code,
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
    return admin, settings


def _make_student(suffix="s"):
    return make_student_identity(first_name="Test", last_name="R", block="A")


def _add_payment(student, admin_id, join_code, amount_paid, late_fee, payment_date, coverage_due_date):
    payment = RentPayment(
        user_id=student.user_id,
        period="A",
        join_code=join_code,
        amount_paid=amount_paid,
        late_fee_charged=late_fee,
        was_late=late_fee > Decimal("0.00"),
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
    )
    db.session.add(payment)
    db.session.add(Transaction(
        user_id=student.user_id,join_code=join_code,
        type="Rent Payment",
        amount=-amount_paid,
        timestamp=payment_date,
        description="Rent payment",
    ))
    db.session.flush()
    return payment


def test_locked_rate_uses_first_valid_payer_base(client):
    admin, _settings = _make_admin_with_block("LOCKR1", suffix="first")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    student_a = _make_student("a")
    student_b = _make_student("b")

    _add_payment(student_a, admin.id, "LOCKR1", Decimal("100.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage)
    _add_payment(student_b, admin.id, "LOCKR1", Decimal("150.00"), Decimal("0.00"), datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc), coverage)
    db.session.commit()

    assert _get_locked_rent_amount_for_join_code_cycle("LOCKR1", coverage) == Decimal("100.00")


def test_locked_rate_ignores_void_transactions(client):
    admin, _settings = _make_admin_with_block("LOCKRV", suffix="void")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    student_a = _make_student("va")
    student_b = _make_student("vb")

    _add_payment(student_a, admin.id, "LOCKRV", Decimal("80.00"), Decimal("0.00"), datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), coverage)
    void_txn = Transaction.query.filter_by(user_id=student_a_user.id, join_code="LOCKRV", type="Rent Payment").first()
    void_txn.is_void = True
    _add_payment(student_b, admin.id, "LOCKRV", Decimal("120.00"), Decimal("0.00"), datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc), coverage)
    db.session.commit()

    assert _get_locked_rent_amount_for_join_code_cycle("LOCKRV", coverage) == Decimal("120.00")


def test_waiver_marks_coverage_period_as_paid(client):
    admin, settings = _make_admin_with_block("WAIV1", suffix="waiver")
    student = _make_student("waived")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    db.session.add(RentWaiver(
        user_id=student_user.id,
        join_code="WAIV1",
        waiver_start_date=coverage - timedelta(days=1),
        waiver_end_date=coverage + timedelta(days=5),
        periods_count=1,
        created_by_teacher_id=admin.id,
    ))
    db.session.commit()

    assert _has_active_rent_waiver(student.id, "WAIV1", coverage) is True
    assert _is_student_coverage_period_paid_wrapper(settings, student.id, "A", "WAIV1", coverage) is True


def test_reverse_cycle_penalties_refunds_only_misapplied_fees(client, monkeypatch):
    admin, settings = _make_admin_with_block("REVFEE", suffix="reverse")
    coverage = datetime(2026, 3, 1, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routes.admin.utc_now', lambda: datetime(2026, 3, 15, tzinfo=timezone.utc))
    on_time_student = _make_student("ontime")
    late_student = _make_student("late")

    _add_payment(
        on_time_student,
        admin.id,
        "REVFEE",
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
        coverage,
    )
    _add_payment(
        late_student,
        admin.id,
        "REVFEE",
        Decimal("110.00"),
        Decimal("10.00"),
        datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        coverage,
    )
    db.session.commit()

    settings.rent_amount = Decimal("150.00")
    settings.updated_at = datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc)
    db.session.commit()

    _login_admin(client, admin.id, "REVFEE")
    response = client.post('/admin/rent/reverse-cycle-penalties', data={'settings_block': 'A'})

    assert response.status_code == 302

    refund_txns = Transaction.query.filter_by(
        join_code="REVFEE",
        type="Rent Late Fee Reversal",
    ).all()
    assert len(refund_txns) == 1
    assert refund_txns[0].student_id == on_time_student.id
    assert refund_txns[0].amount == Decimal("10.00")

    on_time_payment = RentPayment.query.filter_by(user_id=on_time_student_user.id, join_code="REVFEE").first()
    late_payment = RentPayment.query.filter_by(user_id=late_student_user.id, join_code="REVFEE").first()
    assert on_time_payment.late_fee_charged == Decimal("0.00")
    assert on_time_payment.was_late is False
    assert late_payment.late_fee_charged == Decimal("10.00")
    assert late_payment.was_late is True
