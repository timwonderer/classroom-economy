"""
Attendance Helper Utilities

Shared utilities for attendance and payroll calculations.
Created to break circular dependency between attendance.py and payroll.py.
"""

from sqlalchemy import func


def get_join_code_for_student_period(student_id, period, user_id=None):
    """
    Resolve the join_code for a student's specific period.

    Args:
        student_id (int): ID of the student.
        period (str): Period/block identifier (case-insensitive).
        user_id (int, optional): Restrict lookup to a specific user.

    Returns:
        str | None: join_code matching the student's seat for the requested period.
    """
    from app.models import ClassEconomy, Seat

    query = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.user_id == student_id,
            func.upper(ClassEconomy.section) == func.upper(period),
            Seat.claimed_at.isnot(None),
        )
    )

    if user_id:
        teacher_class_ids = (
            ClassEconomy.query
            .with_entities(ClassEconomy.class_id)
            .filter(ClassEconomy.user_id == user_id)
            .subquery()
        )
        query = query.filter(Seat.class_id.in_(teacher_class_ids))

    seat = query.order_by(Seat.id.desc()).first()
    if not seat:
        return None
    class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
    return class_row.join_code if class_row else None
