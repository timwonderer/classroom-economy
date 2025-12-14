"""Utility helpers for demo student session lifecycle management."""

from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    DemoStudent,
    HallPassLog,
    InsuranceClaim,
    RentPayment,
    RentWaiver,
    Student,
    StudentBlock,
    StudentInsurance,
    StudentItem,
    StudentTeacher,
    TapEvent,
    Transaction,
    TeacherBlock,
)


def cleanup_demo_student_data(demo_session: DemoStudent, delete_session_record: bool = True) -> None:
    """Remove all data associated with a demo student before deleting the student.

    The cleanup order is important to avoid foreign key violations. Claims are
    removed before insurance policies, which are removed before rent, hall pass,
    and commerce artifacts, followed by the demo session record and the student
    itself.

    Args:
        demo_session: The demo session record to clean up.
        delete_session_record: Whether to delete the DemoStudent row after
            cleaning related data. Defaults to True.
    """

    student_id = demo_session.student_id

    # Mark the session inactive before deleting dependents (FK-safe order below)
    demo_session.is_active = False
    demo_session.ended_at = demo_session.ended_at or datetime.now(timezone.utc)

    # Insurance-related artifacts
    InsuranceClaim.query.filter_by(student_id=student_id).delete()
    StudentInsurance.query.filter_by(student_id=student_id).delete()

    # Rent artifacts
    RentPayment.query.filter_by(student_id=student_id).delete()
    RentWaiver.query.filter_by(student_id=student_id).delete()

    # Hall pass requests
    HallPassLog.query.filter_by(student_id=student_id).delete()

    # Commerce/engagement artifacts
    StudentItem.query.filter_by(student_id=student_id).delete()
    TapEvent.query.filter_by(student_id=student_id).delete()
    Transaction.query.filter_by(student_id=student_id).delete()

    # Remove student associations
    StudentTeacher.query.filter_by(student_id=student_id).delete()
    StudentBlock.query.filter_by(student_id=student_id).delete()
    TeacherBlock.query.filter_by(student_id=student_id).delete()

    if delete_session_record:
        db.session.delete(demo_session)

    Student.query.filter_by(id=student_id).delete()
