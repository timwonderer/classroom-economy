from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope, make_student_with_seat
from app.extensions import db
from app.models import ClassEconomy, Transaction, TransactionStatus
from app.services import ledger_service


def _build_issue_context():
    teacher = make_admin("teacher_issue_reverse", "secret")
    db.session.add(teacher)
    db.session.flush()

    student, _seat = make_student_with_seat(
        join_code="ISSUEA1",
        block="A",
        first_name="Ivy",
        last_name="R",
    )

    class_a = create_class_scope(teacher=teacher, join_code="ISSUEA1", student=student, block="A")
    create_class_scope(teacher=teacher, join_code="ISSUEB1", student=student, block="B")
    db.session.flush()

    return teacher, student, class_a.class_id


def test_compensate_posted_transaction_creates_seat_scoped_reversal():
    teacher, student, class_id = _build_issue_context()

    tx = Transaction(
        seat_id=student.identity_profile.seat_id,
        class_id=class_id,
        join_code="ISSUEA1",
        amount=Decimal("30.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="deposit",
        description="Posted deposit",
    )
    db.session.add(tx)
    db.session.flush()

    reversal_tx = ledger_service.compensate_posted_transaction(
        tx,
        description="Issue reversal for posted transaction",
        compensation_type="issue_reversal",
    )
    assert tx.status == TransactionStatus.POSTED
    assert tx.reversal_transaction_id == reversal_tx.id

    reversal = db.session.get(Transaction, tx.reversal_transaction_id)
    assert reversal is not None
    assert reversal.original_transaction_id == tx.id
    assert reversal.status == TransactionStatus.PENDING
    assert reversal.join_code == "ISSUEA1"
    assert reversal.class_id == class_id
    assert reversal.seat_id == student.identity_profile.seat_id
    assert reversal.amount == Decimal("-30.00")
    db.session.commit()


def test_compensate_posted_transaction_preserves_class_scope():
    teacher, student, class_id = _build_issue_context()

    tx = Transaction(
        seat_id=student.identity_profile.seat_id,
        class_id=ClassEconomy.query.filter_by(join_code="ISSUEB1").first().class_id,
        join_code="ISSUEB1",
        amount=Decimal("20.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="deposit",
        description="Wrong-scope deposit",
    )
    db.session.add(tx)
    db.session.flush()

    reversal_tx = ledger_service.compensate_posted_transaction(
        tx,
        description="Issue reversal for mismatched class",
        compensation_type="issue_reversal",
    )
    assert reversal_tx.class_id == tx.class_id
    assert reversal_tx.join_code == "ISSUEB1"
    assert reversal_tx.seat_id == student.identity_profile.seat_id
    assert reversal_tx.amount == Decimal("-20.00")
    db.session.commit()
