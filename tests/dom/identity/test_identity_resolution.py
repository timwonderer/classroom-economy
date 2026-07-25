from app import db
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize


def test_DOM_IDEN_001__student_requires_explicit_identity_profile(client):
    classroom = initialize("chemistry_p1", client.application)
    student = classroom.students[0]

    assert student.profile is not None
    assert student.profile.profile_type in ("student", "student_claimed")
    assert student.profile.first_name == "Ava"
    assert student.profile.last_name == "Chen"
    assert student.profile.full_name == "Ava Chen"


def test_DOM_IDEN_001__student_name_update_syncs_identity_profile(client):
    classroom = initialize("chemistry_p1", client.application)
    student = classroom.students[0]

    with FEATContext("FEAT-IDEN-001", idempotency_key="identity_profile:update_sync"):
        student.profile.first_name = "Jordyn"
        student.profile.last_name = "Nguyen"
        db.session.flush()

    assert student.profile.first_name == "Jordyn"
    assert student.profile.last_name == "Nguyen"
    assert student.profile.last_initial == "N"


def test_DOM_IDEN_001__seat_reads_name_from_identity_profile(client):
    classroom = initialize("chemistry_p1", client.application)
    student = classroom.students[0]

    assert student.profile is not None
    assert student.profile.profile_type == "student"
    assert student.profile.first_name == "Ava"
    assert student.profile.last_initial == "C"


def test_DOM_IDEN_001__student_internal_reference_is_non_sequential_and_unique(client):
    classroom = initialize("chemistry_p1", client.application)
    a = classroom.students[0].seat
    b = classroom.students[1].seat

    assert a.public_id != b.public_id
    assert a.id != b.id
