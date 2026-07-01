from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app import db
from app.models import User, UserRole, Admin, IdentityProfile, Student, StudentTeacher
from app.hash_utils import get_random_salt
import pyotp
from flask import session
from app.routes.admin import _scoped_students

def test_new_admin_cannot_see_unassigned_students(client):
    """
    Regression test for P0 leak: New admins should NOT see students who have
    teacher_id=None (unassigned) unless they are explicitly linked via StudentTeacher.
    """
    app = client.application
    # Create Teacher B
    teacher_b = make_admin("teacher_b_leak", pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.commit()

    # Create Student B (Unassigned)
    salt = get_random_salt()
    profile_b = IdentityProfile(profile_type="student", first_name="UnassignedStudent", last_name="B")
    db.session.add(profile_b)
    db.session.flush()
    student_b = Student(
        identity_profile=profile_b,
        block="A",
        salt=salt,
        first_half_hash="hash_unassigned",
        has_completed_setup=False
    )
    db.session.add(student_b)
    db.session.commit()

    # Link to Teacher B (Simulate proper ownership via StudentTeacher)
    link = StudentTeacher(user_id=student_b_user.id, teacher_id=teacher_b.id)
    db.session.add(link)
    db.session.commit()

    # Create Teacher A (New teacher)
    teacher_a = make_admin("teacher_a_leak", pyotp.random_base32())
    db.session.add(teacher_a)
    db.session.commit()

    # Simulate Teacher A context
    with app.test_request_context():
        session['is_admin'] = True
        session['admin_id'] = teacher_a.id
        from flask import g
        from types import SimpleNamespace
        g.canonical_context = SimpleNamespace(user_id=teacher_a.id, class_id=None, seat_id=None)

        # Default behavior (used by dashboard)
        query = _scoped_students(include_unassigned=True)
        results = query.all()

        # Teacher A should see 0 students
        assert len(results) == 0, "Teacher A should not see unassigned students belonging to Teacher B"

def test_owner_can_see_unassigned_students_if_linked(client):
    """
    Verify that the owner (Teacher B) CAN still see the student because of the StudentTeacher link,
    even though teacher_id is None.
    """
    app = client.application
    # Setup fresh data for this test to avoid collision if run out of order
    teacher_b = make_admin("teacher_b_owner", pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.commit()

    salt = get_random_salt()
    profile_b = IdentityProfile(profile_type="student", first_name="OwnerTestStudent", last_name="B")
    db.session.add(profile_b)
    db.session.flush()
    student_b = Student(
        identity_profile=profile_b,
        block="A",
        salt=salt,
        first_half_hash="hash_owner",
        has_completed_setup=False
    )
    db.session.add(student_b)
    db.session.commit()

    link = StudentTeacher(user_id=student_b_user.id, teacher_id=teacher_b.id)
    db.session.add(link)
    db.session.commit()

    # Simulate Teacher B context
    with app.test_request_context():
        session['is_admin'] = True
        session['admin_id'] = teacher_b.id
        from flask import g
        from types import SimpleNamespace
        g.canonical_context = SimpleNamespace(user_id=teacher_b.id, class_id=None, seat_id=None)

        query = _scoped_students(include_unassigned=True)
        results = query.all()

        assert len(results) == 1
        assert results[0].display_first_name == "OwnerTestStudent"
