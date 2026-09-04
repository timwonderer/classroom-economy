from app.services.ledger_balance_query_service import (
    reconstruct_available_balance,
    reconstruct_posted_balance,
    verify_available_balance,
    verify_posted_balance,
)
from app.services.ledger_transfer_service import verify_transfer
from app.feats.base import FEATContext
from app.extensions import db
from app.models import LedgerBalanceSnapshot
from app.services.ledger_posting_service import create_pending_transaction
from app.services.ledger_settlement_service import settle_balances
from tests.helpers.ledger import provision_ledger_classroom, create_ledger_transfer_pair


def test_reconstruct_posted_balance_rejects_incomplete_scope():
    result = reconstruct_posted_balance("", 1, "checking")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"
    assert result.complete is False


def test_reconstruct_available_balance_rejects_incomplete_scope():
    result = reconstruct_available_balance("class-a", 1, "reserve")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"


def test_projection_verification_compares_against_canonical_history(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:projection"):
        create_pending_transaction(
            seat_id=seat.id, class_id=classroom.class_id,
            target_seat_id=seat.id, actor_seat_id=seat.id,
            mechanism="self", user_id=seat.user_id, amount=12,
            account_type="checking", type="Deposit", description="proof projection",
        )
        settle_balances(seat.id, classroom.class_id)

    assert verify_posted_balance(classroom.class_id, seat.id, "checking").outcome == "PASS"
    assert verify_available_balance(classroom.class_id, seat.id, "checking").outcome == "PASS"

    snapshot = LedgerBalanceSnapshot.query.filter_by(
        class_id=classroom.class_id, seat_id=seat.id, account_type="checking"
    ).one()
    with FEATContext("FEAT-LED-001", idempotency_key="proof:projection-corrupt"):
        snapshot.posted_balance_cents += 1
        db.session.flush()
    assert verify_posted_balance(classroom.class_id, seat.id, "checking").code == "posted_balance_mismatch"


def test_verify_transfer_requires_scoped_correlation():
    result = verify_transfer("", "")
    assert result.outcome == "UNAVAILABLE"
    assert result.code == "invalid_scope"


def test_verify_transfer_passes_for_posted_two_leg_transfer(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:valid-transfer"):
        withdrawal, deposit = create_ledger_transfer_pair(
            seat_id=seat.id,
            class_id=classroom.class_id,
            user_id=seat.user_id,
            amount=10,
            from_account="checking",
            to_account="savings",
            withdraw_description="proof withdrawal",
            deposit_description="proof deposit",
        )
        settle_balances(seat.id, classroom.class_id)
        result = verify_transfer(classroom.class_id, withdrawal.correlation_id)

    assert result.outcome == "PASS"
    assert result.leg_count == 2
    assert result.scope_consistent is True
    assert result.account_pair_valid is True
    assert result.equal_magnitude is True
    assert result.zero_sum is True
    assert result.posting_consistent is True


def test_reconstruct_posted_balance_does_not_depend_on_snapshot(client, app):
    classroom = provision_ledger_classroom("chemistry_p1", app)
    seat = classroom.students[0].seat
    with FEATContext("FEAT-LED-001", idempotency_key="proof:balance-history"):
        transaction = create_pending_transaction(
            seat_id=seat.id,
            class_id=classroom.class_id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            user_id=seat.user_id,
            amount=12,
            account_type="checking",
            type="Deposit",
            description="proof balance history",
        )
        settle_balances(seat.id, classroom.class_id)

    snapshot = LedgerBalanceSnapshot.query.filter_by(
        class_id=classroom.class_id, seat_id=seat.id, account_type="checking"
    ).one()
    with FEATContext("FEAT-LED-001", idempotency_key="proof:corrupt-snapshot"):
        snapshot.posted_balance_cents = -999999
        db.session.flush()

    result = reconstruct_posted_balance(classroom.class_id, seat.id, "checking")
    assert result.outcome == "PASS"
    assert result.reconstructed_cents == int(transaction.amount_cents)
