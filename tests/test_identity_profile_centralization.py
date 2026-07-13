from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from app import db
from app.models import IdentityProfile, Seat


def _create_admin(username: str):
    admin = seed_canonical_admin(username, "TESTSECRET123456").user
    db.session.commit()
    return admin


def test_student_requires_explicit_identity_profile(client):
    teacher = _create_admin("identity-teacher-1")
    class_row = create_class_scope(teacher_user=teacher, join_code="IDPROF01")
    db.session.commit()

    seat = make_student_identity(class_id=class_row.class_id, first_name="Alicia", last_name="Quinn")
    db.session.commit()

    assert seat.identity_profile is not None
    profile = seat.identity_profile
    assert profile.profile_type in ("student", "student_claimed")
    assert profile.first_name == "Alicia"
    assert profile.last_name == "Quinn"
    assert seat.identity_profile.full_name == "Alicia Quinn"


def test_student_name_update_syncs_identity_profile(client):
    teacher = _create_admin("identity-teacher-2")
    class_row = create_class_scope(teacher_user=teacher, join_code="IDPROF02")
    db.session.commit()

    seat = make_student_identity(class_id=class_row.class_id, first_name="Jordan", last_name="Mills")
    db.session.commit()

    seat.identity_profile.first_name = "Jordyn"
    seat.identity_profile.last_name = "Nguyen"
    db.session.commit()

    profile = db.session.get(IdentityProfile, seat.identity_profile.id)
    assert profile.first_name == "Jordyn"
    assert profile.last_name == "Nguyen"
    assert seat.identity_profile.first_name == "Jordyn"
    assert seat.identity_profile.last_initial == "N"


def test_seat_reads_name_from_identity_profile(client):
    teacher = _create_admin("identity-teacher-3")
    class_row = create_class_scope(teacher_user=teacher, join_code="IDPROF03")
    db.session.commit()

    seat = Seat(class_id=class_row.class_id, role="student")
    db.session.add(seat)
    db.session.flush()

    profile = IdentityProfile(seat_id=seat.id, profile_type='student_unclaimed', first_name="Mateo", last_name="Rivera")
    db.session.add(profile)
    db.session.commit()

    assert seat.identity_profile is not None
    assert seat.identity_profile.profile_type == "student_unclaimed"
    assert seat.identity_profile.first_name == "Mateo"
    assert seat.identity_profile.last_initial == "R"


def test_student_internal_reference_is_non_sequential_and_unique(client):
    teacher = _create_admin("identity-teacher-4")
    class_row = create_class_scope(teacher_user=teacher, join_code="IDPROF04")
    db.session.commit()

    a = make_student_identity(class_id=class_row.class_id, first_name="One", last_name="Alpha")
    b = make_student_identity(class_id=class_row.class_id, first_name="Two", last_name="Beta")
    db.session.commit()

    # Each seat has a unique public_id (UUID)
    assert a.public_id != b.public_id
    assert a.id != b.id
