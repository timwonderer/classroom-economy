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
    db.session.commit()

    onboarding = TeacherOnboarding(
        teacher_id=admin.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc)
    )
    db.session.add(onboarding)
    
    class_row = create_class_scope(
        teacher_user=admin,
    )
    student = make_student_identity(class_id=class_row.class_id, first_name="Nav", last_name="T", claimed=True)
    db.session.flush()
    _tb_seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_row.class_id, role="student").first()
    replace_enabled_class_features(
        class_row.class_id,
        {"insurance", "banking", "rent", "hall_pass", "store"},
    )
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_row.class_id,
            seat_id=_tb_seat.id,
            role="teacher",
        )
        sess['admin_id'] = admin.id

    # Begin traversal
    integrity_tester.traverse("/admin/")

def test_student_navigation_integrity(client, integrity_tester):
    """Test full student navigation tree for 500s and mutations."""
    teacher = make_admin("nav_teacher2", "secret")
    db.session.flush()
    db.session.commit()

    class_row = create_class_scope(teacher_user=teacher)
    student = make_student_identity(class_id=class_row.class_id, first_name="Nav", last_name="S", claimed=True)
    db.session.flush()
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_row.class_id, role="student").first()
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    # Begin traversal
    integrity_tester.traverse("/student/dashboard")

def test_sysadmin_navigation_integrity(client, integrity_tester):
    """Test sysadmin navigation tree."""
    sysadmin = make_sysadmin("nav_sysadmin", "secret")
    db.session.commit()

    with client.session_transaction() as sess:
        sess['sysadmin_id'] = sysadmin.id
        sess['is_sysadmin'] = True

    # Begin traversal
    integrity_tester.traverse("/sysadmin/dashboard")
