from decimal import Decimal

from app.extensions import db
from app.models import Transaction, TransactionStatus
from tests.dom.interpretation.helpers import (
    issue_reverse_scope_mismatch_state,
    issue_reverse_success_state,
)
from app.utils.opaque_refs import make_opaque_ref


def test_DOM_SUP_001__issue_reverse_transaction_creates_reversal_for_posted_tx(client, app):
    """In-scope reversal: submitter owns the referenced POSTED transaction and
    the teacher's active class matches the issue's class, so the reversal
    succeeds."""
    classroom, student, issue, tx = issue_reverse_success_state(client, app)

    issue_ref = make_opaque_ref("issue", issue.id)
    response = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Valid request"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db.session.refresh(tx)
    assert tx.is_void is True
    assert tx.status == TransactionStatus.POSTED
    assert tx.reversal_transaction_id is not None

    reversal = db.session.get(Transaction, tx.reversal_transaction_id)
    assert reversal is not None
    assert reversal.original_transaction_id == tx.id
    assert reversal.status == TransactionStatus.PENDING
    assert reversal.class_id == classroom.class_id
    assert reversal.amount == Decimal("-30.00")


def test_DOM_SUP_001__issue_reverse_transaction_rejects_scope_mismatch(client, app):
    """Ownership-mismatch rejection: the issue is visible under the teacher's
    active class (no 404), but the referenced transaction belongs to a different
    seat than the submitter, so the reversal is rejected and the transaction is
    left untouched."""
    classroom, submitter, other_student, issue, tx = issue_reverse_scope_mismatch_state(client, app)

    # Sanity: the rejection must be driven by the intended ownership mismatch,
    # not by issue invisibility or an active-class mismatch.
    submitter_seat_id = submitter.seat.id
    assert tx.seat_id == other_student.seat.id
    assert tx.seat_id != submitter_seat_id
    assert issue.class_public_id == classroom.economy.class_public_id

    issue_ref = make_opaque_ref("issue", issue.id)

    # The issue detail page is reachable (visible in the active class scope):
    # confirms the rejection below is not merely a 404 from scope filtering.
    view_response = client.get(f"/admin/issues/{issue_ref}")
    assert view_response.status_code == 200

    response = client.post(
        f"/admin/issues/{issue_ref}/resolve",
        data={"action_type": "reverse_transaction", "teacher_notes": "Attempt mismatch"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/admin/issues/{issue_ref}" in response.location

    db.session.refresh(tx)
    assert tx.is_void is False
    assert tx.reversal_transaction_id is None
