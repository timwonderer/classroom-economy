import os
import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models import TeacherOnboarding, User, UserRole, Student, StudentTeacher, Seat, IdentityProfile
from app.hash_utils import get_random_salt, hash_username
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

    onboarding = TeacherOnboarding(
        teacher_id=admin.id,
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
    salt = get_random_salt()
    student = Student(
        first_name="Nav",
        last_initial="T",
        block="A",
        salt=salt,
        username_hash=hash_username("nav_teacher_student", salt),
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=admin.id))
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    _tb_seat = Seat(user_id=student_user.id, class_id=class_row.class_id, join_code="NAVTECH1", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name="Nav", last_initial="T"))
    replace_enabled_class_features(
        class_row.class_id,
        {"insurance", "banking", "rent", "hall_pass", "store"},
    )
    db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
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

    class_row = create_class_scope(
        teacher=teacher,
        join_code="NAVSTU1",
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=False
    )
    
    salt = get_random_salt()
    student = Student(
        first_name="Nav",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("nav_student", salt),
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.commit()

    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=class_row.class_id, join_code="NAVSTU1", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Nav", last_initial="S"))
    db.session.add(seat)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
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

    with client.session_transaction() as sess:
        sess['sysadmin_id'] = sysadmin.id
        sess['is_sysadmin'] = True

    # Begin traversal
    integrity_tester.traverse("/sysadmin/dashboard")
