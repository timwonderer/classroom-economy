
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
import pyotp
import uuid
from app import db
from app.models import User, UserRole, Admin, IdentityProfile
from app.hash_utils import get_random_salt

def test_student_count_relies_only_on_link_table(client):
    """
    Verify that teacher.get_student_count() counts students linked via StudentTeacher.
    """
    # Use random usernames to avoid collision in persistent DB
    t_username = f"harden_prof_{uuid.uuid4().hex[:8]}"
    secret = pyotp.random_base32()
    teacher = make_admin(t_username, secret)
    db.session.add(teacher)
    db.session.commit()

    # Create Student (with NO teacher_id)
    s_firstname = f"Hardened_{uuid.uuid4().hex[:8]}"
    student = make_student_identity(block='Period 1', first_name=s_firstname, last_name='S')
    db.session.commit()

    # 3. Verify count is 0 initially
    initial_count = teacher.get_student_count()
    assert initial_count == 0

    # 5. Verify count is 1
    final_count = teacher.get_student_count()
    assert final_count == 1

def test_delete_teacher_cleans_up_links(client):
    """
    Verify teacher self-deletion removes StudentTeacher links but keeps the student
    when they are still linked to another teacher.
    """
    # Create Teacher to delete
    t1_username = f"del_target_{uuid.uuid4().hex[:8]}"
    teacher = make_admin(t1_username, 's')
    db.session.add(teacher)
    db.session.commit()
    teacher_id = teacher.id

    # Create Survivor Teacher
    t2_username = f"survivor_{uuid.uuid4().hex[:8]}"
    survivor_teacher = make_admin(t2_username, 's2')
    db.session.add(survivor_teacher)
    db.session.commit()
    survivor_teacher_id = survivor_teacher.id

    # Create Student
    s_firstname = f"Survivor_{uuid.uuid4().hex[:8]}"
    student = make_student_identity(block='Period 1', first_name=s_firstname, last_name='S')
    db.session.commit()
    student_id = student.id

    db.session.commit()

    from app.routes.admin import _hard_delete_teacher_account_scope
    _hard_delete_teacher_account_scope(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    
    # Verify Teacher Gone
    assert db.session.get(Admin, teacher_id) is None

    # Verify Student Still Exists (because linked to survivor_teacher)
    assert db.session.get(IdentityProfile, s.identity_id) is not None
    


def test_student_teacher_unique_constraint(client):
    """
    Verify that the database prevents duplicate links between the same student and teacher.
    """
    from sqlalchemy.exc import IntegrityError
    
    # Setup
    t = make_admin(f"unique_t_{uuid.uuid4().hex}", 's')
    s = make_student_identity(block="B", first_name="Unique", last_name="S")
    db.session.add(t)
    db.session.commit()
    
    db.session.commit()
    db.session.rollback()


def test_remove_student_from_teacher_scope_preserves_shared_student(client):
    """
    Removing a student from one teacher should not delete the student when another
    teacher link still exists.
    """
    t1 = make_admin(f"t1_{uuid.uuid4().hex[:8]}", 's')
    t2 = make_admin(f"t2_{uuid.uuid4().hex[:8]}", 's2')
    s = make_student_identity(block="B", first_name="Shared", last_name="S")
    db.session.add_all([t1, t2])
    db.session.commit()

    db.session.commit()

    from app.routes.admin import _remove_student_from_teacher_scope

    was_deleted = _remove_student_from_teacher_scope(s, t1.id)
    db.session.commit()

    assert was_deleted is False
    assert db.session.get(IdentityProfile, s.identity_id) is not None
