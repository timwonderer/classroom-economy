from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_teacher
import pytest
from app.models import User, UserRole, RentSettings, TeacherOnboarding, InsurancePolicy, Seat, IdentityProfile
from app.extensions import db
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher
import os


def test_admin_dashboard_rendering(client):
    """Admin dashboard should render successfully with new layout."""
    teacher = make_teacher("render_admin")
    db.session.flush()

    # Mark onboarding as completed so we don't get redirected
    onboarding = TeacherOnboarding(
        user_id=teacher.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc)
    )
    db.session.add(onboarding)
    db.session.commit()

    login_teacher(client, teacher)

    response = client.get('/admin/')
    assert response.status_code == 200
    assert b'Teacher Dashboard' in response.data


def test_student_dashboard_rendering(client):
    """Student dashboard should render successfully with new layout."""
    teacher = make_teacher("render_teacher")
    db.session.flush()

    class_row = create_class_scope(teacher_user=teacher, join_code="RENDER1")
    seat = make_student_identity(
        class_id=class_row.class_id,
        first_name="Render",
        last_name="S",
        claimed=True,
    )
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=seat.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b'Token Hub' in response.data
