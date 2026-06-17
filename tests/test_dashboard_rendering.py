from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app.models import Admin, Student, StudentTeacher, RentSettings, TeacherOnboarding, InsurancePolicy, Seat, IdentityProfile
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope
import os

def test_admin_dashboard_rendering(client):
    """Admin dashboard should render successfully with new layout."""
    admin = make_admin("render_admin", "secret")
    db.session.add(admin)
    db.session.commit()

    # Mark onboarding as completed so we don't get redirected
    onboarding = TeacherOnboarding(
        teacher_id=admin.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc)
    )
    db.session.add(onboarding)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        sess['is_admin'] = True
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    response = client.get('/admin/')
    assert response.status_code == 200
    assert response.status_code == 200
    assert b'Teacher Dashboard' in response.data


def test_insurance_upgrade_prompt_for_legacy_policies(client):
    """Dashboard shows insurance tier prompt when legacy policies are flagged."""
    admin = make_admin("legacy_insurance_admin", "secret")
    db.session.add(admin)
    db.session.commit()

    onboarding = TeacherOnboarding(
        teacher_id=admin.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc),
        steps_completed={"needs_insurance_tier_upgrade": True},
    )
    db.session.add(onboarding)

    class_row = create_class_scope(teacher=admin, join_code="LEGACY-INS-1", student=None, block="A", create_student_membership=False, create_seat=False)
    db.session.flush()

    policy = InsurancePolicy(
        policy_code="LEGACY001",
        teacher_id=admin.id,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        title="Legacy Plan",
        description="Old structure",
        premium=5.0,
    )
    db.session.add(policy)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['admin_id'] = admin.id
        sess['is_admin'] = True
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    response = client.get('/admin/')

    assert response.status_code == 200
    assert b"Update insurance to the new tiered design" in response.data

def test_student_dashboard_rendering(client):
    """Student dashboard should render successfully with new layout."""
    teacher = make_admin("render_teacher", "secret")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Render",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("render_student", salt),
    )
    db.session.add(student)
    db.session.flush()
    # Create StudentTeacher link instead of deprecated teacher_id
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    seat = Seat(student_id=student.id, join_code="RENDER1", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Render", last_initial="S"))
    db.session.add(seat)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "RENDER1"

    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b'Token Hub' in response.data
