"""Reusable helpers for hard-deleting student records and dependent data."""

import sqlalchemy as sa

from app.extensions import db
from app.models import (
    LedgerBalanceSnapshot,
    HallPassLog,
    Issue,
    IssueResolutionAction,
    IssueStatusHistory,
    ClassEconomy,
    EntitlementEvent,
    PendingAction,
    AttendanceSession,
    PayrollEvent,
    PolicyTransition,
    RecoveryRequest,
    Transaction,
    Seat,
    User,
    IdentityProfile,
)
from app.services.recovery_service import delete_recovery_codes_for_seat


def _collect_related_ids_for_seats(seat_ids_for_student):
    """Materialize dependent record IDs once for downstream delete/update queries."""
    seat_ids_for_student = list(seat_ids_for_student or [])
    if not seat_ids_for_student:
        return [], [], [], []

    entitlement_ids = [
        row[0]
        for row in (
            db.session.query(EntitlementEvent.entitlement_id)
            .filter(
                EntitlementEvent.target_seat_id.in_(seat_ids_for_student),
                EntitlementEvent.event_type == "GRANTED",
            )
            .all()
        )
    ]
    issue_ids = [
        row[0]
        for row in db.session.query(Issue.id).filter(
            Issue.actor_public_id.in_(
                db.session.query(Seat.public_id).filter(Seat.id.in_(seat_ids_for_student))
            )
        ).all()
    ]
    tx_ids = [
        row[0]
        for row in db.session.query(Transaction.id)
        .filter(Transaction.seat_id.in_(seat_ids_for_student))
        .all()
    ]
    return entitlement_ids, issue_ids, tx_ids, seat_ids_for_student


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
    return _collect_related_ids_for_seats(seat_ids_for_student)


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


def _delete_student_scoped_rows(
    student_id,
    entitlement_ids,
    issue_ids,
    tx_ids,
    seat_ids,
    seat_ids_for_student=None,
    scoped_class_id=None,
):
    """Delete records that are scoped directly to the student being removed."""
    if entitlement_ids:
        PendingAction.query.filter(
            PendingAction.entitlement_id.in_(entitlement_ids)
        ).delete(synchronize_session=False)
        EntitlementEvent.query.filter(
            EntitlementEvent.entitlement_id.in_(entitlement_ids)
        ).delete(synchronize_session=False)
    if scoped_class_id:
        PendingAction.query.filter(
            PendingAction.class_id == scoped_class_id
        ).delete(synchronize_session=False)
    if issue_ids:
        IssueResolutionAction.query.filter(
            IssueResolutionAction.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)
        IssueStatusHistory.query.filter(
            IssueStatusHistory.issue_id.in_(issue_ids)
        ).delete(synchronize_session=False)

    if seat_ids_for_student is None:
        seat_ids_for_student = [
            row[0]
            for row in (
                db.session.query(Seat.id)
                .filter(Seat.user_id == student_id)
                .all()
            )
        ]
    if seat_ids_for_student:
        seat_pub_ids = [
            pub_id for (pub_id,) in
            db.session.query(Seat.public_id).filter(Seat.id.in_(seat_ids_for_student)).all()
        ]
        if seat_pub_ids:
            Issue.query.filter(Issue.actor_public_id.in_(seat_pub_ids)).delete(synchronize_session=False)
    for sid in (seat_ids_for_student or []):
        delete_recovery_codes_for_seat(sid)
    if tx_ids:
        Transaction.query.filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
    if seat_ids_for_student:
        attendance_query = AttendanceSession.query.filter(
            AttendanceSession.target_seat_id.in_(seat_ids_for_student)
        )
        hall_pass_query = HallPassLog.query.filter(
            HallPassLog.requested_by_seat_id.in_(seat_ids_for_student)
        )
        payroll_query = PayrollEvent.query.filter(
            PayrollEvent.target_seat_id.in_(seat_ids_for_student)
        )
        if scoped_class_id:
            attendance_query = attendance_query.filter(AttendanceSession.class_id == scoped_class_id)
            hall_pass_query = hall_pass_query.filter(HallPassLog.class_id == scoped_class_id)
            payroll_query = payroll_query.filter(PayrollEvent.class_id == scoped_class_id)
        attendance_query.delete(synchronize_session=False)
        hall_pass_query.delete(synchronize_session=False)
        payroll_query.delete(synchronize_session=False)
    if seat_ids:
        LedgerBalanceSnapshot.query.filter(LedgerBalanceSnapshot.seat_id.in_(seat_ids)).delete(synchronize_session=False)


def delete_orphaned_users(user_ids):
    """Delete every ``users`` row in ``user_ids`` that retains no seat anywhere.

    A ``User`` is the auth principal *behind* a seat; it has no standalone
    existence. Once the last seat referencing it is gone the principal must not
    survive (INV-CORE-000 §III.5, DOM-IDEN-001 §VI). Because ``users`` carries
    credential and recovery material, leaving the row behind is also a
    PII-retention violation.

    Teacher principals are exempt here: they own ``ClassEconomy`` rows and are
    destroyed only through the terminal FEAT-IDEN-007 command, which tears the
    owned classes down first.

    Returns the list of user ids actually deleted.
    """
    candidate_ids = {uid for uid in (user_ids or []) if uid}
    if not candidate_ids:
        return []

    still_seated = {
        row[0]
        for row in db.session.query(Seat.user_id)
        .filter(Seat.user_id.in_(candidate_ids))
        .distinct()
        .all()
    }
    owns_classes = {
        row[0]
        for row in db.session.query(ClassEconomy.teacher_user_id)
        .filter(ClassEconomy.teacher_user_id.in_(candidate_ids))
        .distinct()
        .all()
    }
    orphan_ids = sorted(candidate_ids - still_seated - owns_classes)
    if not orphan_ids:
        return []

    # Clear or remove the references that would otherwise block the delete.
    # `attendance_sessions.target_user_id` is ON DELETE SET NULL against a
    # NOT NULL column, so surviving rows must go rather than be nulled.
    AttendanceSession.query.filter(
        AttendanceSession.target_user_id.in_(orphan_ids)
    ).delete(synchronize_session=False)
    RecoveryRequest.query.filter(
        RecoveryRequest.user_id.in_(orphan_ids)
    ).delete(synchronize_session=False)
    Transaction.query.filter(Transaction.user_id.in_(orphan_ids)).update(
        {Transaction.user_id: None}, synchronize_session=False
    )
    Issue.query.filter(Issue.sysadmin_id.in_(orphan_ids)).update(
        {Issue.sysadmin_id: None}, synchronize_session=False
    )
    PolicyTransition.query.filter(PolicyTransition.created_by.in_(orphan_ids)).update(
        {PolicyTransition.created_by: None}, synchronize_session=False
    )

    User.query.filter(User.id.in_(orphan_ids)).delete(synchronize_session=False)
    return orphan_ids


def delete_user_if_orphaned(user_id):
    """Single-principal form of :func:`delete_orphaned_users`."""
    return bool(delete_orphaned_users([user_id]))


def hard_delete_student_if_orphaned(student_id):
    """Hard-delete a student and dependent rows only when no teacher links remain."""
    has_links = (
        db.session.query(Seat.id)
        .filter(Seat.user_id == student_id)
        .all()
    )
    if has_links:
        return False

    entitlement_ids, issue_ids, tx_ids, seat_ids = _collect_related_ids(student_id)
    _unclaim_all_seats_for_student(student_id)
    _clear_cross_transaction_refs(tx_ids)
    _delete_student_scoped_rows(student_id, entitlement_ids, issue_ids, tx_ids, seat_ids)
    Seat.query.filter(Seat.user_id == student_id).delete(synchronize_session=False)
    # The principal does not outlive its last seat.
    delete_user_if_orphaned(student_id)
    return True


def remove_student_from_teacher_scope(seat_id, user_id):
    """
    Remove a student's seat from a specific teacher's roster and hard-delete if orphaned.
    """
    # Detach the seat that belongs to this teacher's classes.
    from app.models import ClassEconomy
    seat = db.session.get(Seat, seat_id)
    if not seat:
        return False

    student_user_id = seat.user_id
    scoped_entitlement_ids, scoped_issue_ids, scoped_tx_ids, scoped_seat_ids = (
        _collect_related_ids_for_seats([seat_id])
    )
    teacher_class_ids = sa.select(ClassEconomy.class_id).where(ClassEconomy.teacher_user_id == user_id)
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
    remaining_links = db.session.query(Seat.id).filter(Seat.user_id == student_user_id).all()
    if remaining_links:
        _clear_cross_transaction_refs(scoped_tx_ids)
        _delete_student_scoped_rows(
            student_user_id,
            scoped_entitlement_ids,
            scoped_issue_ids,
            scoped_tx_ids,
            scoped_seat_ids,
            scoped_class_id=seat.class_id,
        )
        return False

    entitlement_ids, issue_ids, tx_ids, seat_ids = _collect_related_ids_for_seats(scoped_seat_ids)
    _clear_cross_transaction_refs(tx_ids)
    _delete_student_scoped_rows(
        student_user_id,
        entitlement_ids,
        issue_ids,
        tx_ids,
        seat_ids,
    )
    Seat.query.filter(Seat.user_id == student_user_id).delete(synchronize_session=False)
    # The detached seat was the student's last one anywhere; the principal goes
    # with it. The seat row itself survives as an unclaimed roster slot owned by
    # the class, which is why the delete above is a no-op on the unclaimed seat.
    delete_user_if_orphaned(student_user_id)
    return True
