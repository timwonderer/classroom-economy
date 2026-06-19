import logging
from typing import Optional

from flask import current_app
from sqlalchemy import func, or_, case, select

from app.extensions import db
from app.models import (
    ClassEconomy, ClassMembership, Seat, Transaction, StudentBlock,
    AttendanceSession, HallPassLog, RedemptionAuditLog, StudentItem, AnalyticsEvent,
    AnalyticsSnapshot, Issue, IssueResolutionAction, InsuranceClaim,
    StudentInsurance, RentPayment, Announcement, StoreItemBlock, StoreItem,
    Student, StudentTeacher, PayrollSettings, RentSettings,
    InsurancePolicyBlock,
)
from app.feats.base import feat_shell, InvariantViolation

logger = logging.getLogger(__name__)


def _raise_invariant_violation(message: str) -> None:
    logger.critical("P0 INVARIANT VIOLATION: %s", message)
    raise InvariantViolation(message)


def _assert_class_scope_integrity(class_id: str, join_code: str) -> None:
    scoped_models = (
        ("ledger_transaction", Transaction),
        ("student_blocks", StudentBlock),
        ("hall_pass_logs", HallPassLog),
        ("student_items", StudentItem),
        ("analytics_events", AnalyticsEvent),
        ("analytics_snapshots", AnalyticsSnapshot),
        ("issues", Issue),
        ("student_insurance", StudentInsurance),
        ("rent_payments", RentPayment),
        ("announcements", Announcement),
    )
    violations = []
    for label, model in scoped_models:
        count = db.session.query(model).filter(
            model.join_code == join_code,
            model.class_id.is_(None),
        ).count()
        if count:
            violations.append(f"{label}={count}")

    # Check for StudentBlock rows with null class_id inferred from active seats in this class
    seat_student_ids = [
        s_id for (s_id,) in db.session.query(Seat.student_id).filter(
            Seat.class_id == class_id,
            Seat.student_id.isnot(None),
        ).distinct().all()
    ]
    seat_blocks = [
        b for (b,) in db.session.query(Seat.block).filter(
            Seat.class_id == class_id,
            Seat.block.isnot(None),
        ).distinct().all()
    ]
    if seat_student_ids and seat_blocks:
        inferred_student_block_nulls = db.session.query(StudentBlock).filter(
            StudentBlock.student_id.in_(seat_student_ids),
            StudentBlock.period.in_(seat_blocks),
            StudentBlock.class_id.is_(None),
        ).count()
        if inferred_student_block_nulls:
            violations.append(f"student_blocks_inferred={inferred_student_block_nulls}")

    if violations:
        _raise_invariant_violation(
            f"class_id NULL rows detected for class_id={class_id} join_code={join_code}: {', '.join(violations)}"
        )

@feat_shell("FEAT-OPS-001")
def collapse_universe(class_id: str, reason: str, actor_membership_id: Optional[int]) -> bool:
    """
    Canonical destruction primitive for a class economy.
    
    The boundary may enter through `join_code`, but this primitive executes on the
    canonical `class_id` anchor only.

    A deleted class MUST leave zero remaining rows in any table scoped by that class.
    There is no soft delete. There is no archive state. There is no preserved financial history.
    
    Args:
        class_id: Canonical class boundary to collapse.
        reason: An audit reason for the deletion (logged).
        actor_membership_id: The ClassMembership ID of the actor performing the deletion.
        
    Returns:
        True if the universe was collapsed (or didn't exist), False if an error occurred.
    """
    if not class_id:
        return True  # Idempotency: If class_id does not exist, return success.

    try:
        economy = db.session.get(ClassEconomy, class_id)
        if not economy:
            return True
        join_code = economy.join_code
        _assert_class_scope_integrity(class_id, join_code)

        logger.info(
            "Collapsing universe for class_id=%s join_code=%s. Reason: %s. Actor: %s",
            class_id,
            join_code,
            reason,
            actor_membership_id,
        )

        # 1. Identify affected Seats and Students for this class
        teacher_id = economy.teacher_id
        affected_seat_blocks = [
            b for (b,) in db.session.query(Seat.block).filter(
                Seat.class_id == class_id,
                Seat.block.isnot(None),
            ).distinct().all()
        ]
        affected_student_ids_seat = [
            s_id for (s_id,) in db.session.query(Seat.student_id).filter(
                Seat.class_id == class_id,
                Seat.student_id.isnot(None),
            ).distinct().all()
        ]
        affected_student_ids_sb = [
            s_id for (s_id,) in db.session.query(StudentBlock.student_id).filter(
                StudentBlock.class_id == class_id,
                StudentBlock.student_id.isnot(None)
            ).distinct().all()
        ]
        affected_student_ids = list(set(affected_student_ids_seat + affected_student_ids_sb))

        # Many tables are handled by ON DELETE CASCADE from ClassEconomy
        # (e.g. BalanceCache, Transaction, StudentBlock, AttendanceSession, RentPayment, ClassMembership, ClassJoinCodeAlias)
        # We explicitly delete the others or things that require manual cleanup first

        # 2. Activity / State Logs & Records (Not all have ON DELETE CASCADE yet)
        HallPassLog.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsSnapshot.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        AnalyticsEvent.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        Announcement.query.filter_by(class_id=class_id).delete(synchronize_session=False)
        StudentBlock.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 3. Insurance & Issue Data
        issue_ids_subq = select(Issue.id).filter_by(class_id=class_id).subquery()
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(select(issue_ids_subq))
        ).delete(synchronize_session=False)
        Issue.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        insurance_ids_subq = select(StudentInsurance.id).filter_by(class_id=class_id).subquery()
        tx_ids_subq = select(Transaction.id).filter_by(class_id=class_id).subquery()
        InsuranceClaim.query.filter(
            or_(
                InsuranceClaim.enrollment_id.in_(select(insurance_ids_subq)),
                InsuranceClaim.transaction_id.in_(select(tx_ids_subq))
            )
        ).delete(synchronize_session=False)
        StudentInsurance.query.filter_by(class_id=class_id).delete(synchronize_session=False)

        # 4. Inventory / Store Data
        student_item_ids_subq = select(StudentItem.id).filter_by(class_id=class_id).subquery()
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(select(student_item_ids_subq))
        ).delete(synchronize_session=False)
        StudentItem.query.filter_by(class_id=class_id).delete(synchronize_session=False)

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

        # 7. Post-collapse: Student Erasure and Link Cleanup
        # If a student has zero remaining Seats under this teacher's classes, remove the StudentTeacher link.
        # If they have zero across ALL teachers, fully delete the student record.
        if affected_student_ids:
            for s_id in affected_student_ids:
                # Does student have any remaining seats in this teacher's other classes?
                remaining_with_teacher = (
                    db.session.query(Seat.id)
                    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                    .filter(
                        Seat.student_id == s_id,
                        ClassEconomy.teacher_id == teacher_id,
                    )
                    .count()
                )
                if remaining_with_teacher == 0:
                    StudentTeacher.query.filter_by(student_id=s_id, teacher_id=teacher_id).delete(synchronize_session=False)

                # Full erasure if totally orphaned across all teachers
                remaining_memberships = db.session.query(ClassMembership.id).filter_by(student_id=s_id).count()
                remaining_seats = db.session.query(Seat.id).filter_by(student_id=s_id).count()
                if remaining_memberships == 0 and remaining_seats == 0:
                    logger.info(f"Student Erasure Rule triggered for student_id={s_id}")
                    StudentTeacher.query.filter_by(student_id=s_id).delete(synchronize_session=False)
                    Student.query.filter_by(id=s_id).delete(synchronize_session=False)

        # 8. Post-collapse: Settings Cleanup
        # If no remaining Seat exists for that block name in this teacher's other classes, delete insurance policy blocks.
        if affected_seat_blocks:
            for block_name in affected_seat_blocks:
                remaining = (
                    db.session.query(Seat.id)
                    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                    .filter(
                        Seat.block == block_name,
                        ClassEconomy.teacher_id == teacher_id,
                    )
                    .count()
                )
                if remaining == 0:
                    logger.info(f"Settings Cleanup Rule triggered for block={block_name}, teacher={teacher_id}")
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
