from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import User, UserRole, Admin, IdentityProfile, Student, Seat


def _create_admin(username: str) -> Admin:
    admin = make_admin(username, "TESTSECRET123456")
    db.session.add(admin)
    db.session.commit()
    return admin


def test_student_requires_explicit_identity_profile(client):
    salt = get_random_salt()
    profile = IdentityProfile(
        profile_type="student",
        first_name="Alicia",
        last_name="Quinn",
    )
    student = Student(
        identity_profile=profile,
        block="A",
        salt=salt,
        username_hash=hash_username("alicia", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.commit()

    assert student.identity_id is not None
    profile = db.session.get(IdentityProfile, student.identity_id)
    assert profile is not None
    assert profile.profile_type == "student"
    assert profile.first_name == "Alicia"
    assert profile.last_name == "Quinn"
    assert student.full_name == "Alicia Quinn"
    assert student.internal_db_id.startswith("sint_")
    assert student.internal_db_id != str(student.id)
    assert student.opaque_id.startswith("stu_")


def test_student_name_update_syncs_identity_profile(client):
    salt = get_random_salt()
    profile = IdentityProfile(
        profile_type="student",
        first_name="Jordan",
        last_name="Mills",
    )
    student = Student(
        identity_profile=profile,
        block="A",
        salt=salt,
        username_hash=hash_username("jordan", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.commit()

    student.identity_profile.first_name = "Jordyn"
    student.identity_profile.last_name = "Nguyen"
    db.session.commit()

    profile = db.session.get(IdentityProfile, student.identity_id)
    assert profile.first_name == "Jordyn"
    assert profile.last_name == "Nguyen"
    assert student.display_first_name == "Jordyn"
    assert student.display_last_initial == "N"
    assert student.display_last_name == "Nguyen"


def test_seat_reads_name_from_identity_profile(client):
    admin = _create_admin("identity-teacher")

    seat = Seat(join_code="JOIN-IDENTITY", block="A", block_identifier="A", role="student")

    db.session.add(seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_unclaimed', first_name="Mateo", last_name="Rivera"))
    db.session.add(seat)
    db.session.commit()

    assert seat.identity_id is not None
    profile = db.session.get(IdentityProfile, seat.identity_id)
    assert profile.profile_type == "student_unclaimed"
    assert seat.display_first_name == "Mateo"
    assert seat.display_last_initial == "R"
    assert seat.display_last_name == "Rivera"


def test_student_internal_reference_is_non_sequential_and_unique(client):
    salt_a = get_random_salt()
    salt_b = get_random_salt()
    profile_a = IdentityProfile(profile_type="student", first_name="One", last_name="Alpha")
    profile_b = IdentityProfile(profile_type="student", first_name="Two", last_name="Beta")
    a = Student(
        identity_profile=profile_a,
        block="A",
        salt=salt_a,
        username_hash=hash_username("one", salt_a),
        pin_hash="fake-hash",
    )
    b = Student(
        identity_profile=profile_b,
        block="B",
        salt=salt_b,
        username_hash=hash_username("two", salt_b),
        pin_hash="fake-hash",
    )
    db.session.add_all([a, b])
    db.session.commit()

    assert a.internal_reference.startswith("sint_")
    assert b.internal_reference.startswith("sint_")
    assert a.internal_reference != b.internal_reference
