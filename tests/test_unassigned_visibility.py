import pytest
from app import db
from app.models import Admin, Student, StudentTeacher
from hash_utils import get_random_salt
import pyotp
from flask import session
from app.auth import get_admin_student_query

def test_new_admin_cannot_see_unassigned_students(client):
    """
    Regression test for P0 leak: New admins should NOT see students who have
    teacher_id=None (unassigned) unless they are explicitly linked via StudentTeacher.
    """
    app = client.application
    # Create Teacher B
    teacher_b = Admin(username="teacher_b_leak", totp_secret=pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.commit()

    # Create Student B (Unassigned)
    salt = get_random_salt()
    student_b = Student(
        first_name="UnassignedStudent",
        last_initial="B",
        block="A",
        salt=salt,
        teacher_id=None, # UNASSIGNED
        first_half_hash="hash_unassigned",
        dob_sum=123,
        has_completed_setup=False
    )
    db.session.add(student_b)
    db.session.commit()

    # Link to Teacher B (Simulate proper ownership via StudentTeacher)
    link = StudentTeacher(student_id=student_b.id, admin_id=teacher_b.id)
    db.session.add(link)
    db.session.commit()

    # Create Teacher A (New teacher)
    teacher_a = Admin(username="teacher_a_leak", totp_secret=pyotp.random_base32())
    db.session.add(teacher_a)
    db.session.commit()

    # Simulate Teacher A context
    with app.test_request_context():
        session['is_admin'] = True
        session['admin_id'] = teacher_a.id

        # Default behavior (used by dashboard)
        query = get_admin_student_query(include_unassigned=True)
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
    teacher_b = Admin(username="teacher_b_owner", totp_secret=pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.commit()

    salt = get_random_salt()
    student_b = Student(
        first_name="OwnerTestStudent",
        last_initial="B",
        block="A",
        salt=salt,
        teacher_id=None, # UNASSIGNED
        first_half_hash="hash_owner",
        dob_sum=123,
        has_completed_setup=False
    )
    db.session.add(student_b)
    db.session.commit()

    link = StudentTeacher(student_id=student_b.id, admin_id=teacher_b.id)
    db.session.add(link)
    db.session.commit()

    # Simulate Teacher B context
    with app.test_request_context():
        session['is_admin'] = True
        session['admin_id'] = teacher_b.id

        query = get_admin_student_query(include_unassigned=True)
        results = query.all()

        assert len(results) == 1
        assert results[0].first_name == "OwnerTestStudent"
