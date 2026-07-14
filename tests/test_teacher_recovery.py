from tests.helpers.v2_fixtures import make_sysadmin, seed_canonical_admin
from tests.helpers.class_scope import make_student_identity
from tests.helpers.class_scope import create_class_scope
from tests.helpers.admin_context import login_teacher
import pytest
import pyotp
import bcrypt
from datetime import datetime, timezone, timedelta
from app.models import IdentityProfile, Seat, RecoveryRequest, StudentRecoveryCode, ClassEconomy, User, UserRole
from app.extensions import db
from app.hash_utils import hash_username_lookup, get_random_salt, hash_hmac

# Helper to create teacher
def create_teacher(username="teacher1"):
    teacher = seed_canonical_admin(username).user
    db.session.flush()
    teacher._canonical_user_id_for_test = teacher.id
    return teacher

# Helper to create student
def create_student(teacher, username="student1", block="A"):
    join_code = f"JOIN{teacher.id}{block}"
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code)

    student = make_student_identity(
        class_id=class_row.class_id,
        first_name="Test",
        last_name="S",
        claimed=True,
        username=username,
    )
    db.session.flush()

    return student, class_row

def test_recovery_fails_missing_period(client, app):
    teacher = create_teacher()
    s1, class_a = create_student(teacher, "s1", "A") # Only Block A
    s2, class_b = create_student(teacher, "s2", "B")
    login_teacher(client, teacher, class_id=class_a.class_id)
    db.session.commit()

    # Initiate with ONLY s1 (missing Block B)
    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['s1']
    }, follow_redirects=True)

    assert b"Unable to verify identity" in response.data

def test_recovery_fails_wrong_student(client, app):
    teacher = create_teacher()
    s1, class_a = create_student(teacher, "s1", "A")
    login_teacher(client, teacher, class_id=class_a.class_id)
    db.session.commit()

    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['wrong_user']
    }, follow_redirects=True)

    assert b"Unable to verify identity" in response.data

def test_username_lookup_works(client, app):
    teacher = create_teacher()
    s1, class_a = create_student(teacher, "UserWithCaps", "A")
    login_teacher(client, teacher, class_id=class_a.class_id)
    db.session.commit()

    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['UserWithCaps']
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/admin/recovery-status' in response.location

def test_setup_recovery_flow(client, app):
    teacher = create_teacher()
    class_row = create_class_scope(teacher_user=teacher, join_code=f"JOIN{teacher.id}A")
    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    login_teacher(client, teacher, class_id=class_row.class_id, seat_id=teacher_seat.id if teacher_seat else None)

    # Login as teacher
    # Check dashboard for prompt (should NOT be there in v2)
    response = client.get('/admin/', follow_redirects=True)
    assert response.status_code == 200
    assert b"Setup Account Recovery" not in response.data
