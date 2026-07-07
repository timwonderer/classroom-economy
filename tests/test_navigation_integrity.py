import os
import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models import TeacherOnboarding, User, UserRole, Seat, IdentityProfile
from app.utils.economy_policy import replace_enabled_class_features
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import create_class_scope
from tests.helpers.class_scope import make_student_identity
from tests.helpers.navigation_traversal import NavigationTester
from tests.helpers.canonical_session import set_canonical_context

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
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=False
    )
    student = make_student_identity(block="A", first_name="Nav", last_name="T")
    student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
    if not student_user:
        student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
        db.session.add(student_user)
        db.session.flush()
    _tb_seat = Seat(user_id=student_user.id, class_id=class_row.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name="Nav", last_name="T"))
    replace_enabled_class_features(
        class_row.class_id,
        {"insurance", "banking", "rent", "hall_pass", "store"},
    )
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.user_id or admin.id,
            class_id=class_row.class_id,
            seat_id=Seat.query.filter_by(class_id=class_row.class_id, user_id=student_user.id).first().id,
            role="teacher",
        )
        sess['admin_id'] = admin.id

    # Begin traversal
    integrity_tester.traverse("/admin/")

def test_student_navigation_integrity(client, integrity_tester):
    """Test full student navigation tree for 500s and mutations."""
    teacher = make_admin("nav_teacher2", "secret")
    db.session.add(teacher)
    db.session.commit()

    class_row = create_class_scope(
        teacher=teacher,
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=False
    )
    
    student = make_student_identity(block="A", first_name="Nav", last_name="S")
    student_user = User.query.filter_by(username_hash=f"auto_{student.id}").first()
    if not student_user:
        student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
        db.session.add(student_user)
        db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=class_row.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Nav", last_name="S"))
    db.session.add(seat)
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

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
