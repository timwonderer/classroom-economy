from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app.models import Admin, Student, StudentTeacher, RentSettings, TeacherOnboarding, InsurancePolicy, Seat, IdentityProfile, User, UserRole
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope, make_student_seat
from tests.helpers.admin_context import login_admin
import os


def _bind_user_for_admin(admin):
    """Create or retrieve a User for the given Admin and link it."""
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    if not user:
        user = User(
            user_role=UserRole.TEACHER,
            username_hash=admin.username_hash,
            username_lookup_hash=admin.username_lookup_hash,
            totp_secret_encrypted=admin.totp_secret,
        )
        db.session.add(user)
        db.session.flush()
    admin.user_id = user.id
    db.session.flush()
    return user


def test_admin_dashboard_rendering(client):
    """Admin dashboard should render successfully with new layout."""
    admin = make_admin("render_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_user_for_admin(admin)
    db.session.commit()

    # Create a class so the admin has canonical context
    class_row = create_class_scope(
        teacher=admin,
        join_code="RENDER-ADMIN-1",
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=True,
        teacher_user_id=user.id,
    )
    db.session.commit()

    # Mark onboarding as completed so we don't get redirected
    onboarding = TeacherOnboarding(
        user_id=user.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc)
    )
    db.session.add(onboarding)
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    login_admin(
        client,
        admin.id,
        class_row.join_code,
        user_id=user.id,
        class_id=class_row.class_id,
        seat_id=teacher_seat.id if teacher_seat else None,
    )

    response = client.get('/admin/')
    assert response.status_code == 200
    assert b'Teacher Dashboard' in response.data


def test_insurance_upgrade_prompt_for_legacy_policies(client):
    """Dashboard shows insurance tier prompt when legacy policies are flagged."""
    admin = make_admin("legacy_insurance_admin", "secret")
    db.session.add(admin)
    db.session.flush()
    user = _bind_user_for_admin(admin)
    db.session.commit()

    # Create a class for canonical context
    class_row = create_class_scope(
        teacher=admin,
        join_code="LEGACY-INS-1",
        student=None,
        block="A",
        create_student_membership=False,
        create_seat=True,
        teacher_user_id=user.id,
    )
    db.session.flush()

    onboarding = TeacherOnboarding(
        user_id=user.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc),
        steps_completed={"needs_insurance_tier_upgrade": True},
    )
    db.session.add(onboarding)

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

    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    login_admin(
        client,
        admin.id,
        class_row.join_code,
        user_id=user.id,
        class_id=class_row.class_id,
        seat_id=teacher_seat.id if teacher_seat else None,
    )

    response = client.get('/admin/')

    assert response.status_code == 200
    assert b"Update insurance to the new tiered design" in response.data

def test_student_dashboard_rendering(client):
    """Student dashboard should render successfully with new layout."""
    teacher = make_admin("render_teacher", "secret")
    db.session.add(teacher)
    db.session.commit()

    class_row = create_class_scope(teacher=teacher, join_code="RENDER1", create_student_membership=False, create_seat=False, teacher_user_id=None)
    db.session.commit()

    seat = make_student_seat(
        class_id=class_row.class_id,
        join_code="RENDER1",
        block="A",
        claimed=True,
        first_name="Render",
        last_name="S",
    )
    db.session.commit()

    profile = db.session.query(IdentityProfile).filter_by(seat_id=seat.id).first()
    assert profile is not None

    salt = get_random_salt()
    student = Student(
        identity_profile=profile,
        block="A",
        salt=salt,
        username_hash=hash_username("render_student", salt),
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()

    user = db.session.get(User, seat.user_id)
    if user:
        user.current_session_nonce = user.current_session_nonce or "render-student-nonce"
        user.last_active_class_id = seat.class_id
        db.session.commit()

    with client.session_transaction() as sess:
        if user:
            sess['user_id'] = user.id
            sess['current_session_nonce'] = user.current_session_nonce
        sess['student_id'] = student.id
        sess['current_seat_id'] = seat.id
        sess['seat_id'] = seat.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['last_activity'] = sess['login_time']
        sess['current_join_code'] = "RENDER1"
        sess['current_class_id'] = seat.class_id
        sess['class_id'] = seat.class_id

    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b'Token Hub' in response.data
