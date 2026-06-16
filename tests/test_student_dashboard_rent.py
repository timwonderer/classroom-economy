from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import os

from werkzeug.security import generate_password_hash

from app.models import Admin, Student, RentSettings, Seat, IdentityProfile
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username


def test_dashboard_handles_rent_with_multi_block_student(client):
    """Dashboard should render when rent is enabled for a multi-block student."""

    teacher = make_admin("rent_teacher", "rentsecret")
    db.session.add(teacher)
    db.session.commit()

    salt = get_random_salt()
    student = Student(
        first_name="Rent",
        last_initial="R",
        block="A,B",
        salt=salt,
        username_hash=hash_username("rent_student", salt),
        pin_hash=generate_password_hash("0000")
    )
    db.session.add(student)
    db.session.commit()

    seat_a = Seat(student_id=student.id, join_code="JOINA", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat_a)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat_a.id, profile_type='student_claimed', first_name="Rent", last_initial="R"))
    seat_b = Seat(student_id=student.id, join_code="JOINB", block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type='student_claimed', first_name="Rent", last_initial="R"))
    db.session.add_all([seat_a, seat_b])

    rent_settings = RentSettings(
        teacher_id=teacher.id,
        is_enabled=True,
        bill_preview_enabled=True,
        rent_amount=25.0,
    )
    db.session.add(rent_settings)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        # Ensure the dashboard context points at block B while the student has both A and B
        sess['current_join_code'] = "JOINB"

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    # Block state JSON should include only the current class context (block B) and not error on block A
    assert b'"B"' in response.data
