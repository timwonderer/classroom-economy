from decimal import Decimal

from app import db
from app.feats.base import FEATContext
from app.models import BalanceCache, IdentityProfile, Seat, Transaction, TransactionStatus, User, UserRole
from app.utils.banking import settle_balances
from tests.helpers.class_scope import create_class_scope
from app.models import ClassEconomy, UserRole


def _student(first_name: str = "Seat", last_initial: str = "S", block: str = "A") -> Seat:
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"ledger-seat-scope:{first_name}:{block}"):
        user = User(
            user_role=UserRole.STUDENT,
            username_hash=f"{first_name.lower()}_{block.lower()}_hash",
            username_lookup_hash=f"{first_name.lower()}_{block.lower()}_lookup",
            passphrase_hash="pw",
        )
        db.session.add(user)
        db.session.flush()
        seat = Seat(user_id=user.id, role="student")
        db.session.add(seat)
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student", first_name=first_name, last_name=last_initial))
        teacher = User(
            user_role=UserRole.TEACHER,
            username_hash=f"ledger_{first_name.lower()}_{block.lower()}_hash",
            username_lookup_hash=f"ledger_{first_name.lower()}_{block.lower()}_lookup",
            passphrase_hash="secret",
        )
        db.session.add(teacher)
        db.session.flush()
        class_scope = create_class_scope(
            join_code=f"LEDGER-{block}",
            display_name=f"Ledger {block}",
            teacher_user=teacher,
            section=block,
        )
        seat.class_id = class_scope.class_id
        db.session.flush()
        return seat


def test_transaction_autofills_seat_id_from_student_and_class_scope(client):
    student = _student()

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:test-transaction"):
        tx = Transaction(
            user_id=student.user_id,
            class_id=student.class_id,
            amount=Decimal("5.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="seat scoped test",
        )
        db.session.add(tx)
        db.session.flush()
        db.session.refresh(tx)
        assert tx.seat_id == student.id

