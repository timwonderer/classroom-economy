from decimal import Decimal

import pytest

from app import db
from app.feats.base import FEATContext
from app.models import Transaction, TransactionStatus
from app.services.ledger_posting_service import create_pending_transaction
from app.services.ledger_posting_service import create_pending_transaction_idempotent
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


def test_DOM_LED_001__transaction_rejects_missing_explicit_class_scope(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    student = classroom.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:missing-class"):
        tx = Transaction(
            user_id=student.user_id,
            class_id=None,
            seat_id=student.id,
            target_seat_id=student.id,
            actor_seat_id=student.id,
            mechanism="self",
            amount=Decimal("5.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            description="missing class scope test",
        )
        db.session.add(tx)
        with pytest.raises(ValueError, match="requires explicit class_id"):
            db.session.flush()


def test_DOM_LED_001__posting_rejects_cross_class_actor_or_target(client, app):
    classroom_a = provision_ledger_classroom("chemistry_p1", app)
    classroom_b = provision_ledger_classroom("ap_csp_p3", app)
    student_a = classroom_a.students[0].seat
    student_b = classroom_b.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:cross-class"):
        with pytest.raises(ValueError, match="all belong to the provided class_id"):
            create_pending_transaction(
                seat_id=student_a.id,
                class_id=classroom_a.class_id,
                target_seat_id=student_b.id,
                actor_seat_id=student_a.id,
                mechanism="self",
                user_id=student_a.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="Deposit",
                description="cross-class scope test",
            )


def test_DOM_LED_001__idempotent_posting_rejects_cross_class_actor_or_target(client, app):
    classroom_a = provision_ledger_classroom("chemistry_p1", app)
    classroom_b = provision_ledger_classroom("ap_csp_p3", app)
    student_a = classroom_a.students[0].seat
    student_b = classroom_b.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:idempotent-cross-class"):
        with pytest.raises(ValueError, match="all belong to the provided class_id"):
            create_pending_transaction_idempotent(
                idempotency_key="ledger-seat-scope:idempotent-cross-class",
                seat_id=student_a.id,
                class_id=classroom_a.class_id,
                target_seat_id=student_b.id,
                actor_seat_id=student_a.id,
                mechanism="self",
                user_id=student_a.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="purchase",
                description="cross-class idempotent scope test",
            )


def test_DOM_LED_001__posting_rejects_unknown_account_type(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat

    with FEATContext("FEAT-LED-001", idempotency_key="ledger-seat-scope:account-type"):
        with pytest.raises(ValueError, match="checking or savings"):
            create_pending_transaction(
                seat_id=seat.id,
                class_id=classroom.class_id,
                target_seat_id=seat.id,
                actor_seat_id=seat.id,
                mechanism="self",
                user_id=seat.user_id,
                amount=Decimal("1.00"),
                account_type="rent",
                type="Deposit",
                description="invalid account type",
            )
