from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Transaction
from app.services.ledger_command_service import create_reserved_effects
from app.utils.transaction_idempotency import (
    IDEMPOTENT_TRANSACTION_TYPES,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    insurance_reimbursement_key,
)
from app.feats.base import FEATContext
from tests.helpers.ledger import (
    create_ledger_idempotent_transaction,
    create_ledger_pending_transaction,
    provision_ledger_classroom,
)


def test_DOM_LED_001__idempotent_transaction_types_are_explicit():
    expected = frozenset({
        "insurance_reimbursement",
        "insurance_premium",
        "purchase",
        "refund",
        "overdraft_fee",
            "payroll",
            "manual_payment",
            "bug_reward",
            "issue_reversal",
            "issue_compensation",
            "rent_payment",
            "Interest",
            "void_item_removed",
        })
    assert IDEMPOTENT_TRANSACTION_TYPES == expected


def test_DOM_LED_001__one_to_many_reservation_replays_effect_set(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    first = classroom.students[0].seat
    second = classroom.students[1].seat
    effects = [
        {"seat_id": first.id, "class_id": classroom.class_id, "target_seat_id": first.id,
         "actor_seat_id": classroom.teacher_seat.id, "mechanism": "teacher",
         "user_id": first.user_id, "amount": Decimal("2.00"), "account_type": "checking",
         "type": "manual_payment", "description": "bonus"},
        {"seat_id": second.id, "class_id": classroom.class_id, "target_seat_id": second.id,
         "actor_seat_id": classroom.teacher_seat.id, "mechanism": "teacher",
         "user_id": second.user_id, "amount": Decimal("2.00"), "account_type": "checking",
         "type": "manual_payment", "description": "bonus"},
    ]
    with FEATContext("FEAT-LED-000", idempotency_key="command:bulk-replay"):
        created, was_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay", effects=effects,
        )
        replay, replay_created = create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay", effects=effects,
        )
    assert was_created is True
    assert replay_created is False
    assert [tx.id for tx in replay] == [tx.id for tx in created]

    changed = [dict(effect) for effect in effects]
    with FEATContext("FEAT-LED-000", idempotency_key="command:bulk-replay-mismatch"):
        create_reserved_effects(
            class_id=classroom.class_id, feat_code="FEAT-LED-000",
            idempotency_key="command:bulk-replay-mismatch", effects=effects,
        )
        changed[0]["amount"] = Decimal("4.00")
        with pytest.raises(ValueError, match="Replay fingerprint mismatch"):
            create_reserved_effects(
                class_id=classroom.class_id, feat_code="FEAT-LED-000",
                idempotency_key="command:bulk-replay-mismatch", effects=changed,
            )


def test_DOM_LED_001__idempotent_transaction_reuses_existing_row_on_retry(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(123)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reuse_1"):
        transaction_one, created_one = create_ledger_idempotent_transaction(
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
        transaction_two, created_two = create_ledger_idempotent_transaction(
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


def test_DOM_LED_001__idempotent_transaction_recovers_from_integrity_race(client, monkeypatch, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    idempotency_key = insurance_reimbursement_key(456)
    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_seed"):
        winning_tx, winning_created = create_ledger_idempotent_transaction(
            idempotency_key=idempotency_key,
            seat_id=student.id,
            class_id=class_row.class_id,
            user_id=student.user_id,
            amount=Decimal("11.00"),
            account_type="checking",
            type="insurance_reimbursement",
            description="Winning insurance reimbursement",
        )
        assert winning_created is True

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_race_call"):
        transaction, created = create_ledger_idempotent_transaction(
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


def test_DOM_LED_001__idempotent_transaction_rejects_non_idempotent_types(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_reject_type"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
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
def test_DOM_LED_001__idempotent_transaction_rejects_empty_keys(client, bad_key, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key=f"test_transaction_idempotency_empty_{bad_key!s}"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
                idempotency_key=bad_key,
                seat_id=student.id,
                class_id=class_row.class_id,
                user_id=student.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )


def test_DOM_LED_001__idempotent_transaction_rejects_oversize_keys(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    class_row = classroom.economy
    student = classroom.students[0].seat
    db.session.commit()

    with FEATContext("FEAT-LED-000", idempotency_key="test_transaction_idempotency_oversize"):
        with pytest.raises(ValueError):
            create_ledger_idempotent_transaction(
                idempotency_key="x" * (MAX_IDEMPOTENCY_KEY_LENGTH + 1),
                seat_id=student.id,
                class_id=class_row.class_id,
                user_id=student.user_id,
                amount=Decimal("5.00"),
                account_type="checking",
                type="refund",
                description="Should fail",
            )
