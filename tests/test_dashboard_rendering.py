from datetime import datetime, timezone
import pytest
from app.models import Admin, Student, TeacherBlock, RentSettings, TeacherOnboarding
from app.extensions import db
from hash_utils import get_random_salt, hash_username
import os

def test_admin_dashboard_rendering(client):
    """Admin dashboard should render successfully with new layout."""
    admin = Admin(username="render_admin", totp_secret="secret")
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
    assert b'Admin Panel' in response.data

def test_student_dashboard_rendering(client):
    """Student dashboard should render successfully with new layout."""
    teacher = Admin(username="render_teacher", totp_secret="secret")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Render",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("render_student", salt),
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()

    seat = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name="Render",
        last_initial="S",
        last_name_hash_by_part=["hash"],
        dob_sum=2025,
        salt=os.urandom(16),
        first_half_hash="hash",
        join_code="RENDER1",
        student_id=student.id,
        is_claimed=True,
    )
    db.session.add(seat)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "RENDER1"

    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b'Token Hub' in response.data
