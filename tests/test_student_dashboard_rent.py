from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import os

from werkzeug.security import generate_password_hash

from app.models import User, UserRole, Admin, RentSettings, Seat, IdentityProfile
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.canonical_session import set_canonical_context


def test_dashboard_handles_rent_with_multi_block_student(client):
    """Dashboard should render when rent is enabled for a multi-block student."""

    teacher = make_admin("rent_teacher", "rentsecret")
    db.session.add(teacher)
    db.session.commit()

    student_user = User(
        username_hash="rent_student_hash",
        username_lookup_hash="rent_student_lookup",
        user_role=UserRole.STUDENT,
    )
    db.session.add(student_user)
    db.session.flush()
    profile = IdentityProfile(profile_type='student', first_name="Rent", last_name="R")
    db.session.add(profile)
    db.session.flush()
    seat_a = Seat(user_id=student_user.id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(seat_a)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat_a.id, profile_type='student_claimed', first_name="Rent", last_name="R"))
    seat_b = Seat(user_id=student_user.id, block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type='student_claimed', first_name="Rent", last_name="R"))
    profile.seat_id = seat_a.id

    rent_settings = RentSettings(is_enabled=True,
        bill_preview_enabled=True,
        rent_amount=25.0,
    )
    db.session.add(rent_settings)
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=seat_b.class_id,
            seat_id=seat_b.id,
            role="student",
        )

    response = client.get('/student/dashboard')

    assert response.status_code == 200
    # Block state JSON should include only the current class context (block B) and not error on block A
    assert b'"B"' in response.data
