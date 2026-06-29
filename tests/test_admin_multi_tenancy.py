"""
Test multi-tenancy for admin/teacher routes.

Ensures that teachers can only see their own students and not students
belonging to other teachers.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import create_class_scope, make_student_with_seat
import pytest
import sqlalchemy as sa
from app import app as flask_app
from app.models import Admin, IdentityProfile, Student, StudentTeacher, ClassEconomy, Seat, User, UserRole
from app.extensions import db
from app.routes.admin import _scoped_students
from app.hash_utils import get_random_salt
from uuid import uuid4


def _make_user_for_admin(admin):
    """Create a canonical User row bound to an Admin."""
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id
    return user


def _make_student_in_class(class_row, *, first_name, join_code, block="A", index=0):
    """Create a canonical student/seat pair for the target class."""
    student, seat = make_student_with_seat(
        class_id=class_row.class_id,
        join_code=join_code,
        block=block,
        first_name=first_name,
        last_name="A",
    )
    student.first_half_hash = f"hash_{uuid4().hex[:8]}"
    db.session.flush()
    return student, seat


@pytest.fixture
def multi_teacher_data(client):
    """Create test data with multiple teachers and students."""
    # Create two teachers
    teacher1 = make_admin(f"teacher1_{uuid4().hex[:6]}", "SECRET1")
    teacher2 = make_admin(f"teacher2_{uuid4().hex[:6]}", "SECRET2")
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.flush()

    user1 = _make_user_for_admin(teacher1)
    user2 = _make_user_for_admin(teacher2)
    db.session.flush()

    # Create a class for teacher1 and 5 students
    class1 = create_class_scope(
        teacher=teacher1,
        teacher_user_id=user1.id,
        join_code=f"MT1_{uuid4().hex[:4]}",
        block="A",
    )
    for i in range(5):
        _make_student_in_class(
            class1,
            first_name=f"StudentT1_{i}",
            join_code=class1.join_code,
            block="A",
            index=i,
        )

    # Create a class for teacher2 and 3 students
    class2 = create_class_scope(
        teacher=teacher2,
        teacher_user_id=user2.id,
        join_code=f"MT2_{uuid4().hex[:4]}",
        block="B",
    )
    for i in range(3):
        _make_student_in_class(
            class2,
            first_name=f"StudentT2_{i}",
            join_code=class2.join_code,
            block="B",
            index=i,
        )

    db.session.commit()

    return teacher1, teacher2, user1, user2


def test_teacher_can_only_see_own_students(client, multi_teacher_data):
    """Test that a teacher can only query their own students."""
    teacher1, teacher2, user1, user2 = multi_teacher_data

    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        g.canonical_context = SimpleNamespace(
            user_id=user1.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )

        students = _scoped_students().all()

        assert len(students) == 5, f"Teacher1 should see 5 students, but saw {len(students)}"

        for student in students:
            assert student.display_first_name.startswith("StudentT1_"), \
                f"Teacher1 should only see StudentT1_ students, but saw {student.display_first_name}"


def test_brand_new_teacher_sees_no_students(client, multi_teacher_data):
    """Test that a brand new teacher with no students sees 0 students."""
    new_teacher = make_admin(f"new_teacher_{uuid4().hex[:6]}", "SECRET3")
    db.session.add(new_teacher)
    db.session.flush()
    new_user = _make_user_for_admin(new_teacher)
    db.session.commit()

    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = new_teacher.id
        g.canonical_context = SimpleNamespace(
            user_id=new_user.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )

        students = _scoped_students().all()

        assert len(students) == 0, \
            f"Brand new teacher should see 0 students, but saw {len(students)} students: {[s.display_first_name for s in students]}"


def test_teacher2_sees_only_their_students(client, multi_teacher_data):
    """Test that teacher2 only sees their 3 students."""
    teacher1, teacher2, user1, user2 = multi_teacher_data

    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher2.id
        g.canonical_context = SimpleNamespace(
            user_id=user2.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )

        students = _scoped_students().all()

        assert len(students) == 3, f"Teacher2 should see 3 students, but saw {len(students)}"

        for student in students:
            assert student.display_first_name.startswith("StudentT2_"), \
                f"Teacher2 should only see StudentT2_ students, but saw {student.display_first_name}"


def test_students_with_null_teacher_id_not_visible_to_teachers(client):
    """Test that students with no class linkage are not visible to any regular teacher."""
    teacher1 = make_admin(f"teacher1_orphan_{uuid4().hex[:6]}", "SECRET1")
    db.session.add(teacher1)
    db.session.flush()
    user1 = _make_user_for_admin(teacher1)
    db.session.flush()

    # Create a student with no class/seat association (orphaned)
    salt = get_random_salt()
    profile = IdentityProfile(profile_type="student", first_name="OrphanedStudent", last_name="Z")
    db.session.add(profile)
    db.session.flush()
    orphaned_student = Student(
        identity_profile=profile,
        block="Z",
        salt=salt,
        first_half_hash=f"hash_orphan_{uuid4().hex[:8]}",
    )
    db.session.add(orphaned_student)
    db.session.commit()

    assert Student.query.filter_by(id=orphaned_student.id).first() is not None

    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        g.canonical_context = SimpleNamespace(
            user_id=user1.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )

        students = _scoped_students().all()

        assert len(students) == 0, \
            f"Teacher should see 0 students (orphaned student should not be visible), but saw {len(students)}"

        student_names = [s.display_first_name for s in students]
        assert "OrphanedStudent" not in student_names, \
            f"Orphaned student should not be visible to teacher, but was found in results: {student_names}"


def test_system_admin_flag_not_set_accidentally(client):
    """
    Test that a regular teacher login doesn't accidentally set is_system_admin.

    This is a CRITICAL security test. If is_system_admin is accidentally set to True
    for a regular teacher, they will see ALL students in the system.
    """
    teacher1 = make_admin(f"teacher1_sysadm_{uuid4().hex[:6]}", "SECRET1")
    teacher2 = make_admin(f"teacher2_sysadm_{uuid4().hex[:6]}", "SECRET2")
    db.session.add(teacher1)
    db.session.add(teacher2)
    db.session.flush()
    user1 = _make_user_for_admin(teacher1)
    user2 = _make_user_for_admin(teacher2)
    db.session.flush()

    class2 = create_class_scope(
        teacher=teacher2,
        teacher_user_id=user2.id,
        join_code=f"SYS2_{uuid4().hex[:4]}",
        block="B",
    )
    for i in range(200):
        _make_student_in_class(
            class2,
            first_name=f"StudentT2_{i}",
            join_code=class2.join_code,
            block="B",
            index=i,
        )

    db.session.commit()

    # Regular teacher sees only their own students (0)
    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        g.canonical_context = SimpleNamespace(
            user_id=user1.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )
        session.pop('is_system_admin', None)

        students = _scoped_students().all()

        assert len(students) == 0, \
            f"Regular teacher should see 0 students, but saw {len(students)}. " \
            f"This indicates is_system_admin might be set incorrectly!"

    # With sysadmin role, all students are visible
    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher1.id
        g.canonical_context = SimpleNamespace(
            user_id=user1.id,
            class_id=None,
            seat_id=None,
            actor_role='sysadmin',
        )
        session['is_system_admin'] = True

        students = _scoped_students().all()

        assert len(students) == 200, \
            f"With is_system_admin=True, should see all 200 students, but saw {len(students)}"


def test_orphaned_students_from_deleted_teacher(client):
    """
    CRITICAL BUG TEST: Test that students from a deleted teacher are not visible to a new teacher with the same ID.

    This test verifies that even if students remain "orphaned" (no ClassEconomy links),
    a new teacher who reuses that ID cannot see them unless they are explicitly linked via ClassEconomy.

    NOTE: Students are now linked to teachers via ClassEconomy (seat/class chain), not StudentTeacher alone.
    """
    # Step 1: Create teacher1, their User, and a class with students
    teacher1 = make_admin(f"teacher1_orphd_{uuid4().hex[:6]}", "SECRET1")
    db.session.add(teacher1)
    db.session.flush()
    user1 = _make_user_for_admin(teacher1)
    db.session.flush()
    teacher1_id = teacher1.id
    user1_id = user1.id

    class1 = create_class_scope(
        teacher=teacher1,
        teacher_user_id=user1_id,
        join_code=f"ORP1_{uuid4().hex[:4]}",
        block="O",
    )
    student_ids = []
    for i in range(5):
        student, _ = _make_student_in_class(
            class1,
            first_name=f"OldStudent_{i}",
            join_code=class1.join_code,
            block="O",
        )
        student_ids.append(student.id)

    db.session.commit()

    # Step 2: Delete teacher1 and their class
    ClassEconomy.query.filter_by(user_id=user1_id).delete()
    db.session.delete(teacher1)
    db.session.delete(user1)
    db.session.commit()

    # Step 3: Create a NEW teacher2 with their own User (no class at all)
    teacher2 = make_admin(f"teacher2_orphd_{uuid4().hex[:6]}", "SECRET2")
    db.session.add(teacher2)
    db.session.flush()
    user2 = _make_user_for_admin(teacher2)
    db.session.commit()

    # Step 4: teacher2 should NOT see any orphaned students
    with client.application.test_request_context():
        from flask import session
        from flask import g
        from types import SimpleNamespace

        session['is_admin'] = True
        session['admin_id'] = teacher2.id
        g.canonical_context = SimpleNamespace(
            user_id=user2.id,
            class_id=None,
            seat_id=None,
            actor_role='teacher',
        )

        students = _scoped_students().all()

        assert len(students) == 0, \
            f"Security Fix: New teacher should see 0 orphaned students, but saw {len(students)}."
