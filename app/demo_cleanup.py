"""Utilities for cleaning up demo student sessions."""

from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    DemoStudent,
    HallPassLog,
    InsuranceClaim,
    RentPayment,
    RentWaiver,
    Student,
    StudentInsurance,
    StudentItem,
    TapEvent,
    Transaction,
)


def cleanup_demo_student_records(demo_session: DemoStudent) -> None:
    """
    Remove all data created by a demo student in FK-safe order.

    Args:
        demo_session: DemoStudent instance to clean up. Must be attached to the current session.
    """

    student_id = demo_session.student_id

    # Ensure the session is marked inactive before deleting child rows
    demo_session.is_active = False
    demo_session.ended_at = demo_session.ended_at or datetime.now(timezone.utc)

    # Delete dependent rows in reverse dependency order to avoid FK violations
    InsuranceClaim.query.filter_by(student_id=student_id).delete()
    StudentInsurance.query.filter_by(student_id=student_id).delete()
    RentWaiver.query.filter_by(student_id=student_id).delete()
    RentPayment.query.filter_by(student_id=student_id).delete()
    HallPassLog.query.filter_by(student_id=student_id).delete()
    StudentItem.query.filter_by(student_id=student_id).delete()
    TapEvent.query.filter_by(student_id=student_id).delete()
    Transaction.query.filter_by(student_id=student_id).delete()

    # Drop the demo session row before removing the student record (FK to student_id)
    db.session.delete(demo_session)
    Student.query.filter_by(id=student_id).delete()
