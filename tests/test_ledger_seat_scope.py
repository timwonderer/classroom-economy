from decimal import Decimal

from app import db
from app.models import BalanceCache, IdentityProfile, Seat, Transaction, TransactionStatus, User, UserRole
from app.utils.banking import settle_balances
from tests.helpers.class_scope import create_class_scope
from app.models import ClassEconomy, UserRole


def _student(first_name: str = "Seat", last_initial: str = "S", block: str = "A") -> Seat:
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=f"{first_name.lower()}_{block.lower()}_hash",
        username_lookup_hash=f"{first_name.lower()}_{block.lower()}_lookup",
        password_hash="pw",
    )
    db.session.add(user)
    db.session.flush()
    seat = Seat(user_id=user.id, block=block, block_identifier=block, role="student")
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student", first_name=first_name, last_name=last_initial))
    teacher = User(
        user_role=UserRole.TEACHER,
        username_hash=f"ledger_{first_name.lower()}_{block.lower()}_hash",
        username_lookup_hash=f"ledger_{first_name.lower()}_{block.lower()}_lookup",
        password_hash="secret",
    )
    db.session.add(teacher)
    db.session.flush()
    class_scope = create_class_scope(
        teacher=teacher,
        teacher_user_id=teacher.id,
        join_code=f"LEDGER-{block}",
        student=None,
        block=block,
        display_name=f"Ledger {block}",
    )
    seat.class_id = class_scope.class_id
    db.session.flush()
    return seat


def test_transaction_autofills_seat_id_from_student_and_join_code(client):
    student = _student()
    db.session.add(student)
    db.session.flush()

    tx = Transaction(
        user_id=student.user_id,
        class_id=student.class_id,
        amount=Decimal("5.00"),
        account_type="checking",
        status=TransactionStatus.PENDING,
        description="seat scoped test",
    )
    db.session.add(tx)
    db.session.commit()

    db.session.refresh(tx)
    assert tx.seat_id == student.id


def test_settlement_creates_balance_cache_with_seat_id(client):
    student = _student(first_name="Cache")
    db.session.add(student)
    db.session.flush()

    db.session.add(
        Transaction(
            user_id=student.user_id,
            class_id=student.class_id,
            amount=Decimal("3.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="pending for settlement",
        )
    )
    db.session.commit()

    settle_balances(student.id, student.class_id)
    db.session.commit()

    cache = BalanceCache.query.filter_by(seat_id=student.id).first()
    assert cache is not None
    assert cache.seat_id == student.id
