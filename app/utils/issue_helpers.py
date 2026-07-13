"""
Helper functions for the Issue Resolution System.

Provides utilities for creating issues, managing status changes, and ensuring
proper data minimization for sysadmin review.
"""

from datetime import datetime, timezone
from app.utils.time import utc_now
from decimal import Decimal
from flask import request, current_app
import hashlib
import secrets

from app.extensions import db
from app.models import (
    Issue,
    IssueStatusHistory,
    IssueResolutionAction,
    Transaction,
    ClassEconomy,
    Seat,
    IdentityProfile,
)
from app.utils.ip_handler import get_real_ip
from app.services.tlcp import create_ticket_correlation_pack
from app.feats.base import feat_shell
from app.utils.join_code import get_display_join_code


def _resolve_actor_seat(actor):
    if actor is None:
        return None
    if isinstance(actor, Seat):
        return actor
    identity_profile = getattr(actor, "identity_profile", None)
    if identity_profile and getattr(identity_profile, "seat", None):
        return identity_profile.seat
    return getattr(actor, "seat", None)


def create_context_snapshot(actor, class_id, related_transaction_id=None, related_record_type=None, related_record_id=None):
    """
    Create an immutable snapshot of system context for an issue.

    Args:
        actor: Seat or legacy student-like instance with an identity_profile->seat path
        class_id: Canonical class ID (UUID)
        related_transaction_id: Optional transaction ID for transaction-specific issues
        related_record_type: Optional record type ('transaction', 'tap_event', etc.)
        related_record_id: Optional record ID

    Returns:
        dict: Context snapshot with ledger state, amounts, timestamps, etc.
    """
    snapshot = {
        'timestamp': utc_now().isoformat(),
        'page_url': request.url if request else None,
        'user_agent': request.headers.get('User-Agent') if request else None,
        'ip_address': get_real_ip() if request else None,
    }

    if not class_id:
        raise ValueError("create_context_snapshot requires canonical class_id scope.")
    seat = _resolve_actor_seat(actor)
    if not seat:
        raise ValueError("create_context_snapshot requires canonical seat_id scope.")

    # Get current balances (scoped by class_id + seat_id)
    # Convert Decimal to float for JSON serialization (db.JSON column)
    checking_balance = seat.get_checking_balance(class_id=class_id, seat_id=seat.id)
    savings_balance = seat.get_savings_balance(class_id=class_id, seat_id=seat.id)
    snapshot['balances'] = {
        'checking': float(checking_balance),
        'savings': float(savings_balance),
        'total': float(checking_balance + savings_balance)
    }

    # If transaction-specific, include transaction details
    if related_transaction_id:
        transaction = db.session.get(Transaction, related_transaction_id)
        if transaction:
            snapshot['transaction'] = {
                'id': transaction.id,
                'amount': float(transaction.amount),
                'account_type': transaction.account_type,
                'description': transaction.description,
                'type': transaction.type,
                'timestamp': transaction.timestamp.isoformat() if transaction.timestamp else None,
                'is_void': transaction.is_void
            }

    # Get recent transaction history (last 10 transactions for context)
    recent_transactions = Transaction.query.filter_by(
        seat_id=seat.id,
        class_id=class_id
    ).order_by(Transaction.timestamp.desc()).limit(10).all()

    snapshot['recent_transactions'] = [
        {
            'id': t.id,
            'amount': float(t.amount),
            'description': t.description,
            'timestamp': t.timestamp.isoformat() if t.timestamp else None
        }
        for t in recent_transactions
    ]

    return snapshot


@feat_shell("FEAT-SUP-001")
def create_issue(actor, user_id, class_id, category_id, explanation, expected_outcome=None,
                 related_transaction_id=None, related_record_type=None, related_record_id=None,
                 include_recent_error=True):
    """
    Create a new issue submission.

    Args:
        actor: Seat or legacy student-like instance with an identity_profile->seat path
        user_id: Canonical owner user ID
        class_id: Canonical class ID (UUID)
        category_id: IssueCategory ID
        explanation: Student's explanation of the issue
        expected_outcome: Optional - what student expected to happen
        related_transaction_id: Optional - for transaction-specific issues
        related_record_type: Optional - type of related record
        related_record_id: Optional - ID of related record
        include_recent_error: Whether to include recent server errors in the ticket pack

    Returns:
        Issue: Created issue instance
    """
    from app.models import ClassEconomy, IssueCategory

    # Get category to determine issue_type
    category = db.session.get(IssueCategory, category_id)
    if not category:
        raise ValueError("Invalid category")

    # Resolve class label and join_code from ClassEconomy
    class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
    join_code = get_display_join_code(class_row.class_id) if class_row else None
    class_label = (class_row.display_name if class_row and class_row.display_name else None) or join_code or class_id
    canonical_seat = _resolve_actor_seat(actor)
    if not canonical_seat:
        raise ValueError("create_issue requires canonical seat public_id scope.")

    # v2 public support identity is the deidentified class-scoped seat UUID.
    actor_public_id = canonical_seat.public_id

    # Create context snapshot
    context_snapshot = create_context_snapshot(
        actor, class_id, related_transaction_id, related_record_type, related_record_id
    )

    now_utc = utc_now()

    # Create the issue
    issue = Issue(
        seat_id=canonical_seat.id,
        actor_public_id=actor_public_id,
        teacher_id=user_id,
        class_id=class_id,
        join_code=join_code,
        class_label=class_label,
        category_id=category_id,
        issue_type=category.category_type,
        student_explanation=explanation,
        student_expected_outcome=expected_outcome,
        related_transaction_id=related_transaction_id,
        related_record_type=related_record_type,
        related_record_id=related_record_id,
        context_snapshot=context_snapshot,
        page_url=request.url if request else None,
        status=Issue.STATUS_OPEN,
        submitted_at=now_utc,
        created_at=now_utc,
        updated_at=now_utc
    )

    db.session.add(issue)
    db.session.flush()  # Get the issue ID

    # Attach immutable correlation snapshot at submission time inside the FEAT boundary.
    create_ticket_correlation_pack(
        issue_id=issue.id,
        actor_type='student',
        actor_public_id=actor_public_id,
        class_id=class_id,
        ticket_created_at=now_utc,
        include_recent_error=include_recent_error,
    )

    # Record status history
    record_status_change(issue, None, Issue.STATUS_OPEN, 'student', canonical_seat.id)

    db.session.flush()  # FEAT-AUTHORIZED-SHELL

    return issue


def record_status_change(issue, previous_status, new_status, changed_by_type, changed_by_id, notes=None):
    """
    Record a status change in the issue history.

    Args:
        issue: Issue model instance
        previous_status: Previous status (or None for initial submission)
        new_status: New status
        changed_by_type: Type of user making change ('student', 'teacher', 'sysadmin', 'system')
        changed_by_id: ID of user making change
        notes: Optional notes about the change
    """
    history = IssueStatusHistory(
        issue_id=issue.id,
        previous_status=previous_status,
        new_status=new_status,
        changed_by_type=changed_by_type,
        changed_by_id=changed_by_id,
        notes=notes,
        changed_at=utc_now()
    )

    db.session.add(history)


def record_resolution_action(issue, action_type, performed_by_type, performed_by_id,
                             action_description=None, related_transaction_id=None,
                             amount_changed=None, before_value=None, after_value=None):
    """
    Record a resolution action taken on an issue.

    Args:
        issue: Issue model instance
        action_type: Type of action ('reverse_transaction', 'correct_amount', etc.)
        performed_by_type: Type of user ('teacher', 'sysadmin')
        performed_by_id: ID of user performing action
        action_description: Optional description of the action
        related_transaction_id: Optional transaction ID if action affects a transaction
        amount_changed: Optional amount that was changed
        before_value: Optional before state
        after_value: Optional after state
    """
    action = IssueResolutionAction(
        issue_id=issue.id,
        action_type=action_type,
        action_description=action_description,
        performed_by_type=performed_by_type,
        performed_by_id=performed_by_id,
        related_transaction_id=related_transaction_id,
        amount_changed=amount_changed,
        before_value=before_value,
        after_value=after_value,
        created_at=utc_now()
    )

    db.session.add(action)


def update_issue_status(issue, new_status, changed_by_type, changed_by_id, notes=None):
    """
    Update issue status and record the change in history.

    Args:
        issue: Issue model instance
        new_status: New status value
        changed_by_type: Type of user making change
        changed_by_id: ID of user making change
        notes: Optional notes about the change
    """
    previous_status = issue.status
    issue.status = new_status
    issue.updated_at = utc_now()

    record_status_change(issue, previous_status, new_status, changed_by_type, changed_by_id, notes)
