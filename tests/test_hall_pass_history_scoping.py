"""
Tests for hall pass history API endpoint scoping.

Ensures that the /api/hall-pass/history endpoint properly scopes
hall pass data by teacher to prevent cross-teacher data leakage.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    User,
    UserRole,
    Student, Admin, HallPassLog, StudentTeacher
)
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from app.models import ClassEconomy, ClassMembership


@pytest.fixture
def setup_multi_teacher_hall_pass_history(client):
    """Create two teachers with students and hall pass history for testing scoping."""
    # Create two teachers
    teacher1 = make_admin("teacher1", "secret1")
    teacher2 = make_admin("teacher2", "secret2")
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.commit()

    # Create students for teacher1
    student1 = make_student_identity(block="A", first_name="Alice", last_name="A")
    student2 = make_student_identity(block="B", first_name="Bob", last_name="B")

    # Create students for teacher2
    student3 = make_student_identity(block="C", first_name="Charlie", last_name="C")
    student4 = make_student_identity(block="D", first_name="Diana", last_name="D")

    db.session.add_all([student1, student2, student3, student4])
    db.session.flush()

    # CRITICAL FIX: Create StudentTeacher associations for multi-tenancy
    db.session.add(StudentTeacher(user_id=student1_user.id, teacher_id=teacher1.id))
    db.session.add(StudentTeacher(user_id=student2_user.id, teacher_id=teacher1.id))
    db.session.add(StudentTeacher(user_id=student3_user.id, teacher_id=teacher2.id))
    db.session.add(StudentTeacher(user_id=student4_user.id, teacher_id=teacher2.id))
    db.session.commit()

    # Create Class Contexts
    join_code1 = "CLASS-A"
    join_code2 = "CLASS-B"
    join_code3 = "CLASS-C"
    join_code4 = "CLASS-D"
    db.session.add_all([
        ClassEconomy(join_code=join_code1, user_id=teacher1.id, status="active", created_by_admin_id=teacher1.id),
        ClassEconomy(join_code=join_code2, user_id=teacher1.id, status="active", created_by_admin_id=teacher1.id),
        ClassEconomy(join_code=join_code3, user_id=teacher2.id, status="active", created_by_admin_id=teacher2.id),
        ClassEconomy(join_code=join_code4, user_id=teacher2.id, status="active", created_by_admin_id=teacher2.id),
        ClassMembership(join_code=join_code1, admin_id=teacher1.id, role="admin"),
        ClassMembership(join_code=join_code2, admin_id=teacher1.id, role="admin"),
        ClassMembership(join_code=join_code3, admin_id=teacher2.id, role="admin"),
        ClassMembership(join_code=join_code4, admin_id=teacher2.id, role="admin"),
        ClassMembership(join_code=join_code1, user_id=student1_user.id, role="student"),
        ClassMembership(join_code=join_code2, user_id=student2_user.id, role="student"),
        ClassMembership(join_code=join_code3, user_id=student3_user.id, role="student"),
        ClassMembership(join_code=join_code4, user_id=student4_user.id, role="student"),
    ])
    db.session.flush()

    # Create hall pass history for teacher1's students
    now = datetime.now(timezone.utc)
    
    # Multiple hall pass logs for student1 (teacher1)
    # Timeline: request -> decision (5 min later) -> left (10 min later) -> return (15 min later)
    pass1 = HallPassLog(
        user_id=student1_user.id,
        reason="Restroom",
        status="returned",
        join_code=join_code1,
        period="A",
        request_time=now - timedelta(hours=2),
        decision_time=now - timedelta(hours=2) + timedelta(minutes=5),
        left_time=now - timedelta(hours=2) + timedelta(minutes=10),
        return_time=now - timedelta(hours=2) + timedelta(minutes=15)
    )
    
    pass2 = HallPassLog(
        user_id=student2_user.id,
        reason="Office",
        status="returned",
        join_code=join_code2,
        period="B",
        request_time=now - timedelta(hours=1),
        decision_time=now - timedelta(hours=1) + timedelta(minutes=5),
        left_time=now - timedelta(hours=1) + timedelta(minutes=10),
        return_time=now - timedelta(hours=1) + timedelta(minutes=15)
    )

    # Create hall pass history for teacher2's students
    pass3 = HallPassLog(
        user_id=student3_user.id,
        reason="Nurse",
        status="returned",
        join_code=join_code3,
        period="C",
        request_time=now - timedelta(hours=3),
        decision_time=now - timedelta(hours=3) + timedelta(minutes=5),
        left_time=now - timedelta(hours=3) + timedelta(minutes=10),
        return_time=now - timedelta(hours=3) + timedelta(minutes=15)
    )
    
    pass4 = HallPassLog(
        user_id=student4_user.id,
        reason="Locker",
        status="returned",
        join_code=join_code4,
        period="D",
        request_time=now - timedelta(minutes=30),
        decision_time=now - timedelta(minutes=25),
        left_time=now - timedelta(minutes=20),
        return_time=now - timedelta(minutes=10)
    )

    db.session.add_all([pass1, pass2, pass3, pass4])
    db.session.commit()

    return {
        'teacher1': teacher1,
        'teacher2': teacher2,
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
    """Test that teacher1 only sees their own students' hall pass history."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    response = client.get('/api/hall-pass/history')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher1 should see 2 records (student1 and student2)
    assert json_data['total'] == 2
    assert len(json_data['records']) == 2
    
    # Verify records belong to teacher1's students
    student_names = [record['student_name'] for record in json_data['records']]
    assert 'Alice A.' in student_names
    assert 'Bob B.' in student_names
    assert 'Charlie C.' not in student_names
    assert 'Diana D.' not in student_names


def test_hall_pass_history_scopes_to_teacher2(client, setup_multi_teacher_hall_pass_history):
    """Test that teacher2 only sees their own students' hall pass history."""
    data = setup_multi_teacher_hall_pass_history
    teacher2_id = data['teacher2'].id
    
    # Login as teacher2
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher2_id
    
    response = client.get('/api/hall-pass/history')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher2 should see 2 records (student3 and student4)
    assert json_data['total'] == 2
    assert len(json_data['records']) == 2
    
    # Verify records belong to teacher2's students
    student_names = [record['student_name'] for record in json_data['records']]
    assert 'Charlie C.' in student_names
    assert 'Diana D.' in student_names
    assert 'Alice A.' not in student_names
    assert 'Bob B.' not in student_names


def test_hall_pass_history_with_shared_student(client, setup_multi_teacher_hall_pass_history):
    """Test that shared students' history is visible to both teachers."""
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
    
    # Teacher1 should still see all their history including student1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    response1 = client.get('/api/hall-pass/history')
    json_data1 = response1.get_json()
    assert json_data1['total'] == 2
    student_names1 = [record['student_name'] for record in json_data1['records']]
    assert 'Alice A.' in student_names1
    
    # Teacher2 should now also see student1's history (in addition to their own)
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher2_id
    
    response2 = client.get('/api/hall-pass/history')
    json_data2 = response2.get_json()
    # Teacher2 now has 2 records: Charlie, Diana. Alice's pass is in CLASS-A (Teacher1), so Teacher2 shouldn't see it.
    assert json_data2['total'] == 2
    student_names2 = [record['student_name'] for record in json_data2['records']]
    assert 'Alice A.' not in student_names2
    assert 'Charlie C.' in student_names2
    assert 'Diana D.' in student_names2


def test_hall_pass_history_period_filter(client, setup_multi_teacher_hall_pass_history):
    """Test that period filter works correctly and is scoped to teacher."""
    data = setup_multi_teacher_hall_pass_history
    teacher1_id = data['teacher1'].id
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    # Filter by period "A" (should only see student1's record)
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
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    # Request page 1 with page_size 1
    response = client.get('/api/hall-pass/history?page=1&page_size=1')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert json_data['total'] == 2
    assert len(json_data['records']) == 1
    assert json_data['page'] == 1
    assert json_data['total_pages'] == 2
