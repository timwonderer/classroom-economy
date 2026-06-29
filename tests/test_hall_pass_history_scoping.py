"""
Tests for hall pass history API endpoint scoping.

Ensures that the /api/hall-pass/history endpoint properly scopes
hall pass data by teacher to prevent cross-teacher data leakage.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope, make_student_with_seat
import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    Student, Admin, HallPassLog, StudentTeacher, IdentityProfile,
    Seat,
)
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


def _make_student(first_name, last_initial, block, username_suffix, class_id, join_code):
    """Create a canonical student + seat pair for hall pass fixtures."""
    student, seat = make_student_with_seat(
        class_id=class_id,
        join_code=join_code,
        block=block,
        first_name=first_name,
        last_name=last_initial,
        claimed=True,
    )
    salt = get_random_salt()
    student.salt = salt
    student.username_hash = hash_username(username_suffix, salt)
    db.session.flush()
    return student, seat


def _login_admin_to_class(client, admin_id, class_row, seat):
    login_admin(
        client,
        admin_id,
        class_row.join_code,
        user_id=class_row.user_id,
        class_id=class_row.class_id,
        seat_id=seat.id,
    )


@pytest.fixture
def setup_multi_teacher_hall_pass_history(client):
    """Create two teachers with students and hall pass history for testing scoping."""
    # Create two teachers
    teacher1 = make_admin("teacher1", "secret1")
    teacher2 = make_admin("teacher2", "secret2")
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.commit()

    # Create Class Contexts using v2 canonical helper
    class1 = create_class_scope(teacher=teacher1, join_code="CLASS-A", block="A")
    class2 = create_class_scope(teacher=teacher1, join_code="CLASS-B", block="B")
    class3 = create_class_scope(teacher=teacher2, join_code="CLASS-C", block="C")
    class4 = create_class_scope(teacher=teacher2, join_code="CLASS-D", block="D")

    # Create students inside their canonical classes.
    student1, seat1 = _make_student("Alice", "A", "A", "alice_a", class1.class_id, "CLASS-A")
    student2, seat2 = _make_student("Bob", "B", "B", "bob_b", class2.class_id, "CLASS-B")
    student3, seat3 = _make_student("Charlie", "C", "C", "charlie_c", class3.class_id, "CLASS-C")
    student4, seat4 = _make_student("Diana", "D", "D", "diana_d", class4.class_id, "CLASS-D")
    db.session.flush()

    # Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(student_id=student1.id, teacher_id=teacher1.id))
    db.session.add(StudentTeacher(student_id=student2.id, teacher_id=teacher1.id))
    db.session.add(StudentTeacher(student_id=student3.id, teacher_id=teacher2.id))
    db.session.add(StudentTeacher(student_id=student4.id, teacher_id=teacher2.id))
    db.session.commit()

    # Create hall pass history
    now = datetime.now(timezone.utc)

    pass1 = HallPassLog(
        student_id=student1.id,
        reason="Restroom",
        status="returned",
        join_code="CLASS-A",
        class_id=class1.class_id,
        seat_id=seat1.id,
        period="A",
        request_time=now - timedelta(hours=2),
        decision_time=now - timedelta(hours=2) + timedelta(minutes=5),
        left_time=now - timedelta(hours=2) + timedelta(minutes=10),
        return_time=now - timedelta(hours=2) + timedelta(minutes=15)
    )

    pass2 = HallPassLog(
        student_id=student2.id,
        reason="Office",
        status="returned",
        join_code="CLASS-B",
        class_id=class2.class_id,
        seat_id=seat2.id,
        period="B",
        request_time=now - timedelta(hours=1),
        decision_time=now - timedelta(hours=1) + timedelta(minutes=5),
        left_time=now - timedelta(hours=1) + timedelta(minutes=10),
        return_time=now - timedelta(hours=1) + timedelta(minutes=15)
    )

    pass3 = HallPassLog(
        student_id=student3.id,
        reason="Nurse",
        status="returned",
        join_code="CLASS-C",
        class_id=class3.class_id,
        seat_id=seat3.id,
        period="C",
        request_time=now - timedelta(hours=3),
        decision_time=now - timedelta(hours=3) + timedelta(minutes=5),
        left_time=now - timedelta(hours=3) + timedelta(minutes=10),
        return_time=now - timedelta(hours=3) + timedelta(minutes=15)
    )

    pass4 = HallPassLog(
        student_id=student4.id,
        reason="Locker",
        status="returned",
        join_code="CLASS-D",
        class_id=class4.class_id,
        seat_id=seat4.id,
        period="D",
        request_time=now - timedelta(minutes=30),
        decision_time=now - timedelta(minutes=25),
        left_time=now - timedelta(minutes=20),
        return_time=now - timedelta(minutes=10)
    )

    db.session.add_all([pass1, pass2, pass3, pass4])
    db.session.commit()

    teacher1_seat = Seat.query.filter_by(class_id=class1.class_id, role="teacher").first()
    teacher2_seat = Seat.query.filter_by(class_id=class3.class_id, role="teacher").first()

    return {
        'teacher1': teacher1,
        'teacher2': teacher2,
        'class1': class1,
        'class2': class2,
        'class3': class3,
        'class4': class4,
        'teacher1_seat': teacher1_seat,
        'teacher2_seat': teacher2_seat,
        'student1': student1,
        'student2': student2,
        'student3': student3,
        'student4': student4,
        'pass1': pass1,
        'pass2': pass2,
        'pass3': pass3,
        'pass4': pass4
    }


def test_hall_pass_history_requires_admin_login(client):
    """Test that the history endpoint requires admin authentication."""
    response = client.get('/api/hall-pass/history')
    # Should redirect to login or return 401/403
    assert response.status_code in [302, 401, 403]


def test_hall_pass_history_scopes_to_teacher1(client, setup_multi_teacher_hall_pass_history):
    """Test that teacher1 only sees hall pass history for the active class."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id

    _login_admin_to_class(client, teacher1_id, data["class1"], data["teacher1_seat"])

    response = client.get('/api/hall-pass/history')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data['status'] == 'success'

    # The endpoint is class-scoped, so teacher1 sees only class1 history.
    assert json_data['total'] == 1
    assert len(json_data['records']) == 1

    # Verify records belong to teacher1's students
    student_names = [record['student_name'] for record in json_data['records']]
    assert 'Alice A.' in student_names
    assert 'Bob B.' not in student_names
    assert 'Charlie C.' not in student_names
    assert 'Diana D.' not in student_names


def test_hall_pass_history_scopes_to_teacher2(client, setup_multi_teacher_hall_pass_history):
    """Test that teacher2 only sees hall pass history for the active class."""
    data = setup_multi_teacher_hall_pass_history
    teacher2_id = data['teacher2'].id

    _login_admin_to_class(client, teacher2_id, data["class3"], data["teacher2_seat"])

    response = client.get('/api/hall-pass/history')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data['status'] == 'success'

    # The endpoint is class-scoped, so teacher2 sees only class3 history.
    assert json_data['total'] == 1
    assert len(json_data['records']) == 1

    # Verify records belong to teacher2's students
    student_names = [record['student_name'] for record in json_data['records']]
    assert 'Charlie C.' in student_names
    assert 'Diana D.' not in student_names
    assert 'Alice A.' not in student_names
    assert 'Bob B.' not in student_names


def test_hall_pass_history_with_shared_student(client, setup_multi_teacher_hall_pass_history):
    """Test that class scope still dominates even when a student is shared."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id
    teacher2_id = data['teacher2'].id
    student1_id = data['student1'].id

    # Share student1 (originally teacher1's) with teacher2
    shared_link = StudentTeacher(
        student_id=student1_id,
        teacher_id=teacher2_id
    )
    db.session.add(shared_link)
    db.session.commit()

    # Teacher1 still only sees class1 history.
    _login_admin_to_class(client, teacher1_id, data["class1"], data["teacher1_seat"])

    response1 = client.get('/api/hall-pass/history')
    json_data1 = response1.get_json()
    assert json_data1['total'] == 1
    student_names1 = [record['student_name'] for record in json_data1['records']]
    assert 'Alice A.' in student_names1

    # Teacher2 still only sees class3 history.
    _login_admin_to_class(client, teacher2_id, data["class3"], data["teacher2_seat"])

    response2 = client.get('/api/hall-pass/history')
    json_data2 = response2.get_json()
    assert json_data2['total'] == 1
    student_names2 = [record['student_name'] for record in json_data2['records']]
    assert 'Alice A.' not in student_names2
    assert 'Charlie C.' in student_names2
    assert 'Diana D.' not in student_names2


def test_hall_pass_history_period_filter(client, setup_multi_teacher_hall_pass_history):
    """Test that period filter works correctly and is scoped to teacher."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id

    _login_admin_to_class(client, teacher1_id, data["class1"], data["teacher1_seat"])

    # Filter by period "A" (still class-scoped to class1).
    response = client.get('/api/hall-pass/history?period=A')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert json_data['total'] == 1
    assert json_data['records'][0]['student_name'] == 'Alice A.'
    assert json_data['records'][0]['period'] == 'A'


def test_hall_pass_history_pagination(client, setup_multi_teacher_hall_pass_history):
    """Test that pagination works correctly."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id

    _login_admin_to_class(client, teacher1_id, data["class1"], data["teacher1_seat"])

    # Request page 1 with page_size 1
    response = client.get('/api/hall-pass/history?page=1&page_size=1')
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert json_data['total'] == 1
    assert len(json_data['records']) == 1
    assert json_data['page'] == 1
    assert json_data['total_pages'] == 1
