from decimal import Decimal

from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction
import app.utils.transaction_idempotency as transaction_idempotency
from app.utils.transaction_idempotency import (
    IDEMPOTENT_TRANSACTION_TYPES,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    create_idempotent_transaction,
    insurance_reimbursement_key,
)
from app.feats.base import FEATContext


def test_idempotent_transaction_types_are_explicit():
    expected = frozenset({
        "insurance_reimbursement",
        "purchase",
        "refund",
        "overdraft_fee",
        "payroll",
        "Interest",
    })
    assert IDEMPOTENT_TRANSACTION_TYPES == expected


def test_create_idempotent_transaction_reuses_existing_row_on_retry(client):
    teacher = seed_canonical_admin("idempotent-teacher", "secret").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="IDEMP123")
    student = make_student_identity(class_id=class_row.class_id, first_name="Retry", last_name="R")
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(123)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reuse_1"):
        transaction_one, created_one = create_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,
            user_id=student.user_id,
            amount=Decimal("10.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Insurance reimbursement",
        )
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reuse_2"):
        transaction_two, created_two = create_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,
            user_id=student.user_id,
            amount=Decimal("10.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Insurance reimbursement",
        )

    assert created_one is True
    assert created_two is False
    assert transaction_one.id == transaction_two.id
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_create_idempotent_transaction_recovers_from_integrity_race(client, monkeypatch):
    teacher = seed_canonical_admin("idempotent-race-teacher", "secret").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="IDEMP456")
    student = make_student_identity(class_id=class_row.class_id, first_name="Race", last_name="R")
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(456)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_seed"):
        winning_tx = Transaction(
            seat_id=student.id,
            class_id=class_row.class_id,
            user_id=student.user_id,
            amount=Decimal("11.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Winning insurance reimbursement",
            idempotency_key=idempotency_key,
        )
        db.session.add(winning_tx)

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_call"):
        transaction, created = create_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,
            user_id=student.user_id,
            amount=Decimal("11.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Losing insurance reimbursement",
        )

    assert created is False
    assert transaction is not None
    assert transaction.id == winning_tx.id
    assert transaction.idempotency_key == idempotency_key
    assert Transaction.query.filter_by(idempotency_key=idempotency_key).count() == 1


def test_create_idempotent_transaction_rejects_non_idempotent_types(client):
    teacher = seed_canonical_admin("idempotent-invalid-teacher", "secret").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="IDEMP789")
    student = make_student_identity(class_id=class_row.class_id, first_name="Nope", last_name="N")
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reject_type"):
        with pytest.raises(ValueError):
            create_idempotent_transaction(
                idempotency_key="txn:unknown:op",
                seat_id=student.id,
                class_id=class_row.class_id,
                user_id=student.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="UnknownType",
                description="Should fail",
            )


@pytest.mark.parametrize("bad_key", [None, "", "   "])
def test_create_idempotent_transaction_rejects_empty_keys(client, bad_key):
    teacher = seed_canonical_admin("idempotent-empty-key-teacher", "secret").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="IDEMP000")
    student = make_student_identity(class_id=class_row.class_id, first_name="Empty", last_name="E")
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key=f"test_transaction_idempotency_empty_{bad_key!s}"):
        with pytest.raises(ValueError):
            create_idempotent_transaction(
                idempotency_key=bad_key,
                seat_id=student.id,
                class_id=class_row.class_id,
                user_id=student.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )


def test_create_idempotent_transaction_rejects_oversize_keys(client):
    teacher = seed_canonical_admin("idempotent-long-key-teacher", "secret").user
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="IDEMP001")
    student = make_student_identity(class_id=class_row.class_id, first_name="Long", last_name="L")
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_oversize"):
        with pytest.raises(ValueError):
            create_idempotent_transaction(
                idempotency_key="x" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1),
                seat_id=student.id,
                class_id=class_row.class_id,
                user_id=student.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )
