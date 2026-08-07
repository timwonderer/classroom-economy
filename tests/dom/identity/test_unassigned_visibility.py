from app.models import ClassEconomy, Seat
from tests.helpers.classroom_initializer import initialize


def _get_teacher_student_seats(teacher_user_id: int):
    # This is a legacy helper replaced by route testing.
    pass


def test_DOM_IDEN_001__cross_teacher_isolation(client):
    """
    Regression test for P0 leak: Teacher B should NOT see students in Teacher A's classes.
    """
    from tests.dom.identity.helpers import admin_get_students
    from tests.helpers.classroom_initializer import initialize_as_teacher
    
    class_a = initialize_as_teacher("chemistry_p1", client, client.application)
    class_b = initialize("biology_block_a", client.application)
    
    resp_a = admin_get_students(client)
    assert resp_a.status_code == 200, "Teacher A should successfully access student list"
    html_a = resp_a.data.decode('utf-8')

    for seat in class_b.students:
        assert f'data-seat-id="{seat.seat.id}"' not in html_a, "Teacher A should not see Teacher B's students"

    # Switch to Teacher B and verify
    client.get('/admin/logout')
    initialize_as_teacher("biology_block_a", client, client.application)
    resp_b = admin_get_students(client)
    assert resp_b.status_code == 200, "Teacher B should successfully access student list"
    html_b = resp_b.data.decode('utf-8')

    for seat in class_a.students:
        assert f'data-seat-id="{seat.seat.id}"' not in html_b, "Teacher B should not see Teacher A's students"


def test_DOM_IDEN_001__owner_can_see_students_in_own_class(client):
    """
    Verify that a teacher CAN see students enrolled in their own class.
    """
    from tests.dom.identity.helpers import admin_get_students
    from tests.helpers.classroom_initializer import initialize_as_teacher
    
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)

    resp = admin_get_students(client)
    html = resp.data.decode('utf-8')
    
    seat_ids = [s.seat.id for s in classroom.students]
    assert len(seat_ids) >= 1
    for seat_id in seat_ids:
        assert f'data-seat-id="{seat_id}"' in html, "Owner should see their own students in the route response"
