"""Reusable helpers for hard-deleting student records and dependent data."""

import sqlalchemy as sa

from app.extensions import db
from app.models import (
    BalanceCache,
    HallPassLog,
    InsuranceClaim,
    Issue,
    IssueResolutionAction,
    IssueStatusHistory,
    RedemptionAuditLog,
    RentPayment,
    RentWaiver,
    Student,
    StudentBlock,
    StudentInsurance,
    StudentItem,
    ClassEconomy,
    TapEvent,
    Transaction,
    UserReport,
    Seat,
)
from app.services.recovery_bridge_service import delete_recovery_codes_for_student


def _collect_related_ids(student_id):
    """Materialize dependent record IDs once for downstream delete/update queries."""
    from app.models import IdentityProfile

    student_item_ids = [
        row[0]
        for row in db.session.query(StudentItem.id).filter(StudentItem.student_id == student_id).all()
    ]
    issue_ids = [
        row[0]
        for row in db.session.query(Issue.id).filter(Issue.student_id == student_id).all()
    ]
    insurance_ids = [
        row[0]
        for row in db.session.query(StudentInsurance.id).filter(StudentInsurance.student_id == student_id).all()
    ]
    tx_ids = [
        row[0]
        for row in db.session.query(Transaction.id)
        .join(Seat, Transaction.seat_id == Seat.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Student.id == student_id)
        .all()
    ]
    seat_ids = [
        row[0]
        for row in db.session.query(Seat.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Student.id == student_id)
        .all()
    ]
    return student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids


def _unclaim_all_seats_for_student(student_id):
    """Detach all canonical seats for this student, resetting them to unclaimed."""
    from app.models import IdentityProfile

    Seat.query.filter(
        Seat.id.in_(
            sa.select(
                db.session.query(Seat.id)
                .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
                .join(Student, Student.identity_id == IdentityProfile.id)
                .filter(Student.id == student_id)
                .subquery()
            )
        )
    ).update(
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


def _delete_student_scoped_rows(student_id, student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids):
    """Delete records that are scoped directly to the student being removed."""
    if student_item_ids:
        RedemptionAuditLog.query.filter(
            RedemptionAuditLog.student_item_id.in_(student_item_ids)
        ).delete(synchronize_session=False)
    if issue_ids:
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)
        IssueStatusHistory.query.filter(
            IssueStatusHistory.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)

    insurance_claim_filters = [InsuranceClaim.seat_id.in_(seat_ids)] if seat_ids else []
    if insurance_ids:
        insurance_claim_filters.append(InsuranceClaim.enrollment_id.in_(insurance_ids))
    if tx_ids:
        insurance_claim_filters.append(InsuranceClaim.transaction_id.in_(tx_ids))
    InsuranceClaim.query.filter(sa.or_(*insurance_claim_filters)).delete(synchronize_session=False)

    Issue.query.filter(Issue.student_id == student_id).delete(synchronize_session=False)
    StudentInsurance.query.filter(StudentInsurance.student_id == student_id).delete(synchronize_session=False)
    UserReport.query.filter(UserReport._student_id == student_id).delete(synchronize_session=False)
    delete_recovery_codes_for_student(student_id)
    if tx_ids:
        Transaction.query.filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
    TapEvent.query.filter(TapEvent.student_id == student_id).delete(synchronize_session=False)
    HallPassLog.query.filter(HallPassLog.student_id == student_id).delete(synchronize_session=False)
    StudentItem.query.filter(StudentItem.student_id == student_id).delete(synchronize_session=False)
    RentPayment.query.filter(RentPayment.student_id == student_id).delete(synchronize_session=False)
    RentWaiver.query.filter(RentWaiver.student_id == student_id).delete(synchronize_session=False)
    StudentBlock.query.filter(StudentBlock.student_id == student_id).delete(synchronize_session=False)
    if seat_ids:
        BalanceCache.query.filter(BalanceCache.seat_id.in_(seat_ids)).delete(synchronize_session=False)


def hard_delete_student_if_orphaned(student_id):
    """Hard-delete a student and dependent rows only when no class seats remain."""
    from app.models import IdentityProfile
    has_seats = (
        db.session.query(Seat.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Student.id == student_id)
        .all()
    )
    print(f"DEBUG: hard_delete_student_if_orphaned for student_id={student_id}. has_seats={has_seats}")
    if has_seats:
        return False

    student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids = _collect_related_ids(student_id)
    _unclaim_all_seats_for_student(student_id)
    _clear_cross_transaction_refs(tx_ids)
    _delete_student_scoped_rows(student_id, student_item_ids, issue_ids, insurance_ids, tx_ids, seat_ids)
    Student.query.filter(Student.id == student_id).delete(synchronize_session=False)
    return True


def remove_student_from_teacher_scope(student_id, teacher_id):
    """
    Remove a student from a specific teacher's roster and hard-delete if orphaned.

    Detaches seats belonging to this teacher's classes by clearing user_id and
    claimed_at.  Seats belonging to other teachers' classes are left intact.
    """
    from app.models import IdentityProfile

    teacher_class_ids = db.session.query(ClassEconomy.class_id).filter_by(teacher_id=teacher_id).subquery()

    # Find seat IDs linked to this student via IdentityProfile in this teacher's classes
    student_seat_ids = (
        db.session.query(Seat.id)
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(
            Student.id == student_id,
            Seat.class_id.in_(sa.select(teacher_class_ids)),
        )
        .subquery()
    )

    Seat.query.filter(
        Seat.id.in_(sa.select(student_seat_ids)),
    ).update(
        {
            Seat.claimed_at: None,
            Seat.user_id: None,
        },
        synchronize_session=False,
    )
    return hard_delete_student_if_orphaned(student_id)
