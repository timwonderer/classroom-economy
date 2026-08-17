from __future__ import annotations

import secrets
from decimal import Decimal
from datetime import datetime
from flask import current_app

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import Issue, Seat, ClassEconomy, User
from app.utils.temporal_display import utc_now


@requires_feat_context("FEAT-OPS-001")
def execute_sysadmin_login_success(
    *,
    user: User,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    """Execute sysadmin login mutations."""
    nonce = secrets.token_urlsafe(32)
    user.current_session_nonce = nonce
    return nonce


@requires_feat_context("FEAT-OPS-001")
def execute_sysadmin_passkey_auth_success(
    *,
    user: User,
    now: datetime,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    """Execute sysadmin passkey auth mutations."""
    from app.services.passwordless_service import touch_admin_credentials_last_used
    
    touch_admin_credentials_last_used(user.id, now)
    nonce = secrets.token_urlsafe(32)
    user.current_session_nonce = nonce
    return nonce


@requires_feat_context("FEAT-OPS-001")
def execute_resolve_escalated_issue(
    *,
    issue: Issue,
    resolution_note: str,
    sysadmin_user_id: int,
    eligible_for_reward: bool,
    reward_amount_value: Decimal | None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Resolve an escalated issue with an optional bug bounty."""
    from app.services import ledger_service
    from app.utils.issue_helpers import record_status_change, record_resolution_action
    
    old_status = issue.status
    issue.status = Issue.STATUS_DEV_RESOLVED
    issue.sysadmin_resolved_at = utc_now()
    issue.sysadmin_notes = resolution_note
    issue.sysadmin_id = sysadmin_user_id
    issue.eligible_for_reward = eligible_for_reward

    if reward_amount_value is not None:
        reward_seat = Seat.query.filter_by(public_id=issue.actor_public_id).first()
        if not reward_seat:
            raise ValueError("Cannot issue reward: actor seat not found.")
            
        reward_class = ClassEconomy.query.filter_by(class_public_id=issue.class_public_id).first()
        reward_transaction = ledger_service.create_pending_transaction(
            seat_id=reward_seat.id,
            class_id=reward_class.class_id if reward_class else None,
            target_seat_id=reward_seat.id,
            actor_seat_id=reward_seat.id,
            mechanism="system",
            user_id=reward_seat.user_id,
            amount=reward_amount_value,
            account_type='checking',
            description=f"Bug Reward (Issue #{issue.id})",
            type='bug_reward',
        )

        record_resolution_action(
            issue,
            action_type='bug_reward_issued',
            performed_by_type='sysadmin',
            performed_by_public_id=None,
            action_description=f"Issued bug reward while resolving issue #{issue.id}",
            related_transaction_id=reward_transaction.id,
            amount_changed=float(reward_amount_value),
            before_value='0.00',
            after_value=str(reward_amount_value),
        )

    reward_note = (
        f" | Bug reward: ${reward_amount_value:.2f}"
        if reward_amount_value is not None
        else ""
    )
    record_status_change(
        issue,
        old_status,
        Issue.STATUS_DEV_RESOLVED,
        'sysadmin',
        None,
        notes=f"{resolution_note}{reward_note}",
    )
