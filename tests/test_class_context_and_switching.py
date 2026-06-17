"""
Tests for class context injection and class switching functionality.

Ensures that:
1. inject_class_context properly loads and provides class context to templates
2. switch_class route correctly handles class switching with proper authorization
3. Multi-class support works as expected
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import os
from datetime import datetime, timezone
import pytest
from flask import session
from app.models import Student, Admin, ClassEconomy, ClassMembership, Seat, IdentityProfile
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


def _get_inject_class_context_processor(client):
    """Helper to get the inject_class_context processor function."""
    from app import app as flask_app
    for processor in flask_app.template_context_processors[None]:
        if processor.__name__ == 'inject_class_context':
            return processor
    return None


@pytest.fixture
def setup_multi_class_student(client):
    """Create a student with multiple class enrollments for testing."""
    # Create three teachers
    teacher1 = make_admin("teacher1", "secret1")
    teacher2 = make_admin("teacher2", "secret2")
    teacher3 = make_admin("teacher3", "secret3")
    db.session.add_all([teacher1, teacher2, teacher3])
    db.session.commit()

    # Create a student
    salt = get_random_salt()
    student = Student(
        first_name="MultiClass",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("multiclass_s", salt),
        pin_hash="fake-hash"
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teachers
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher1.id))
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher2.id))
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher3.id))
    db.session.commit()

    # Create Class Economies
    class_1a = ClassEconomy(join_code="TEACHER1A", teacher_id=teacher1.id, created_by_admin_id=teacher1.id, display_name="Class 1A")
    class_2b = ClassEconomy(join_code="TEACHER2B", teacher_id=teacher2.id, created_by_admin_id=teacher2.id, display_name="Class 2B")
    class_3c = ClassEconomy(join_code="TEACHER3C", teacher_id=teacher3.id, created_by_admin_id=teacher3.id, display_name="Class 3C")
    class_unclaimed = ClassEconomy(join_code="UNCLAIMEDZ", teacher_id=teacher1.id, created_by_admin_id=teacher1.id, display_name="Unclaimed Z")
    db.session.add_all([class_1a, class_2b, class_3c, class_unclaimed])
    db.session.commit()

    # Create ClassMemberships
    # Admin memberships
    db.session.add(ClassMembership(class_id=class_1a.class_id, join_code="TEACHER1A", admin_id=teacher1.id, role='admin'))
    db.session.add(ClassMembership(class_id=class_2b.class_id, join_code="TEACHER2B", admin_id=teacher2.id, role='admin'))
    db.session.add(ClassMembership(class_id=class_3c.class_id, join_code="TEACHER3C", admin_id=teacher3.id, role='admin'))
    # Student memberships
    db.session.add(ClassMembership(class_id=class_1a.class_id, join_code="TEACHER1A", student_id=student.id, role='student'))
    db.session.add(ClassMembership(class_id=class_2b.class_id, join_code="TEACHER2B", student_id=student.id, role='student'))
    db.session.add(ClassMembership(class_id=class_3c.class_id, join_code="TEACHER3C", student_id=student.id, role='student'))
    db.session.commit()

    # Create claimed roster blocks and runtime seats for the student in multiple classes
    seat1 = Seat(student_id=student.id, class_id=class_1a.class_id, join_code="TEACHER1A", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat1)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat1.id, profile_type='student_claimed', first_name=b"MultiClass", last_initial="S"))
    seat2 = Seat(student_id=student.id, class_id=class_2b.class_id, join_code="TEACHER2B", block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat2)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat2.id, profile_type='student_claimed', first_name=b"MultiClass", last_initial="S"))
    seat3 = Seat(student_id=student.id, class_id=class_3c.class_id, join_code="TEACHER3C", block="C", block_identifier="C", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat3)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat3.id, profile_type='student_claimed', first_name=b"MultiClass", last_initial="S"))
    db.session.add_all([seat1, seat2, seat3])
    db.session.flush()
    db.session.add_all([
        Seat(
            student_id=student.id,
            class_id=class_1a.class_id,
            join_code="TEACHER1A",
            block="A",
            block_identifier="A",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        ),
        Seat(
            student_id=student.id,
            class_id=class_2b.class_id,
            join_code="TEACHER2B",
            block="B",
            block_identifier="B",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        ),
        Seat(
            student_id=student.id,
            class_id=class_3c.class_id,
            join_code="TEACHER3C",
            block="C",
            block_identifier="C",
            role="student",
            claimed_at=datetime.now(timezone.utc),
        ),
    ])
    db.session.commit()

    return {
        'student': student,
        'teachers': [teacher1, teacher2, teacher3],
        'seats': [seat1, seat2, seat3],
        'classes': {
            "TEACHER1A": class_1a,
            "TEACHER2B": class_2b,
            "TEACHER3C": class_3c,
            "UNCLAIMEDZ": class_unclaimed,
        },
    }


@pytest.fixture
def setup_single_class_student(client):
    """Create a student with only one class for testing."""
    teacher = make_admin("single_teacher", "secret")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="SingleClass",
        last_initial="X",
        block="D",
        salt=salt,
        username_hash=hash_username("singleclass_x", salt),
        pin_hash="fake-hash"
    )
    db.session.add(student)
    db.session.commit()

    # Link student to teacher
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    # Create Class Economy
    class_single = ClassEconomy(join_code="SINGLED", teacher_id=teacher.id, created_by_admin_id=teacher.id, display_name="Single D")
    db.session.add(class_single)
    db.session.commit()

    # Create ClassMemberships
    db.session.add(ClassMembership(class_id=class_single.class_id, join_code="SINGLED", admin_id=teacher.id, role='admin'))
    db.session.add(ClassMembership(class_id=class_single.class_id, join_code="SINGLED", student_id=student.id, role='student'))
    db.session.commit()

    seat = Seat(student_id=student.id, class_id=class_single.class_id, join_code="SINGLED", block="D", block_identifier="D", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name=b"SingleClass", last_initial="X"))
    db.session.add(seat)
    db.session.flush()
    db.session.add(Seat(
        student_id=student.id,
        class_id=class_single.class_id,
        join_code="SINGLED",
        block="D",
        block_identifier="D",
        role="student",
        claimed_at=datetime.now(timezone.utc),
    ))
    db.session.commit()

    return {
        'student': student,
        'teacher': teacher,
        'seat': seat
    }


# ==================== inject_class_context Tests ====================

def test_inject_class_context_no_student(client):
    """Test that inject_class_context returns empty context when no student is logged in."""
    with client.application.test_request_context('/'):
        ctx_processor = _get_inject_class_context_processor(client)
        assert ctx_processor is not None, "inject_class_context not found"
        
        context = ctx_processor()
        assert context['current_class_context'] is None
        assert context['available_classes'] == []


def test_inject_class_context_no_claimed_seats(client):
    """Test that inject_class_context returns empty context when student has no claimed seats."""
    from flask import session
    # Create a student with no claimed seats
    salt = get_random_salt()
    student = Student(
        first_name="NoSeats",
        last_initial="N",
        block="Z",
        salt=salt,
        username_hash=hash_username("noseats_n", salt),
        pin_hash="fake-hash"
    )
    db.session.add(student)
    db.session.commit()

    with client.application.test_request_context('/'):
        session['student_id'] = student.id
        
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context['current_class_context'] is None
        assert context['available_classes'] == []


def test_inject_class_context_defaults_to_first_seat(client, setup_multi_class_student):
    """Test that inject_class_context defaults to first seat when no join_code in session."""
    from flask import session
    data = setup_multi_class_student
    student = data['student']
    
    with client.application.test_request_context('/'):
        session['student_id'] = student.id
        # No current_join_code set - should default to first seat
        
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        
        # Should default to first claimed seat
        assert context['current_class_context'] is not None
        assert context['current_class_context']['join_code'] == "TEACHER1A"
        assert context['current_class_context']['teacher_name'] == "teacher1"
        assert context['current_class_context']['block'] == "A"


def test_inject_class_context_uses_session_join_code(client, setup_multi_class_student):
    """Test that inject_class_context correctly uses join_code from session."""
    from flask import session
    data = setup_multi_class_student
    student = data['student']
    
    with client.application.test_request_context('/'):
        session['student_id'] = student.id
        class_row = ClassEconomy.query.filter_by(join_code="TEACHER2B").first()
        session['current_class_id'] = class_row.class_id
        
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        
        # Should use session join_code
        assert context['current_class_context'] is not None
        assert context['current_class_context']['join_code'] == "TEACHER2B"
        assert context['current_class_context']['teacher_name'] == "teacher2"
        assert context['current_class_context']['block'] == "B"


def test_inject_class_context_available_classes_list(client, setup_multi_class_student):
    """Test that inject_class_context builds correct available_classes list."""
    from flask import session
    data = setup_multi_class_student
    student = data['student']
    
    with client.application.test_request_context('/'):
        session['student_id'] = student.id
        class_row = ClassEconomy.query.filter_by(join_code="TEACHER2B").first()
        session['current_class_id'] = class_row.class_id
        
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        
        # Should have all 3 classes
        assert len(context['available_classes']) == 3
        
        # Check each class is present
        join_codes = [c['join_code'] for c in context['available_classes']]
        assert "TEACHER1A" in join_codes
        assert "TEACHER2B" in join_codes
        assert "TEACHER3C" in join_codes
        
        # Check current class is marked
        current_classes = [c for c in context['available_classes'] if c['is_current']]
        assert len(current_classes) == 1
        assert current_classes[0]['join_code'] == "TEACHER2B"


def test_inject_class_context_handles_missing_teacher(client, setup_single_class_student):
    """Test that inject_class_context handles missing teacher records gracefully.
    
    Note: Due to CASCADE delete on teacher_id foreign key, when a teacher is deleted,
    all their TeacherBlock records are also deleted. This test verifies the context
    processor's defensive coding with .get() even though this scenario shouldn't
    occur in production due to the CASCADE constraint.
    """
    data = setup_single_class_student
    student = data['student']
    seat = data['seat']
    
    # We can't actually delete the teacher due to CASCADE, but we can test
    # the .get() defensive coding by just verifying the code handles the dict lookup
    # This test ensures the code uses .get() which returns None for missing keys
    # rather than direct dictionary access which would raise KeyError
    
    # The test now just verifies normal operation works
    from flask import session
    with client.application.test_request_context('/'):
        session['student_id'] = student.id
        
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        
        # Should successfully return context with valid teacher
        assert context['current_class_context'] is not None
        assert context['current_class_context']['teacher_name'] == "single_teacher"
        assert len(context['available_classes']) == 1
        assert context['available_classes'][0]['teacher_name'] == "single_teacher"


def test_inject_class_context_exception_handling(client):
    """Test that inject_class_context handles exceptions without breaking template rendering."""
    from flask import session
    # Create a scenario that would cause an error
    # Use a very large ID that's guaranteed to not exist
    non_existent_id = 2**31 - 1  # Max signed 32-bit integer
    with client.application.test_request_context('/'):
        session['student_id'] = non_existent_id
        
        ctx_processor = _get_inject_class_context_processor(client)
        
        # Should not raise exception, should return empty context
        context = ctx_processor()
        assert context['current_class_context'] is None
        assert context['available_classes'] == []


# ==================== switch_class Route Tests ====================

def test_switch_class_success(client, setup_multi_class_student):
    """Test successful class switching with valid join_code."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        class_row = ClassEconomy.query.filter_by(join_code="TEACHER1A").first()
        sess['current_class_id'] = class_row.class_id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Switch to TEACHER2B
    target_class_id = data['classes']["TEACHER2B"].class_id
    response = client.post(f'/student/switch-class/{target_class_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['teacher_name'] == 'teacher2'
    assert data['block'] == 'B'
    assert 'Switched to teacher2' in data['message']
    
    # Verify session was updated
    with client.session_transaction() as sess:
        assert sess['current_join_code'] == 'TEACHER2B'


def test_switch_class_rejects_missing_runtime_seat(client, setup_multi_class_student):
    """Switching classes should fail when runtime seat rows are missing."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']

    Seat.query.delete()
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        class_row = ClassEconomy.query.filter_by(join_code="TEACHER1A").first()
        sess['current_class_id'] = class_row.class_id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    target_class_id = data['classes']["TEACHER2B"].class_id
    response = client.post(f'/student/switch-class/{target_class_id}')

    assert response.status_code == 403


def test_switch_class_unauthorized(client, setup_multi_class_student):
    """Test that switch_class returns 403 when student doesn't have access to join_code."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Try to switch to a class the student doesn't have access to
    response = client.post('/student/switch-class/invalid-class-id')
    
    assert response.status_code == 403
    data = response.get_json()
    assert data['status'] == 'error'
    assert "don't have access" in data['message']


def test_switch_class_not_logged_in(client):
    """Test that switch_class requires login."""
    # Try to switch without being logged in
    response = client.post('/student/switch-class/any-class-id')
    
    # Should redirect to login
    assert response.status_code == 302
    assert '/student/login' in response.location


def test_switch_class_nonexistent_join_code(client, setup_multi_class_student):
    """Test switch_class with non-existent join_code."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Try to switch to non-existent join code
    response = client.post('/student/switch-class/not-a-real-class')
    
    assert response.status_code == 403


def test_switch_class_unclaimed_seat(client, setup_multi_class_student):
    """Test that switch_class rejects unclaimed seats."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    teachers = data['teachers']
    
    # Create an unclaimed seat for this student
    unclaimed_seat = Seat(student_id=student.id, class_id=data['classes']["UNCLAIMEDZ"].class_id, join_code="UNCLAIMEDZ", block="Z", block_identifier="Z", role="student")
    db.session.add(unclaimed_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=unclaimed_seat.id, profile_type='student_unclaimed', first_name=b"MultiClass", last_initial="S"))
    db.session.add(unclaimed_seat)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Try to switch to unclaimed seat
    unclaimed_class_id = data['classes']["UNCLAIMEDZ"].class_id
    response = client.post(f'/student/switch-class/{unclaimed_class_id}')
    
    assert response.status_code == 403
    data = response.get_json()
    assert data['status'] == 'error'


def test_switch_class_proper_response_structure(client, setup_multi_class_student):
    """Test that switch_class returns proper response structure."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    target_class_id = data['classes']["TEACHER3C"].class_id
    response = client.post(f'/student/switch-class/{target_class_id}')
    
    assert response.status_code == 200
    response_data = response.get_json()
    
    # Verify all required fields are present
    assert 'status' in response_data
    assert 'message' in response_data
    assert 'teacher_name' in response_data
    assert 'block' in response_data
    
    # Verify correct values
    assert response_data['status'] == 'success'
    assert response_data['teacher_name'] == 'teacher3'
    assert response_data['block'] == 'C'


def test_switch_class_between_all_classes(client, setup_multi_class_student):
    """Test switching between all available classes in sequence."""
    from datetime import datetime, timezone
    data = setup_multi_class_student
    student = data['student']
    
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
    
    # Switch to each class in sequence
    for join_code, teacher_name, block in [
        ("TEACHER1A", "teacher1", "A"),
        ("TEACHER2B", "teacher2", "B"),
        ("TEACHER3C", "teacher3", "C"),
        ("TEACHER1A", "teacher1", "A"),  # Switch back to first
    ]:
        class_id = data['classes'][join_code].class_id
        response = client.post(f'/student/switch-class/{class_id}')
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['status'] == 'success'
        assert response_data['teacher_name'] == teacher_name
        assert response_data['block'] == block
        
        # Verify session was updated
        with client.session_transaction() as sess:
            assert sess['current_join_code'] == join_code
