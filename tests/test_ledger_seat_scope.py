from decimal import Decimal

from app import db
from app.hash_utils import get_random_salt, hash_username_lookup
from app.models import BalanceCache, Seat, Student, Transaction, TransactionStatus, User
from app.utils.banking import settle_balances


def _student(first_name: str = "Seat", last_initial: str = "S", block: str = "A") -> Student:
    return Student(
        first_name=first_name,
        last_initial=last_initial,
        block=block,
        salt=get_random_salt(),
        first_half_hash=None,
        second_half_hash=None,
    )


def test_transaction_autofills_seat_id_from_student_and_join_code(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    user = User(username_hash=hash_username_lookup(f"ledger_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, join_code="JOIN_LEDGER", block="A")
    db.session.add(seat)
    db.session.flush()

    tx = Transaction(
        user_id=student_user.id,
        join_code="JOIN_LEDGER",
        amount=Decimal("5.00"),
        account_type="checking",
        status=TransactionStatus.PENDING,
        description="seat scoped test",
    )
    db.session.add(tx)
    db.session.commit()

    db.session.refresh(tx)
    assert tx.seat_id == seat.id


def test_settlement_creates_balance_cache_with_seat_id(client):
    student = _student(first_name="Cache")
    db.session.add(student)
    db.session.flush()

    user = User(username_hash=hash_username_lookup(f"cache_user_{student.id}"), password_hash="pw")
    db.session.add(user)
    db.session.flush()

    seat = Seat(user_id=user.id, join_code="JOIN_CACHE", block="A")
    db.session.add(seat)
    db.session.flush()

    db.session.add(
        Transaction(
            user_id=student_user.id,
            join_code="JOIN_CACHE",
            amount=Decimal("3.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="pending for settlement",
        )
    )
    db.session.commit()

    settle_balances(student.id, "JOIN_CACHE")
    db.session.commit()

    cache = BalanceCache.query.filter_by(join_code="JOIN_CACHE", user_id=student_user.id).first()
    assert cache is not None
    assert cache.seat_id == seat.id
