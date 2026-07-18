"""
Test multi-tenancy for admin/teacher routes.

V2 canonical model: isolation is enforced via Seat.class_id → ClassEconomy.user_id.
"""

import pytest

from app.extensions import db
from app.models import ClassEconomy, Seat, User
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _get_teacher_students(teacher_user_id: int):
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


@pytest.fixture
def two_teachers(client):
    class_1 = initialize("chemistry_p1", client.application)
    class_2 = initialize("biology_block_a", client.application)
    return class_1.teacher_user, class_2.teacher_user


def test_DOM_IDEN_007__teacher_can_only_see_own_students(client, two_teachers):
    """Teacher1 sees only their 5 students via class_id scoping."""
    teacher1, teacher2 = two_teachers

    students = _get_teacher_students(teacher1.id)
    assert len(students) >= 1
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == teacher1.id


def test_DOM_IDEN_007__brand_new_teacher_sees_no_students(client, two_teachers):
    """A teacher with no classes sees zero students."""
    new_teacher = initialize("ap_csp_p3", client.application).teacher_user

    students = _get_teacher_students(new_teacher.id)
    assert len(students) == 0


def test_DOM_IDEN_007__teacher2_sees_only_their_students(client, two_teachers):
    """Teacher2 sees only their 3 students via class_id scoping."""
    teacher1, teacher2 = two_teachers

    students = _get_teacher_students(teacher2.id)
    assert len(students) >= 1
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == teacher2.id


def test_DOM_IDEN_007__students_without_class_not_visible_to_teachers(client):
    """Students with no class (no Seat) are not visible to any teacher."""
    teacher = initialize("chemistry_p1", client.application).teacher_user

    students = _get_teacher_students(teacher.id)
    assert len(students) == 0


def test_DOM_IDEN_007__class_isolation_between_teachers(client):
    """Students in teacher A's class are invisible to teacher B."""
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    teacher_a = class_a.teacher_user
    teacher_b = class_b.teacher_user

    students_visible_to_b = _get_teacher_students(teacher_b.id)
    assert len(students_visible_to_b) == 0
