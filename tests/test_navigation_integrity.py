import os
import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models import TeacherOnboarding, Student, StudentTeacher, Seat, IdentityProfile, User, UserRole
from app.hash_utils import get_random_salt, hash_username
from app.utils.auth_username import build_hashed_username_fields
from app.utils.economy_policy import replace_enabled_class_features
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import create_class_scope
from tests.helpers.navigation_traversal import NavigationTester

@pytest.fixture
def integrity_tester(client):
    return NavigationTester(
        client=client,
        max_depth=3, # Configurable if needed
        allowlist=["/admin", "/student", "/sysadmin", "/main"],
        blocklist=[
            "/logout",
            "/api",
            "/download",
            "/export",
            "/static",
            "/admin/banking",
        ]
    )

def test_teacher_navigation_integrity(client, integrity_tester):
    """Test full teacher navigation tree for 500s and mutations."""
    admin = make_admin("nav_teacher", "secret")
    db.session.add(admin)
    db.session.commit()
    teacher_user = User(user_role=UserRole.TEACHER, username_hash=admin.username_hash, username_lookup_hash=admin.username_lookup_hash)
    db.session.add(teacher_user)
    db.session.flush()
    admin.user_id = teacher_user.id

    onboarding = TeacherOnboarding(
        user_id=teacher_user.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc)
    )
    db.session.add(onboarding)
    
    class_row = create_class_scope(
        teacher=admin,
        join_code="NAVTECH1",
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=False
    )
    profile = IdentityProfile(profile_type='student', first_name="Nav", last_name="T")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=get_random_salt())
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    _tb_seat = Seat(user_id=teacher_user.id, class_id=class_row.class_id, join_code="NAVTECH1", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name="Nav", last_name="T"))
    replace_enabled_class_features(
        class_row.class_id,
        {"insurance", "banking", "rent", "hall_pass", "store"},
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = teacher_user.id
        sess['is_admin'] = True
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "NAVTECH1"

    # Begin traversal
    integrity_tester.traverse("/admin/")

def test_student_navigation_integrity(client, integrity_tester):
    """Test full student navigation tree for 500s and mutations."""
    teacher = make_admin("nav_teacher2", "secret")
    db.session.add(teacher)
    db.session.commit()
    teacher_user = User(user_role=UserRole.TEACHER, username_hash=teacher.username_hash, username_lookup_hash=teacher.username_lookup_hash)
    db.session.add(teacher_user)
    db.session.flush()
    teacher.user_id = teacher_user.id

    class_row = create_class_scope(
        teacher=teacher,
        join_code="NAVSTU1",
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=False
    )
    
    profile = IdentityProfile(profile_type='student', first_name="Nav", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=get_random_salt())
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    _salt, username_hash, username_lookup_hash = build_hashed_username_fields("nav_student")
    student_user = User(user_role=UserRole.STUDENT, username_hash=username_hash, username_lookup_hash=username_lookup_hash)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=class_row.class_id, join_code="NAVSTU1", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Nav", last_name="S"))
    db.session.add(seat)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = teacher_user.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "NAVSTU1"
        sess['seat_id'] = seat.id

    # Begin traversal
    integrity_tester.traverse("/student/dashboard")

def test_sysadmin_navigation_integrity(client, integrity_tester):
    """Test sysadmin navigation tree."""
    sysadmin = make_sysadmin("nav_sysadmin", "secret")
    db.session.add(sysadmin)
    db.session.commit()
    sysadmin_user = User(user_role=UserRole.SYSADMIN, username_hash=sysadmin.username_hash, username_lookup_hash=sysadmin.username_lookup_hash)
    db.session.add(sysadmin_user)
    db.session.flush()

    with client.session_transaction() as sess:
        sess['user_id'] = sysadmin_user.id
        sess['is_sysadmin'] = True

    # Begin traversal
    integrity_tester.traverse("/sysadmin/dashboard")
