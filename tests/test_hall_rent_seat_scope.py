from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import db
from app.hash_utils import get_random_salt, hash_username_lookup
from app.models import HallPassLog, RentPayment, RentWaiver, Seat, Student, User


def _student() -> Student:
    return Student(
        first_name="Scope",
        last_initial="S",
        block="A",
        salt=get_random_salt(),
        first_half_hash=None,
        second_half_hash=None,
    )


def test_hall_pass_log_autofills_seat_id_from_join_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username_hash=hash_username_lookup(f"hall_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, join_code="JOIN_HALL", block="A")
    db.session.add(seat)
    db.session.flush()

    hall_pass = HallPassLog(
        user_id=student_user.id,
        join_code="JOIN_HALL",
        reason="Bathroom",
        period="A",
    )
    db.session.add(hall_pass)
    db.session.commit()

    db.session.refresh(hall_pass)
    assert hall_pass.seat_id == seat.id


def test_rent_payment_autofills_seat_id_from_join_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username_hash=hash_username_lookup(f"rent_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, join_code="JOIN_RENT", block="A")
    db.session.add(seat)
    db.session.flush()

    rent_payment = RentPayment(
        user_id=student_user.id,
        join_code="JOIN_RENT",
        period="A",
        amount_paid=Decimal("10.00"),
    )
    db.session.add(rent_payment)
    db.session.commit()

    db.session.refresh(rent_payment)
    assert rent_payment.seat_id == seat.id


def test_rent_waiver_autofills_seat_id_from_join_scope(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username_hash=hash_username_lookup(f"waiver_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, join_code="JOIN_WAIVE", block="A")
    db.session.add(seat)
    db.session.flush()

    now = datetime.now(timezone.utc)
    waiver = RentWaiver(
        user_id=student_user.id,
        join_code="JOIN_WAIVE",
        waiver_start_date=now,
        waiver_end_date=now + timedelta(days=30),
        periods_count=1,
        reason="test",
    )
    db.session.add(waiver)
    db.session.commit()

    db.session.refresh(waiver)
    assert waiver.seat_id == seat.id
