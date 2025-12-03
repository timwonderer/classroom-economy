"""
Tests for hall pass queue API endpoint scoping.

Ensures that the /api/hall-pass/queue endpoint properly scopes
hall pass data by teacher_id to prevent cross-teacher data leakage.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.models import (
    Student, Admin, HallPassLog, StudentTeacher, HallPassSettings
)
from app.extensions import db
from hash_utils import get_random_salt, hash_username


@pytest.fixture
def setup_multi_teacher_hall_passes(client):
    """Create two teachers with students and hall passes for testing scoping."""
    # Create two teachers
    teacher1 = Admin(
        username="teacher1",
        totp_secret="secret1"
    )
    teacher2 = Admin(
        username="teacher2",
        totp_secret="secret2"
    )
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.commit()

    # Create students for teacher1
    salt1 = get_random_salt()
    student1 = Student(
        first_name="Alice",
        last_initial="A",
        block="Period1",
        salt=salt1,
        username_hash=hash_username("alice_a", salt1),
        teacher_id=teacher1.id
    )
    
    salt2 = get_random_salt()
    student2 = Student(
        first_name="Bob",
        last_initial="B",
        block="Period1",
        salt=salt2,
        username_hash=hash_username("bob_b", salt2),
        teacher_id=teacher1.id
    )

    # Create students for teacher2
    salt3 = get_random_salt()
    student3 = Student(
        first_name="Charlie",
        last_initial="C",
        block="Period2",
        salt=salt3,
        username_hash=hash_username("charlie_c", salt3),
        teacher_id=teacher2.id
    )
    
    salt4 = get_random_salt()
    student4 = Student(
        first_name="Diana",
        last_initial="D",
        block="Period2",
        salt=salt4,
        username_hash=hash_username("diana_d", salt4),
        teacher_id=teacher2.id
    )

    db.session.add_all([student1, student2, student3, student4])
    db.session.commit()

    # Create hall pass settings for both teachers
    settings1 = HallPassSettings(
        teacher_id=teacher1.id,
        queue_enabled=True,
        queue_limit=10
    )
    settings2 = HallPassSettings(
        teacher_id=teacher2.id,
        queue_enabled=True,
        queue_limit=10
    )
    db.session.add_all([settings1, settings2])
    db.session.commit()

    # Create hall passes for teacher1's students
    now = datetime.now(timezone.utc)
    
    # Approved pass for student1 (teacher1)
    pass1 = HallPassLog(
        student_id=student1.id,
        reason="Restroom",
        status="approved",
        decision_time=now - timedelta(minutes=5)
    )
    
    # Currently out pass for student2 (teacher1)
    pass2 = HallPassLog(
        student_id=student2.id,
        reason="Office",
        status="left",
        left_time=now - timedelta(minutes=3),
        decision_time=now - timedelta(minutes=10)
    )

    # Create hall passes for teacher2's students
    # Approved pass for student3 (teacher2)
    pass3 = HallPassLog(
        student_id=student3.id,
        reason="Nurse",
        status="approved",
        decision_time=now - timedelta(minutes=2)
    )
    
    # Currently out pass for student4 (teacher2)
    pass4 = HallPassLog(
        student_id=student4.id,
        reason="Locker",
        status="left",
        left_time=now - timedelta(minutes=1),
        decision_time=now - timedelta(minutes=8)
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


def test_hall_pass_queue_requires_teacher_id(client, setup_multi_teacher_hall_passes):
    """Test that the queue endpoint requires teacher_id parameter."""
    response = client.get('/api/hall-pass/queue')
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'teacher_id' in data['message']


def test_hall_pass_queue_scopes_to_teacher1(client, setup_multi_teacher_hall_passes):
    """Test that teacher1 only sees their own students' hall passes."""
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    
    response = client.get(f'/api/hall-pass/queue?teacher_id={teacher1_id}')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher1 should see 1 in queue (student1) and 1 currently out (student2)
    assert len(json_data['queue']) == 1
    assert json_data['currently_out'] == 1
    assert json_data['total'] == 2
    
    # Verify it's the correct student in queue
    assert json_data['queue'][0]['student_name'] == 'Alice A.'
    assert json_data['queue'][0]['destination'] == 'Restroom'


def test_hall_pass_queue_scopes_to_teacher2(client, setup_multi_teacher_hall_passes):
    """Test that teacher2 only sees their own students' hall passes."""
    data = setup_multi_teacher_hall_passes
    teacher2_id = data['teacher2'].id
    
    response = client.get(f'/api/hall-pass/queue?teacher_id={teacher2_id}')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Teacher2 should see 1 in queue (student3) and 1 currently out (student4)
    assert len(json_data['queue']) == 1
    assert json_data['currently_out'] == 1
    assert json_data['total'] == 2
    
    # Verify it's the correct student in queue
    assert json_data['queue'][0]['student_name'] == 'Charlie C.'
    assert json_data['queue'][0]['destination'] == 'Nurse'


def test_hall_pass_queue_with_shared_student(client, setup_multi_teacher_hall_passes):
    """Test that shared students are visible to both teachers."""
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    teacher2_id = data['teacher2'].id
    student1_id = data['student1'].id
    
    # Share student1 (originally teacher1's) with teacher2
    shared_link = StudentTeacher(
        student_id=student1_id,
        admin_id=teacher2_id
    )
    db.session.add(shared_link)
    db.session.commit()
    
    # Teacher1 should still see student1 in queue
    response1 = client.get(f'/api/hall-pass/queue?teacher_id={teacher1_id}')
    json_data1 = response1.get_json()
    assert len(json_data1['queue']) == 1
    assert json_data1['queue'][0]['student_name'] == 'Alice A.'
    
    # Teacher2 should now also see student1 in queue (in addition to their own)
    response2 = client.get(f'/api/hall-pass/queue?teacher_id={teacher2_id}')
    json_data2 = response2.get_json()
    # Teacher2 now has 2 students in queue: Charlie (their original) + Alice (shared)
    assert len(json_data2['queue']) == 2
    student_names = [item['student_name'] for item in json_data2['queue']]
    assert 'Alice A.' in student_names
    assert 'Charlie C.' in student_names


def test_hall_pass_queue_uses_session_admin_id(client, setup_multi_teacher_hall_passes):
    """Test that endpoint uses session admin_id if no teacher_id param provided."""
    data = setup_multi_teacher_hall_passes
    teacher1_id = data['teacher1'].id
    
    # Simulate admin login by setting session
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher1_id
    
    # Request without teacher_id parameter
    response = client.get('/api/hall-pass/queue')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    
    # Should see teacher1's data
    assert len(json_data['queue']) == 1
    assert json_data['queue'][0]['student_name'] == 'Alice A.'


def test_hall_pass_queue_rejects_invalid_teacher_id(client):
    """Test that endpoint returns 404 for non-existent teacher_id."""
    response = client.get('/api/hall-pass/queue?teacher_id=99999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'Invalid teacher_id' in data['message']


def test_hall_pass_queue_rejects_cross_teacher_access(client, setup_multi_teacher_hall_passes):
    """Test that teacher1 cannot access teacher2's queue."""
    data = setup_multi_teacher_hall_passes
    teacher2_id = data['teacher2'].id
    
    # Login as teacher1
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = data['teacher1'].id
    
    # Try to access teacher2's queue
    response = client.get(f'/api/hall-pass/queue?teacher_id={teacher2_id}')
    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data['status'] == 'error'
    assert 'Unauthorized' in json_data['message']
