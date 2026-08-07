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


def test_DOM_IDEN_001__cross_teacher_isolation(client):
    """
    Regression test for P0 leak: Teacher B should NOT see students in Teacher A's classes.
    """
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    teacher_a = class_a.teacher_user
    teacher_b = class_b.teacher_user

    results_a = _get_teacher_student_seats(teacher_a.id)
    results_b = _get_teacher_student_seats(teacher_b.id)

    class_a_seat_ids = {s.seat.id for s in class_a.students}
    class_b_seat_ids = {s.seat.id for s in class_b.students}

    for seat in results_a:
        assert seat.id not in class_b_seat_ids, "Teacher A should not see Teacher B's students"
    for seat in results_b:
        assert seat.id not in class_a_seat_ids, "Teacher B should not see Teacher A's students"


def test_DOM_IDEN_001__owner_can_see_students_in_own_class(client):
    """
    Verify that a teacher CAN see students enrolled in their own class.
    """
    classroom = initialize("chemistry_p1", client.application)
    teacher = classroom.teacher_user

    results = _get_teacher_student_seats(teacher.id)
    assert len(results) >= 1
    for seat in results:
        assert seat.class_id == classroom.class_id
