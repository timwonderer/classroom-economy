"""Reusable helpers for hard-deleting student records and dependent data."""

import sqlalchemy as sa

from app.extensions import db
from app.models import (
    BalanceCache,
    HallPassLog,
    InsuranceClaim,
    InsuranceEnrollment,
    Issue,
    IssueResolutionAction,
    IssueStatusHistory,
    RedemptionAuditLog,
    RedemptionEvent,
    RentPayment,
    RentWaiver,
    StorePurchase,
    AttendanceSession,
    SeatAttendanceState,
    Transaction,
    UserReport,
    Seat,
    IdentityProfile,
)
from app.services.recovery_bridge_service import delete_recovery_codes_for_student


def _collect_related_ids(student_id):
    """Materialize dependent record IDs once for downstream delete/update queries."""
    seat_ids_for_student = [
        row[0]
        for row in (
            db.session.query(Seat.id)
            .filter(Seat.user_id == student_id)
            .all()
        )
    ]
    store_purchase_ids = [
        row[0]
        for row in (
            db.session.query(StorePurchase.id)
            .filter(StorePurchase.seat_id.in_(seat_ids_for_student))
            .all()
        )
    ]
    issue_ids = [
        row[0]
        for row in db.session.query(Issue.id).filter(Issue.student_id == student_id).all()
    ]
    insurance_ids = [
        row[0]
        for row in db.session.query(InsuranceEnrollment.id)
        .filter(InsuranceEnrollment.seat_id.in_(seat_ids_for_student))
        .all()
    ]
    tx_ids = [
        row[0]
        for row in db.session.query(Transaction.id)
        .filter(Transaction.seat_id.in_(seat_ids_for_student))
        .all()
    ]
    return store_purchase_ids, issue_ids, insurance_ids, tx_ids, seat_ids_for_student


def _unclaim_all_seats_for_student(student_id):
    """Detach all canonical seats for this student, resetting them to unclaimed."""
    Seat.query.filter(Seat.user_id == student_id).update(
        {
            Seat.claimed_at: None,
            Seat.user_id: None,
        },
        synchronize_session=False,
    )


def _clear_cross_transaction_refs(tx_ids):
    """Clear references to transactions that are about to be deleted."""
    if not tx_ids:
        return

    Issue.query.filter(
        Issue.related_transaction_id.in_(tx_ids)
    ).update(
        {Issue.related_transaction_id: None},
        synchronize_session=False,
    )
    IssueResolutionAction.query.filter(
        IssueResolutionAction.related_transaction_id.in_(tx_ids)
    ).update(
        {IssueResolutionAction.related_transaction_id: None},
        synchronize_session=False,
    )
    Transaction.query.filter(
        Transaction.original_transaction_id.in_(tx_ids)
    ).update(
        {Transaction.original_transaction_id: None},
        synchronize_session=False,
    )
    Transaction.query.filter(
        Transaction.reversal_transaction_id.in_(tx_ids)
    ).update(
        {Transaction.reversal_transaction_id: None},
        synchronize_session=False,
    )


def _delete_student_scoped_rows(student_id, store_purchase_ids, issue_ids, insurance_ids, tx_ids, seat_ids):
    """Delete records that are scoped directly to the student being removed."""
    if store_purchase_ids:
        RedemptionEvent.query.filter(
            RedemptionEvent.purchase_id.in_(store_purchase_ids)
        ).delete(synchronize_session=False)
    if issue_ids:
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)
        IssueStatusHistory.query.filter(
            IssueStatusHistory.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)

    seat_ids_for_student = [
        row[0]
        for row in (
            db.session.query(Seat.id)
            .filter(Seat.user_id == student_id)
            .all()
        )
    ]
    insurance_claim_filters = [InsuranceClaim.seat_id.in_(seat_ids_for_student)] if seat_ids_for_student else []
    if insurance_ids:
        insurance_claim_filters.append(InsuranceClaim.enrollment_id.in_(insurance_ids))
    if tx_ids:
        insurance_claim_filters.append(InsuranceClaim.transaction_id.in_(tx_ids))
    InsuranceClaim.query.filter(sa.or_(*insurance_claim_filters)).delete(synchronize_session=False)

    Issue.query.filter(Issue.student_id == student_id).delete(synchronize_session=False)
    InsuranceEnrollment.query.filter(
        InsuranceEnrollment.seat_id.in_(seat_ids_for_student)
    ).delete(synchronize_session=False)
    UserReport.query.filter(UserReport._student_id == student_id).delete(synchronize_session=False)
    delete_recovery_codes_for_student(student_id)
    if tx_ids:
        Transaction.query.filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
    if seat_ids_for_student:
        SeatAttendanceState.query.filter(SeatAttendanceState.seat_id.in_(seat_ids_for_student)).delete(synchronize_session=False)
        AttendanceSession.query.filter(AttendanceSession.seat_id.in_(seat_ids_for_student)).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.student_id == student_id).delete(synchronize_session=False)
    RentPayment.query.filter(RentPayment.student_id == student_id).delete(synchronize_session=False)
    RentWaiver.query.filter(RentWaiver.student_id == student_id).delete(synchronize_session=False)
    if seat_ids:
        BalanceCache.query.filter(BalanceCache.seat_id.in_(seat_ids)).delete(synchronize_session=False)


def hard_delete_student_if_orphaned(student_id):
    """Hard-delete a student and dependent rows only when no teacher links remain."""
    has_links = (
        db.session.query(Seat.id)
        .filter(Seat.user_id == student_id)
        .all()
    )
    if has_links:
        return False

    store_purchase_ids, issue_ids, insurance_ids, tx_ids, seat_ids = _collect_related_ids(student_id)
    _unclaim_all_seats_for_student(student_id)
    _clear_cross_transaction_refs(tx_ids)
    _delete_student_scoped_rows(student_id, store_purchase_ids, issue_ids, insurance_ids, tx_ids, seat_ids)
    Seat.query.filter(Seat.user_id == student_id).delete(synchronize_session=False)
    return True


def remove_student_from_teacher_scope(seat_id, teacher_id):
    """
    Remove a student's seat from a specific teacher's roster and hard-delete if orphaned.
    """
    # Detach the seat that belongs to this teacher's classes.
    from app.models import ClassEconomy
    seat = db.session.get(Seat, seat_id)
    if not seat:
        return False

    student_user_id = seat.user_id
    teacher_class_ids = db.session.query(ClassEconomy.class_id).filter_by(user_id=teacher_id).subquery()
    Seat.query.filter(
        Seat.id == seat_id,
        Seat.class_id.in_(teacher_class_ids),
    ).update(
        {
            Seat.claimed_at: None,
            Seat.user_id: None,
        },
        synchronize_session=False,
    )
    return hard_delete_student_if_orphaned(student_user_id)
