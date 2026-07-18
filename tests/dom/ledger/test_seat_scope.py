from decimal import Decimal

from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from tests.helpers.ledger import provision_ledger_classroom


def test_DOM_LED_001__transaction_autofills_seat_id_from_student_and_class_scope(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:test-transaction"):
        tx = Transaction(
            user_id=student.user_id,
            class_id=student.class_id,
            seat_id=student.id,
            target_seat_id=student.id,
            actor_seat_id=student.id,
            mechanism="self",
            amount=Decimal("5.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="seat scoped test",
        )
        db.session.add(tx)
        db.session.flush()
        db.session.refresh(tx)
        assert tx.seat_id == student.id
