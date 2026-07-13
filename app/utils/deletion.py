import logging
from typing import Optional

from flask import current_app
from sqlalchemy import func, or_, case, select

from app.extensions import db
from app.models import (
    ClassEconomy, Seat, Transaction,
    AttendanceSession, HallPassLog, RedemptionAuditLog, StorePurchase, RedemptionEvent, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    InsuranceEnrollment, RentPayment, Announcement, StoreItemBlock, StoreItem,
    PayrollSettings, RentSettings,
    InsurancePolicyBlock,
)
from app.feats.base import feat_shell, InvariantViolation

logger = logging.getLogger(__name__)


def _raise_invariant_violation(message: str) -> None:
    logger.critical("P0 INVARIANT VIOLATION: %s", message)
    raise InvariantViolation(message)


def _assert_class_scope_integrity(class_id: str) -> None:
    scoped_models = (
        ("ledger_transaction", Transaction),
        ("hall_pass_logs", HallPassLog),
        ("store_purchases", StorePurchase),
        ("redemption_events", RedemptionEvent),
        ("analytics_events", AnalyticsEvent),
        ("analytics_snapshots", AnalyticsSnapshot),
        ("issues", Issue),
        ("insurance_enrollments", InsuranceEnrollment),
        ("rent_payments", RentPayment),
        ("announcements", Announcement),
    )
    violations = []
    for label, model in scoped_models:
        if not hasattr(model, 'class_id'):
            continue
        count = db.session.query(model).filter(
            model.class_id.is_(None),
        ).count()
        if count:
            violations.append(f"{label}={count}")

    if violations:
        _raise_invariant_violation(
            f"class_id NULL rows detected for class_id={class_id}: {', '.join(violations)}"
        )

@feat_shell("FEAT-OPS-001")
def collapse_universe(class_id: str, reason: str, actor_membership_id: Optional[int]) -> bool:
    """
    Canonical destruction primitive for a class economy.
    
    A deleted class MUST leave zero remaining rows in any table scoped by that class.
    There is no soft delete. There is no archive state. There is no preserved financial history.
    
    Args:
        class_id: Canonical class boundary to collapse.
        reason: An audit reason for the deletion (logged).
        actor_seat_id: The Seat ID of the actor performing the deletion.
        
    Returns:
        True if the universe was collapsed (or didn't exist), False if an error occurred.
    """
    if not class_id:
        return True  # Idempotency: If class_id does not exist, return success.

    try:
        economy = db.session.get(ClassEconomy, class_id)
        if not economy:
            return True
        _assert_class_scope_integrity(class_id)

        logger.info(
            "Collapsing universe for class_id=%s. Reason: %s. Actor: %s",
            class_id,
            reason,
            actor_membership_id,
        )

        # 1. Identify affected seats and student-scoped rows for this class
        user_id = economy.user_id
        affected_seat_blocks = [
            b for (b,) in db.session.query(ClassEconomy.section).filter(
                ClassEconomy.class_id == class_id,
                ClassEconomy.section.isnot(None),
            ).distinct().all()
        ]
        affected_student_ids_seat = [
            s_id for (s_id,) in db.session.query(Seat.user_id)
            .filter(Seat.class_id == class_id, Seat.user_id.isnot(None))
            .distinct().all()
        ]
        affected_student_ids = list(set(affected_student_ids_seat))

        # Many tables are handled by ON DELETE CASCADE from ClassEconomy
        # (e.g. BalanceCache, Transaction, AttendanceSession, RentPayment, ClassJoinCodeAlias)
        # We explicitly delete the others or things that require manual cleanup first

        # 2. Activity / State Logs & Records (Not all have ON DELETE CASCADE yet)
        HallPassLog.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsSnapshot.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsEvent.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        Announcement.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 3. Insurance & Issue Data
        issue_ids_sel = select(Issue.id).filter_by(class_id=class_id)
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(issue_ids_sel)
        ).delete(synchronize_session=False)
        Issue.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        insurance_ids_sel = select(InsuranceEnrollment.id).filter_by(class_id=class_id)
        tx_ids_sel = select(Transaction.id).filter_by(class_id=class_id)
        InsuranceClaim.query.filter(
            or_(
                InsuranceClaim.enrollment_id.in_(insurance_ids_sel),
                InsuranceClaim.transaction_id.in_(tx_ids_sel)
            )
        ).delete(synchronize_session=False)
        InsuranceEnrollment.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 4. Inventory / Store Data
        store_purchase_ids_subq = select(StorePurchase.id).filter_by(class_id=class_id).subquery()
        RedemptionEvent.query.filter(
            RedemptionEvent.purchase_id.in_(select(store_purchase_ids_subq))
        ).delete(synchronize_session=False)
        StorePurchase.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 4b. StoreItemBlocks for this class (class-scoped; also handled by FK cascade on class deletion)
        StoreItemBlock.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        # Delete StoreItems that now have NO remaining StoreItemBlock visibility entries for this class
        deletable_store_items = (
            db.session.query(StoreItem.id)
            .outerjoin(StoreItemBlock, StoreItem.id == StoreItemBlock.store_item_id)
            .filter(
                StoreItem.class_id == class_id,
                StoreItemBlock.store_item_id.is_(None),
            )
            .subquery()
        )
        StoreItem.query.filter(StoreItem.id.in_(select(deletable_store_items))).delete(synchronize_session=False)

        # 5. Delete Seats for this class (also handled by FK cascade on ClassEconomy deletion)
        Seat.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 6. Delete the ClassEconomy itself (triggers ON DELETE CASCADE for Transactions, Memberships, etc.)
        db.session.delete(economy)

        # 7. Post-collapse: Seat erasure and link cleanup
        # If a seat owner has zero remaining seats under the current teacher's classes, continue erasure checks.
        # If they have zero across all teachers, fully delete the student record.
        if affected_student_ids:
            for s_id in affected_student_ids:
                # Full erasure if totally orphaned across all teachers
                remaining_seats = db.session.query(Seat.id).filter(Seat.user_id == s_id).count()
                if remaining_seats == 0:
                    logger.info(f"Seat erasure rule triggered for student_id={s_id}")

        # 8. Post-collapse: Settings cleanup
        # If no remaining seat exists for that section name in the current owner's other classes, delete insurance policy sections.
        if affected_seat_blocks:
            for block_name in affected_seat_blocks:
                remaining = (
                    db.session.query(Seat.id)
                    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                    .filter(
                        ClassEconomy.section == block_name,
                        ClassEconomy.user_id == user_id,
                    )
                    .count()
                )
                if remaining == 0:
                    logger.info(f"Settings Cleanup Rule triggered for section={block_name}, user_id={user_id}")
                    InsurancePolicyBlock.query.filter_by(block=block_name).delete(synchronize_session=False)

        db.session.flush()  # FEAT-AUTHORIZED-SHELL
        return True

    except InvariantViolation:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to collapse universe for class_id={class_id}: {e}", exc_info=True)
        return False
