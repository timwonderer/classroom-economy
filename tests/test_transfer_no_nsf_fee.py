"""A transfer is lateral movement, not spending — insufficient funds is invalid.

A transfer between the seat's OWN accounts (checking<->savings) is not a failed
agreement. On insufficient funds it must simply decline: it does NOT proceed and
does NOT incur an NSF fee. NSF is charged only where money was meant to leave for
a purchase or to meet an obligation. Regression for the checking-insufficient
transfer branch, which previously charged a forced overdraft fee.
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import LedgerCommandReservation, Transaction, ObligationAssessment
from app.services.ledger_balance_query_service import get_available_balances
from tests.helpers.classroom_initializer import initialize_as_student
from tests.helpers.ledger import create_ledger_idempotent_transaction


def test_insufficient_checking_transfer_declines_without_nsf_fee(client, app):
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with app.app_context():
        fees_before = Transaction.query.filter_by(
            class_id=class_id, type="overdraft_fee"
        ).count()
        nsf_before = ObligationAssessment.query.filter_by(
            class_id=class_id, obligation_type="NSF_FEE"
        ).count()

    # Satisfy the single-use transfer token and passphrase gates so the POST
    # actually reaches the insufficient-funds branch under test.
    with client.session_transaction() as sess:
        sess["transfer_token"] = "test-token"

    # A fresh student has no checking balance, so any checking->savings transfer
    # is over-balance and must be declined.
    resp = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "10.00",
            "transfer_token": "test-token",
            "passphrase": student.passphrase,
        },
        follow_redirects=False,
    )

    # Declined (redirect back or 400 for JSON); never a server error.
    assert resp.status_code in (302, 400)

    with app.app_context():
        # No NSF fee transaction and no NSF_FEE fine obligation were created.
        assert Transaction.query.filter_by(
            class_id=class_id, type="overdraft_fee"
        ).count() == fees_before
        assert ObligationAssessment.query.filter_by(
            class_id=class_id, obligation_type="NSF_FEE"
        ).count() == nsf_before


def test_successful_transfer_moves_funds_under_feat_context(client, app):
    """A funded checking->savings transfer succeeds through the FEAT boundary.

    Regression: the /student/transfer POST path called execute_account_transfer
    without passing user_id AND without opening a FEAT context, so a real transfer
    raised TypeError('missing user_id') and then, once user_id was supplied, a
    FEATContextError on flush ('mutated state outside a verified FEAT context').
    This guards the FEAT-LED-000 wrapping and the user_id wiring together by
    exercising a transfer that actually reaches the ledger.
    """
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    class_id = classroom.class_id

    with app.app_context():
        seat_id = student.seat.id
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"fund:{seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"fund-seat:{seat_id}",
                seat_id=seat_id,
                class_id=class_id,
                user_id=student.user.id,
                amount=Decimal("50.00"),
                account_type="checking",
                type="payroll",
                description="Test funding",
            )
        checking_before, savings_before = get_available_balances(
            seat_id, class_id
        )

    with client.session_transaction() as sess:
        sess["transfer_token"] = "test-token"

    resp = client.post(
        "/student/transfer",
        data={
            "from_account": "checking",
            "to_account": "savings",
            "amount": "20.00",
            "transfer_token": "test-token",
            "passphrase": student.passphrase,
        },
        follow_redirects=False,
    )
    # Success redirects to the dashboard; never a server error.
    assert resp.status_code == 302

    with app.app_context():
        checking_after, savings_after = get_available_balances(
            seat_id, class_id
        )
        assert checking_after == checking_before - Decimal("20.00")
        assert savings_after == savings_before + Decimal("20.00")
        legs = Transaction.query.filter_by(class_id=class_id, seat_id=seat_id).filter(
            Transaction.type.in_(["Withdrawal", "Deposit"])
        ).order_by(Transaction.id.desc()).limit(2).all()
        assert len(legs) == 2
        assert len({leg.command_reservation_id for leg in legs}) == 1
        reservation = db.session.get(LedgerCommandReservation, legs[0].command_reservation_id)
        assert reservation is not None
        assert Transaction.query.filter_by(command_reservation_id=reservation.id).count() == 2
        from app.services.ledger_transfer_service import verify_transfer
        assert verify_transfer(class_id, legs[0].correlation_id).outcome == "UNAVAILABLE"
