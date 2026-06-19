"""
FEAT-STOR-006: Redemption Disposition

Owns the canonical mutation path for resolving a pending redemption request.

Two business actions share this FEAT:
  - approve: redemption confirmed by the teacher; the held inventory item is
    consumed and the associated 'redemption' ledger entry is finalized.
  - reject: redemption refused by the teacher; the original purchase is
    refunded via a new ledger transaction and the item is marked rejected.

This FEAT is intentionally named for the business action ("Redemption
Disposition"), not the storage implementation. Wave 8 will split
`StudentItem` into `StorePurchase` + `RedemptionEvent`; when that happens,
this FEAT's body changes but its contract — "dispose a pending redemption
request" — does not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from flask import current_app

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import (
    RedemptionAuditAction,
    RedemptionAuditLog,
    RedemptionAuditSource,
    StudentItem,
    Transaction,
)
from app.services.ledger_service import create_pending_transaction_idempotent
from app.utils.time import ensure_utc, utc_now, UTC_MIN
from app.utils.transaction_idempotency import student_item_refund_key


# -------------------- Public contract --------------------


@dataclass
class RedemptionDispositionResult:
    """Outcome of a redemption disposition."""

    disposition: str  # 'approved' | 'rejected'
    student_item_id: int
    audit_log_id: int
    refund_transaction_id: Optional[int] = None
    refund_amount: Optional[Decimal] = None
    message: str = ""


class RedemptionDispositionError(Exception):
    """
    Raised for business-rule failures during redemption disposition.

    Distinct from FEATContextError (architectural violation) and SQLAlchemyError
    (infrastructure failure). Routes may convert this to a 4xx response.
    """


# -------------------- Internal helpers --------------------


def _resolve_class_display_label(class_id, join_code, fallback_block):
    """Snapshot a stable class label for audit purposes."""
    from app.models import ClassEconomy

    if class_id:
        economy = ClassEconomy.query.filter_by(class_id=class_id).first()
        if economy:
            return economy.display_name or economy.join_code
    if join_code:
        economy = ClassEconomy.query.filter_by(join_code=join_code).first()
        if economy:
            return economy.display_name or economy.join_code
    return fallback_block or "Unknown Class"


def _write_audit_row(*, student_item, student, teacher_id, action, notes):
    """Append a single live audit row and return its id."""
    action_map = {
        "approved": RedemptionAuditAction.APPROVED,
        "rejected": RedemptionAuditAction.REJECTED,
    }
    if action not in action_map:
        raise RedemptionDispositionError(f"Unsupported disposition action: {action}")

    class_id = getattr(student_item, "class_id", None)
    join_code = getattr(student_item, "join_code", None)
    fallback_block = student.block if student else None
    class_label = _resolve_class_display_label(class_id, join_code, fallback_block)

    audit_row = RedemptionAuditLog(
        student_item_id=student_item.id,
        class_display_label=class_label,
        action=action_map[action],
        notes=notes if notes else None,
        teacher_id=teacher_id,
        class_id=class_id,
        seat_id=student_item.seat_id,
        timestamp=utc_now(),
        source=RedemptionAuditSource.LIVE,
    )
    db.session.add(audit_row)
    db.session.flush()
    return audit_row.id


def _find_original_purchase_tx(student_item):
    """Locate the closest-by-timestamp purchase transaction for this item."""
    item_name = student_item.store_item.name if student_item.store_item else None
    if not item_name:
        return None

    candidates = (
        Transaction.query.filter_by(
            seat_id=student_item.seat_id,
            class_id=student_item.class_id,
            type="purchase",
        )
        .filter(Transaction.description.like(f"Purchase: {item_name}%"))
        .all()
    )
    if not candidates:
        return None

    if student_item.purchase_date:
        target_ts = ensure_utc(student_item.purchase_date)

        def _distance(tx):
            if not tx.timestamp:
                return float("inf")
            return abs((ensure_utc(tx.timestamp) - target_ts).total_seconds())

        return min(candidates, key=_distance)

    return max(
        candidates,
        key=lambda tx: ensure_utc(tx.timestamp) if tx.timestamp else UTC_MIN,
    )


def _compute_refund_amount(student_item, purchase_tx) -> Decimal:
    """Derive the per-unit refund amount from the original purchase, or fall back to current price."""
    if purchase_tx and purchase_tx.amount is not None:
        total_amount = abs(purchase_tx.amount)
        quantity = 1
        if purchase_tx.description:
            match = re.search(r"\(x(\d+)\)", purchase_tx.description)
            if match:
                try:
                    parsed = int(match.group(1))
                    if parsed > 0:
                        quantity = parsed
                except ValueError:
                    pass
        return total_amount / quantity
    return student_item.store_item.price


# -------------------- Public FEAT entry points --------------------


@requires_feat_context("FEAT-STOR-006")
def execute_redemption_approval(
    *,
    student_item: StudentItem,
    actor_teacher_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    """
    Approve a pending redemption request.

    Side effects (all inside this FEAT's transaction):
      - Insert a `RedemptionAuditLog(action=APPROVED, source=LIVE)` row.
      - Mutate `student_item.status` from 'processing' to 'completed'.
      - Rewrite the matching pending redemption transaction's description
        from "Used: <name>" to "Redeemed: <name>".

    Raises `RedemptionDispositionError` if `student_item.status != 'processing'`.
    """
    if student_item.status != "processing":
        raise RedemptionDispositionError(
            f"StudentItem {student_item.id} is not in 'processing' state; cannot approve."
        )

    audit_log_id = _write_audit_row(
        student_item=student_item,
        student=student_item.student,
        teacher_id=actor_teacher_id,
        action="approved",
        notes=notes,
    )

    student_item.status = "completed"

    item_name = student_item.store_item.name if student_item.store_item else None
    if item_name:
        redemption_tx = (
            Transaction.query.filter_by(
                seat_id=student_item.seat_id,
                class_id=student_item.class_id,
                type="redemption",
            )
            .filter(Transaction.description.like(f"Used: {item_name}%"))
            .order_by(Transaction.timestamp.desc())
            .first()
        )
        if redemption_tx:
            redemption_tx.description = f"Redeemed: {item_name}"

    db.session.flush()

    return RedemptionDispositionResult(
        disposition="approved",
        student_item_id=student_item.id,
        audit_log_id=audit_log_id,
        message="Redemption approved.",
    )


@requires_feat_context("FEAT-STOR-006")
def execute_redemption_rejection(
    *,
    student_item: StudentItem,
    actor_teacher_id: int,
    notes: Optional[str] = None,
) -> RedemptionDispositionResult:
    """
    Reject a pending redemption request and refund the student.

    Side effects (all inside this FEAT's transaction):
      - Insert a `RedemptionAuditLog(action=REJECTED, source=LIVE)` row.
      - Create a pending refund Transaction (idempotent on the redemption-rejected
        key) crediting the student's checking account by the per-unit purchase price.
      - Link the original purchase Transaction's `reversal_transaction_id` to the
        new refund row.
      - Mutate `student_item.status` to 'rejected' and append a status note to
        `redemption_details`.

    Raises:
      - `RedemptionDispositionError` if `student_item.status != 'processing'` or
        if `class_id` is missing (cannot scope the refund).
    """
    if student_item.status != "processing":
        raise RedemptionDispositionError(
            f"StudentItem {student_item.id} is not in 'processing' state; cannot reject."
        )

    refund_class_id = student_item.class_id
    if not refund_class_id:
        current_app.logger.error(
            "StudentItem %s missing class_id during refund. Aborting to avoid unscoped transaction.",
            student_item.id,
        )
        raise RedemptionDispositionError("Unable to resolve class for refund.")

    audit_log_id = _write_audit_row(
        student_item=student_item,
        student=student_item.student,
        teacher_id=actor_teacher_id,
        action="rejected",
        notes=notes,
    )

    purchase_tx = _find_original_purchase_tx(student_item)
    refund_amount = _compute_refund_amount(student_item, purchase_tx)

    refund_tx, _created = create_pending_transaction_idempotent(
        idempotency_key=student_item_refund_key(student_item.id, "redemption-rejected"),
        seat_id=student_item.seat_id,
        class_id=refund_class_id,
        teacher_id=student_item.store_item.teacher_id,
        amount=refund_amount,
        account_type="checking",
        type="refund",
        original_transaction_id=purchase_tx.id if purchase_tx else None,
        description=f"Refund: {student_item.store_item.name} (Redemption Rejected)",
    )
    if purchase_tx:
        purchase_tx.reversal_transaction_id = refund_tx.id

    student_item.status = "rejected"
    student_item.redemption_date = utc_now()
    if student_item.redemption_details:
        student_item.redemption_details = f"{student_item.redemption_details}\n---\nStatus: rejected"
    else:
        student_item.redemption_details = "Status: rejected"

    db.session.flush()

    return RedemptionDispositionResult(
        disposition="rejected",
        student_item_id=student_item.id,
        audit_log_id=audit_log_id,
        refund_transaction_id=refund_tx.id,
        refund_amount=refund_amount,
        message="Redemption rejected and refunded.",
    )
