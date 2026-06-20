"""
Test multi-tenancy for admin/teacher routes.

Ensures that teachers can only see their own students and not students
belonging to other teachers.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
import sqlalchemy as sa
from app import app as flask_app
from app.models import Admin, IdentityProfile, Student, StudentTeacher
from app.extensions import db
from app.auth import get_admin_student_query
from app.hash_utils import get_random_salt


@pytest.fixture
def multi_teacher_data(client):
    """Create test data with multiple teachers and students."""
    # Create two teachers
    teacher1 = make_admin("teacher1", "SECRET1")
    teacher2 = make_admin("teacher2", "SECRET2")
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.flush()
    
    # Create students for teacher1
    for i in range(5):
        salt = get_random_salt()
        profile = IdentityProfile(profile_type="student", first_name=f"StudentT1_{i}", last_name="A")
        db.session.add(profile)
        db.session.flush()
        student = Student(
            identity_profile=profile,
            block="A",
            salt=salt,
            first_half_hash=f"hash_t1_{i}",  # Unique hash for each student
        )
        db.session.add(student)
        db.session.flush()
        
        # Create StudentTeacher association
        db.session.add(StudentTeacher(
            student_id=student.id,
            teacher_id=teacher1.id
        ))
    
    # Create students for teacher2
    for i in range(3):
        salt = get_random_salt()
        profile = IdentityProfile(profile_type="student", first_name=f"StudentT2_{i}", last_name="B")
        db.session.add(profile)
        db.session.flush()
        student = Student(
            identity_profile=profile,
            block="B",
            salt=salt,
            first_half_hash=f"hash_t2_{i}",  # Unique hash for each student
        )
        db.session.add(student)
        db.session.flush()
        
        # Create StudentTeacher association
        db.session.add(StudentTeacher(
            student_id=student.id,
            teacher_id=teacher2.id
        ))
    
    db.session.commit()
    
    return teacher1, teacher2


def test_teacher_can_only_see_own_students(client, multi_teacher_data):
    """Test that a teacher can only query their own students."""
    teacher1, teacher2 = multi_teacher_data
    
    # Make a request to trigger request context, then query students
    with client.application.test_request_context():
        from flask import session
        
        # Set session directly in request context
        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        
        # Query students as teacher1
        students = get_admin_student_query().all()
        
        # Should only see teacher1's 5 students
        assert len(students) == 5, f"Teacher1 should see 5 students, but saw {len(students)}"
        
        # Verify all students belong to teacher1
        for student in students:
            assert student.display_first_name.startswith("StudentT1_"), \
                f"Teacher1 should only see StudentT1_ students, but saw {student.display_first_name}"


def test_brand_new_teacher_sees_no_students(client, multi_teacher_data):
    """Test that a brand new teacher with no students sees 0 students."""
    # multi_teacher_data fixture creates test data but we don't need the teacher objects here
    
    # Create a brand new teacher with no students
    new_teacher = make_admin("new_teacher", "SECRET3")
    db.session.add(new_teacher)
    db.session.commit()
    
    # Make a request to trigger request context, then query students
    with client.application.test_request_context():
        from flask import session
        
        # Set session directly in request context
        session['is_admin'] = True
        session['admin_id'] = new_teacher.id
        
        # Query students as new teacher
        students = get_admin_student_query().all()
        
        # Should see 0 students
        assert len(students) == 0, \
            f"Brand new teacher should see 0 students, but saw {len(students)} students: {[s.display_first_name for s in students]}"


def test_teacher2_sees_only_their_students(client, multi_teacher_data):
    """Test that teacher2 only sees their 3 students."""
    teacher1, teacher2 = multi_teacher_data
    
    # Make a request to trigger request context, then query students
    with client.application.test_request_context():
        from flask import session
        
        # Set session directly in request context
        session['is_admin'] = True
        session['admin_id'] = teacher2.id
        
        # Query students as teacher2
        students = get_admin_student_query().all()
        
        # Should only see teacher2's 3 students
        assert len(students) == 3, f"Teacher2 should see 3 students, but saw {len(students)}"
        
        # Verify all students belong to teacher2
        for student in students:
            assert student.display_first_name.startswith("StudentT2_"), \
                f"Teacher2 should only see StudentT2_ students, but saw {student.display_first_name}"


def test_students_with_null_teacher_id_not_visible_to_teachers(client):
    """Test that students with NULL teacher_id are not visible to any regular teacher."""
    # Create a teacher
    teacher1 = make_admin("teacher1", "SECRET1")
    db.session.add(teacher1)
    db.session.flush()
    
    # Create a student with NULL teacher_id (orphaned student)
    salt = get_random_salt()
    orphaned_student = Student(
        first_name="OrphanedStudent",
        last_initial="Z",
        block="Z",
        salt=salt,
        first_half_hash="hash_orphan",
    )
    db.session.add(orphaned_student)
    db.session.commit()
    
    # Verify the orphaned student exists in the database (by ID since first_name is encrypted)
    assert Student.query.filter_by(id=orphaned_student.id).first() is not None
    
    # Make a request to trigger request context, then query students
    with client.application.test_request_context():
        from flask import session
        
        # Set session directly in request context
        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        
        # Query students as teacher1
        students = get_admin_student_query().all()
        
        # Teacher should NOT see the orphaned student
        assert len(students) == 0, \
            f"Teacher should see 0 students (orphaned student should not be visible), but saw {len(students)}"
        
        # Verify orphaned student is not in the results
        student_names = [s.display_first_name for s in students]
        assert "OrphanedStudent" not in student_names, \
            f"Orphaned student should not be visible to teacher, but was found in results: {student_names}"


def test_system_admin_flag_not_set_accidentally(client):
    """
    Test that a regular teacher login doesn't accidentally set is_system_admin.
    
    This is a CRITICAL security test. If is_system_admin is accidentally set to True
    for a regular teacher, they will see ALL students in the system.
    """
    # Create a regular teacher
    teacher1 = make_admin("teacher1", "SECRET1")
    db.session.add(teacher1)
    db.session.flush()
    
    # Create students for another teacher to ensure there's data
    teacher2 = make_admin("teacher2", "SECRET2")
    db.session.add(teacher2)
    db.session.flush()
    
    for i in range(200):  # Create 200 students for teacher2
        salt = get_random_salt()
        student = Student(
            first_name=f"StudentT2_{i}",
            last_initial="B",
            block="B",
            salt=salt,
            first_half_hash=f"hash_t2_sys_{i}",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(StudentTeacher(
            student_id=student.id,
            teacher_id=teacher2.id
        ))
    
    db.session.commit()
    
    # Simulate a regular teacher login (WITHOUT is_system_admin)
    with client.application.test_request_context():
        from flask import session
        
        # Set session as a regular admin (this is what happens in normal login)
        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        # Explicitly ensure is_system_admin is NOT set
        session.pop('is_system_admin', None)
        
        # Query students
        students = get_admin_student_query().all()
        
        # Teacher1 should see 0 students (since they have none)
        assert len(students) == 0, \
            f"Regular teacher should see 0 students, but saw {len(students)}. " \
            f"This indicates is_system_admin might be set incorrectly!"
    
    # Now test what happens if is_system_admin is accidentally set
    with client.application.test_request_context():
        from flask import session
        
        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        session['is_system_admin'] = True  # ACCIDENTALLY SET!
        
        # Query students
        students = get_admin_student_query().all()
        
        # With is_system_admin=True, they WOULD see all students
        assert len(students) == 200, \
            f"With is_system_admin=True, should see all 200 students, but saw {len(students)}"


def test_orphaned_students_from_deleted_teacher(client):
    """
    CRITICAL BUG TEST: Test that students from a deleted teacher are not visible to a new teacher with the same ID.
    
    This test verifies that even if students remain "orphaned" (no StudentTeacher links),
    a new teacher who reuses that ID cannot see them unless they are explicitly linked via StudentTeacher.
    
    NOTE: The legacy Student.teacher_id column has been dropped. Students are now linked ONLY
    via the StudentTeacher table. This test verifies the new architecture correctly isolates students.
    """
    # Simulate the historical scenario
    
    # Step 1: Create teacher 1 and their students
    teacher1 = make_admin("teacher1", "SECRET1")
    db.session.add(teacher1)
    db.session.flush()
    teacher1_id = teacher1.id
    
    # Create 5 students for teacher1
    student_ids = []
    for i in range(5):
        salt = get_random_salt()
        student = Student(
            first_name=f"OldStudent_{i}",
            last_initial="O",
            block="O",
            salt=salt,
            first_half_hash=f"hash_old_{i}",
        )
        db.session.add(student)
        db.session.flush()
        student_ids.append(student.id)
        
        # Create StudentTeacher association (the ONLY way to link students to teachers)
        db.session.add(StudentTeacher(
            student_id=student.id,
            teacher_id=teacher1_id
        ))
    
    db.session.commit()
    
    # Step 2: Delete teacher1
    # First, delete StudentTeacher records (these have CASCADE delete)
    StudentTeacher.query.filter_by(teacher_id=teacher1_id).delete()
    # Then delete the teacher
    db.session.delete(teacher1)
    db.session.commit()
    
    # Step 3: Create a NEW teacher that gets the SAME ID
    teacher2 = make_admin("teacher2", "SECRET2")
    db.session.add(teacher2)
    db.session.flush()
    
    # Manually set teacher2's ID to the same as teacher1 (simulating ID reuse)
    teacher2_original_id = teacher2.id
    connection = db.session.connection()
    connection.execute(
        sa.text("UPDATE teachers SET id = :new_id WHERE id = :old_id"),
        {'new_id': teacher1_id, 'old_id': teacher2_original_id}
    )
    db.session.commit()
    
    # Verify teacher2 now has the same ID as teacher1 had
    from app.utils.auth_username import hash_username_lookup
    teacher2_reloaded = Admin.query.filter_by(username_lookup_hash=hash_username_lookup("teacher2")).first()
    assert teacher2_reloaded.id == teacher1_id, "Teacher2 should have same ID as deleted teacher1"

    # Verify orphaned students still exist in the database (they're just not linked to anyone)
    orphaned_students = Student.query.filter(Student.id.in_(student_ids)).all()
    
    # SQLite behavior note: In production (PostgreSQL), students may persist after their
    # associated teacher is deleted. In SQLite (test environment), CASCADE behavior may
    # delete them automatically. We recreate orphaned students to simulate the real-world
    # scenario where students become "orphaned" - they exist in the database but have no
    # active StudentTeacher links. This tests that teachers CANNOT see students simply
    # because the teacher's ID happens to match a previously-used ID.
    if len(orphaned_students) == 0:
        for i in range(5):
            salt = get_random_salt()
            student = Student(
                first_name=f"OldStudent_{i}",
                last_initial="O",
                block="O",
                salt=salt,
                first_half_hash=f"hash_old_orphaned_{i}",
            )
            db.session.add(student)
        db.session.commit()
    
    # Step 4: Check if teacher2 can see the orphaned students
    with client.application.test_request_context():
        from flask import session
        session['is_admin'] = True
        session['admin_id'] = teacher1_id  # Using the reused ID
        
        students = get_admin_student_query().all()
        
        # FIX: Teacher2 should NOT see orphaned students because we now use ONLY StudentTeacher
        # Since there are no StudentTeacher links for teacher2 (ID reuse), they see 0 students
        assert len(students) == 0, \
            f"Security Fix: New teacher with reused ID should see 0 orphaned students, but saw {len(students)}."


