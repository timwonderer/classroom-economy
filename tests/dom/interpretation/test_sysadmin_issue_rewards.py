from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import (
    Issue,
    IssueCategory,
    IssueResolutionAction,
    Transaction,
    TransactionStatus,
)
from app.utils.opaque_refs import make_opaque_ref
from app.feats.base import FEATContext
from tests.dom.interpretation.helpers import (
    create_sysadmin_via_cli,
    login_sysadmin,
    sysadmin_reward_issue_state,
)


def test_DOM_SUP_001__sysadmin_resolve_issue_issues_bug_reward_transaction(client, app):
    classroom, student, issue = sysadmin_reward_issue_state(client, app)
    sysadmin, sysadmin_secret = create_sysadmin_via_cli(app, username="sysadmin_issue_reward")
    login_sysadmin(client, "sysadmin_issue_reward", sysadmin_secret)

    issue_ref = make_opaque_ref("issue", issue.id)
    resp = client.post(
        f"/sysadmin/issues/{issue_ref}/resolve",
        data={
            "resolution_note": "Confirmed and fixed.",
            "eligible_for_reward": "on",
            "reward_amount": "4.50",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.session.refresh(issue)
    assert issue.status == Issue.STATUS_DEV_RESOLVED
    assert issue.eligible_for_reward is True
    assert issue.sysadmin_id == sysadmin.id
    assert issue.sysadmin_resolved_at is not None

    reward_tx = Transaction.query.filter(
        Transaction.seat_id == student.seat.id,
        Transaction.user_id == student.user.id,
        Transaction.class_id == classroom.class_id,
        Transaction.type == "bug_reward",
    ).first()
    assert reward_tx is not None
    assert reward_tx.amount == Decimal("4.50")
    assert reward_tx.account_type == "checking"
    assert reward_tx.status == TransactionStatus.PENDING
    assert "Issue" in (reward_tx.description or "")

    reward_action = IssueResolutionAction.query.filter_by(
        issue_id=issue.id,
        action_type="bug_reward_issued",
    ).first()
    assert reward_action is not None
    assert reward_action.related_transaction_id == reward_tx.id
