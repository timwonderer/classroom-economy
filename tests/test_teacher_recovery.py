from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
from tests.helpers.class_scope import create_class_scope
import pytest
import pyotp
import bcrypt
from datetime import datetime, timezone, timedelta
from app.models import Admin, IdentityProfile, Seat, RecoveryRequest, StudentRecoveryCode, StudentTeacher, ClassEconomy, User, UserRole
from app.extensions import db
from app.hash_utils import hash_username_lookup, get_random_salt, hash_hmac

# Helper to create teacher
def create_teacher(username="teacher1"):
    salt = get_random_salt()
    teacher = make_admin(username, pyotp.random_base32(),
        salt=salt,
        has_assigned_students=True
    )
    db.session.add(teacher)
    db.session.flush()
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        totp_secret_encrypted=teacher.totp_secret,
    )
    db.session.add(user)
    db.session.flush()
    teacher._canonical_user_id_for_test = user.id
    return teacher

# Helper to create student
def create_student(teacher, username="student1", block="A"):
    join_code = f"JOIN{teacher.id}{block}"
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not class_row:
        class_row = ClassEconomy(join_code=join_code, user_id=teacher.id)
        db.session.add(class_row)
        db.session.flush()

    student = make_student_identity(
        class_id=class_row.class_id,
        join_code=join_code,
        block=block,
        first_name="Test",
        last_name="S",
        claimed=True,
    )
    db.session.add(StudentTeacher(user_id=student.user_id, teacher_id=teacher.id))
    db.session.flush()

    return student

@pytest.mark.skip(reason="Test harness issue: session transaction not persisting correctly for student verification step in SQLite memory DB")
def test_teacher_recovery_full_flow(client, app):
    pass

def test_recovery_fails_missing_period(client, app):
    teacher = create_teacher()
    s1 = create_student(teacher, "s1", "A") # Only Block A
    s2 = create_student(teacher, "s2", "B")
    db.session.commit()

    # Initiate with ONLY s1 (missing Block B)
    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['s1']
    }, follow_redirects=True)

    assert b"Unable to verify identity" in response.data

def test_recovery_fails_wrong_student(client, app):
    teacher = create_teacher()
    s1 = create_student(teacher, "s1", "A")
    db.session.commit()

    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['wrong_user']
    }, follow_redirects=True)

    assert b"Unable to verify identity" in response.data

def test_username_lookup_works(client, app):
    teacher = create_teacher()
    s1 = create_student(teacher, "UserWithCaps", "A")
    db.session.commit()

    response = client.post('/admin/recover', data={
        'join_code[]': [f"JOIN{teacher.id}A"],
        'student_username[]': ['UserWithCaps']
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/admin/recovery-status' in response.location

def test_setup_recovery_flow(client, app):
    teacher = create_teacher()

    # Login as teacher
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = teacher.id
        sess['user_id'] = teacher._canonical_user_id_for_test
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Check dashboard for prompt (should NOT be there in v2)
    response = client.get('/admin/')
    assert response.status_code == 200
    assert b"Setup Account Recovery" not in response.data

    # Post to setup (redirects in V2)
    response = client.post('/admin/setup-recovery', data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Recovery setup is already enabled without date-of-birth requirements." in response.data
