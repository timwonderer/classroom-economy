"""
Test multi-tenancy for admin/teacher routes.

V2 canonical model: isolation is enforced via Seat.class_id → ClassEconomy.user_id.
"""

import pytest

from app.extensions import db
from app.models import ClassEconomy, Seat, User
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _get_teacher_students(teacher_user_id: int):
    # This is a legacy helper replaced by route testing.
    pass


def test_DOM_IDEN_007__teacher_can_only_see_own_students(client):
    """Teacher1 sees only their students via class_id scoping."""
    from tests.dom.identity.helpers import admin_get_students
    from tests.helpers.classroom_initializer import initialize_as_teacher
    
    class_1 = initialize_as_teacher("chemistry_p1", client, client.application)
    
    resp = admin_get_students(client)
    html = resp.data.decode('utf-8')
    
    class_1_seats = class_1.students
    assert len(class_1_seats) >= 1
    for student in class_1_seats:
        assert f'data-seat-id="{student.seat.id}"' in html
def test_DOM_IDEN_007__teacher2_sees_only_their_students(client):
    """Teacher2 sees only their students via class_id scoping."""
    from tests.dom.identity.helpers import admin_get_students
    from tests.helpers.classroom_initializer import initialize_as_teacher
    
    class_2 = initialize_as_teacher("biology_block_a", client, client.application)
    
    resp = admin_get_students(client)
    html = resp.data.decode('utf-8')
    
    class_2_seats = class_2.students
    assert len(class_2_seats) >= 1
    for student in class_2_seats:
        assert f'data-seat-id="{student.seat.id}"' in html


def test_DOM_IDEN_007__class_isolation_between_teachers(client):
    """Students in teacher A's class are invisible to teacher B."""
    from tests.dom.identity.helpers import admin_get_students
    
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize_as_teacher("biology_block_a", client, client.application)

    resp_b = admin_get_students(client)
    html_b = resp_b.data.decode('utf-8')
    
    for student in class_a.students:
        assert f'data-seat-id="{student.seat.id}"' not in html_b, "Teacher B should not see teacher A's students"
