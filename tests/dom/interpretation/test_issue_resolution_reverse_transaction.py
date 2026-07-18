from decimal import Decimal

from app.extensions import db
from app.models import Transaction, TransactionStatus
from tests.dom.interpretation.helpers import issue_reverse_state
from app.utils.opaque_refs import make_opaque_ref


def test_DOM_SUP_001__issue_reverse_transaction_creates_reversal_for_posted_tx(client, app):
    class_a, _class_b, student, issue, tx = issue_reverse_state(client, app)

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
    assert reversal.class_id == class_a.class_id
    assert reversal.amount == Decimal("-30.00")


def test_DOM_SUP_001__issue_reverse_transaction_rejects_scope_mismatch(client, app):
    class_a, _class_b, student, issue, tx = issue_reverse_state(client, app)

    issue_ref = make_opaque_ref("issue", issue.id)
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
