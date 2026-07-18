from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import db, Transaction
from app.feats.base import FEATContext
from app.models import AttendanceSession, IdentityProfile, PayrollSettings, Seat, Transaction
from app.payroll import DEFAULT_PAY_RATE_PER_SECOND, calculate_payroll_breakdown, get_cached_payroll_with_meta, get_pay_rate_for_block
from tests.helpers.classroom_initializer import initialize

FLOAT_TOLERANCE = 0.0001


@pytest.fixture
def classroom(app):
    return initialize("chemistry_p1", app)


def test_FEAT_PAY_001__calculate_payroll(client, classroom):
    student = classroom.students[0]
    seat = student.seat

    now = datetime.now(timezone.utc)
    attendance_session = AttendanceSession(
        seat_id=seat.id,
        class_id=classroom.class_id,
        started_at=now - timedelta(minutes=60),
        ended_at=now - timedelta(minutes=30),
        duration_seconds=1800,
    )
    with FEATContext("FEAT-LED-004", idempotency_key="payroll:test_calculate_payroll:attendance"):
        db.session.add(attendance_session)
        db.session.flush()

    seat_ids = [seat.id]
    last_payroll_time = now - timedelta(days=1)
    payroll_summary = calculate_payroll_breakdown(classroom.class_id, seat_ids, last_payroll_time)

    assert seat.id in payroll_summary
    assert payroll_summary[seat.id] == Decimal("7.50")

    payroll_summary2 = calculate_payroll_breakdown(classroom.class_id, [], last_payroll_time)
    assert seat.id not in payroll_summary2

    manual_tx = Transaction(
        user_id=student.user.id,
        amount=3,
        type="manual_payment",
        timestamp=now - timedelta(minutes=5),
        class_id=classroom.class_id,
        seat_id=seat.id,
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
    )
    with FEATContext("FEAT-LED-004", idempotency_key="payroll:test_calculate_payroll:manual"):
        db.session.add(manual_tx)
        db.session.flush()

    post_manual_summary = calculate_payroll_breakdown(classroom.class_id, seat_ids, last_payroll_time)
    assert post_manual_summary == {}


def test_FEAT_PAY_001__calculate_payroll_ignores_other_class_manual_payment_anchor(client, classroom):
    class_a = classroom
    class_b = initialize("biology_block_a", client.application)
    student = class_a.students[0]

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"payroll-multiclass:{class_a.class_id}:{class_b.class_id}:{student.user.id}"):
        seat_b_row = Seat(user_id=student.user.id, class_id=class_b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add(seat_b_row)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat_b_row.id, profile_type="student_claimed", first_name=student.first_name, last_name=student.last_name, class_id=class_b.class_id))
        db.session.flush()

    seat_a = student.seat
    seat_b = Seat.query.filter_by(user_id=student.user.id, class_id=class_b.class_id, role="student").first()
    assert seat_a is not None
    assert seat_b is not None

    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-LED-004", idempotency_key=f"payroll-multiclass-sessions:{class_a.class_id}:{class_b.class_id}:{student.user.id}"):
        db.session.add_all([
            AttendanceSession(seat_id=seat_a.id, class_id=class_a.class_id, started_at=now - timedelta(minutes=50), ended_at=now - timedelta(minutes=40), duration_seconds=600),
            AttendanceSession(seat_id=seat_a.id, class_id=class_a.class_id, started_at=now - timedelta(minutes=39), ended_at=now - timedelta(minutes=35), duration_seconds=240),
            AttendanceSession(seat_id=seat_b.id, class_id=class_b.class_id, started_at=now - timedelta(minutes=30), ended_at=now - timedelta(minutes=15), duration_seconds=900),
            Transaction(user_id=student.user.id, seat_id=seat_a.id, target_seat_id=seat_a.id, actor_seat_id=seat_a.id, mechanism="self", class_id=class_a.class_id, amount=3, type="manual_payment", timestamp=now - timedelta(minutes=5)),
        ])
    db.session.commit()

    summary_a = calculate_payroll_breakdown(class_a.class_id, [seat_a.id], now - timedelta(days=1))
    summary_b = calculate_payroll_breakdown(class_b.class_id, [seat_b.id], now - timedelta(days=1))

    assert summary_a == {}
    assert summary_b == {seat_b.id: Decimal("3.75")}


def test_DOM_CLASS_001__get_pay_rate_for_block_default(classroom):
    rate = get_pay_rate_for_block("A", class_id=classroom.class_id)
    assert rate == DEFAULT_PAY_RATE_PER_SECOND
    assert isinstance(rate, Decimal)


def test_DOM_CLASS_001__get_pay_rate_for_block_block_specific(classroom):
    block_setting = PayrollSettings(class_id=classroom.class_id, block="A", pay_rate=Decimal("0.50"), is_active=True)
    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll:block_specific"):
        db.session.add(block_setting)
        db.session.flush()

    rate = get_pay_rate_for_block("A", class_id=classroom.class_id)
    assert abs(float(rate) - (0.50 / 60.0)) < FLOAT_TOLERANCE
    assert isinstance(rate, Decimal)


def test_DOM_CLASS_001__get_pay_rate_for_block_global_fallback(classroom):
    global_setting = PayrollSettings(class_id=classroom.class_id, block=None, pay_rate=Decimal("0.30"), is_active=True)
    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll:global_fallback"):
        db.session.add(global_setting)
        db.session.flush()

    rate = get_pay_rate_for_block("B", class_id=classroom.class_id)
    assert float(rate) == 0.30 / 60.0
    assert isinstance(rate, Decimal)


def test_DOM_CLASS_001__get_pay_rate_for_block_precedence(classroom):
    global_setting = PayrollSettings(class_id=classroom.class_id, block=None, pay_rate=Decimal("0.25"), is_active=True)
    block_setting = PayrollSettings(class_id=classroom.class_id, block="A", pay_rate=Decimal("0.75"), is_active=True)
    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll:precedence"):
        db.session.add_all([global_setting, block_setting])
        db.session.flush()

    assert float(get_pay_rate_for_block("A", class_id=classroom.class_id)) == 0.75 / 60.0
    assert abs(float(get_pay_rate_for_block("B", class_id=classroom.class_id)) - (0.25 / 60.0)) < FLOAT_TOLERANCE


def test_DOM_CLASS_001__get_pay_rate_for_block_per_minute_to_per_second_conversion(classroom):
    setting = PayrollSettings(class_id=classroom.class_id, block="A", pay_rate=Decimal("1.20"), is_active=True)
    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll:conversion"):
        db.session.add(setting)
        db.session.flush()

    rate = get_pay_rate_for_block("A", class_id=classroom.class_id)
    assert float(rate) == 0.02
    assert isinstance(rate, Decimal)


def test_DOM_CLASS_001__get_pay_rate_for_block_json_serialization(classroom):
    import json

    setting = PayrollSettings(class_id=classroom.class_id, block="A", pay_rate=Decimal("0.45"), is_active=True)
    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll:json"):
        db.session.add(setting)
        db.session.flush()

    rate = get_pay_rate_for_block("A", class_id=classroom.class_id)
    json_str = json.dumps({"pay_rate": float(rate)})
    assert json_str is not None
    assert abs(json.loads(json_str)["pay_rate"] - (0.45 / 60.0)) < FLOAT_TOLERANCE


def test_DOM_CLASS_001__get_pay_rate_for_block_inactive_settings_ignored(classroom):
    with FEATContext("FEAT-LED-004", idempotency_key="payroll:inactive-setting"):
        db.session.add(PayrollSettings(class_id=classroom.class_id, block="A", pay_rate=Decimal("0.99"), is_active=False))
        db.session.flush()

    assert get_pay_rate_for_block("A", class_id=classroom.class_id) == DEFAULT_PAY_RATE_PER_SECOND


def test_DOM_CLASS_001__get_pay_rate_for_block_requires_class_scope(client):
    with pytest.raises(ValueError, match="class_id"):
        get_pay_rate_for_block("A", class_id=None)


def test_FEAT_PAY_001__get_cached_payroll_with_meta(client, classroom):
    student = classroom.students[0]
    seat = student.seat

    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-LED-004", idempotency_key="payroll:cached-session-one"):
        db.session.add(AttendanceSession(seat_id=seat.id, class_id=classroom.class_id, started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1), duration_seconds=3600))
        db.session.flush()

    summary, updated_at = get_cached_payroll_with_meta(classroom.class_id, [seat.id], now - timedelta(days=1))
    assert seat.id in summary
    assert summary[seat.id] > 0
    initial_amount = summary[seat.id]

    with FEATContext("FEAT-LED-004", idempotency_key="payroll:cached-session-two"):
        db.session.add(AttendanceSession(seat_id=seat.id, class_id=classroom.class_id, started_at=now - timedelta(minutes=30), ended_at=now - timedelta(minutes=15), duration_seconds=900))
        db.session.flush()

    summary_fresh, updated_at_fresh = get_cached_payroll_with_meta(classroom.class_id, [seat.id], now - timedelta(days=1))
    assert summary_fresh[seat.id] > initial_amount
    assert updated_at_fresh >= updated_at


def test_FEAT_PAY_001__get_cached_payroll_with_meta_fails_closed(client):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match=r"Class scope \(class_id\) must be explicitly provided."):
        get_cached_payroll_with_meta(None, [], now)
