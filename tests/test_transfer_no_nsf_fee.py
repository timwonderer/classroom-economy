"""A transfer is lateral movement, not spending — insufficient funds is invalid.

A transfer between the seat's OWN accounts (checking<->savings) is not a failed
agreement. On insufficient funds it must simply decline: it does NOT proceed and
does NOT incur an NSF fee. NSF is charged only where money was meant to leave for
a purchase or to meet an obligation. Regression for the checking-insufficient
transfer branch, which previously charged a forced overdraft fee.
"""

from __future__ import annotations

from app.models import Transaction, ObligationAssessment
from tests.helpers.classroom_initializer import initialize_as_student


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

    # A fresh student has no checking balance, so any checking->savings transfer
    # is over-balance and must be declined.
    resp = client.post(
        "/student/transfer",
        data={"from_account": "checking", "to_account": "savings", "amount": "10.00"},
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
