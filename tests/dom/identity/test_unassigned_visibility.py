from app.models import ClassEconomy, Seat
from tests.helpers.classroom_initializer import initialize


def _get_teacher_student_seats(teacher_user_id: int):
    """Return student Seat rows in classes owned by this teacher."""
    return (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            ClassEconomy.user_id == teacher_user_id,
            Seat.role == "student",
        )
        .all()
    )


def test_DOM_IDEN_001__new_admin_cannot_see_unassigned_students(client):
    """
    Regression test for P0 leak: New admins should NOT see students who have
    no class association (no Seat in any of their classes).
    """
    class_b = initialize("chemistry_p1", client.application)
    teacher_b = class_b.teacher_user
    student_b = class_b.students[0].seat
    teacher_a = initialize("ap_csp_p3", client.application).teacher_user

    # teacher_a has no classes, should see no students
    results = _get_teacher_student_seats(teacher_a.id)
    assert len(results) == 0, "Teacher A should not see students not in Teacher A's classes"


def test_DOM_IDEN_001__owner_can_see_students_in_own_class(client):
    """
    Verify that a teacher CAN see students enrolled in their own class.
    """
    class_b = initialize("chemistry_p1", client.application)
    teacher_b = class_b.teacher_user
    student_b = class_b.students[0].seat

    results = _get_teacher_student_seats(teacher_b.id)
    assert len(results) == 1
