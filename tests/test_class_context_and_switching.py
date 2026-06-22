from datetime import datetime, timezone

import pytest
from flask import session

from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from app.models import ClassEconomy, IdentityProfile, Seat, Student, User, UserRole


def _get_inject_class_context_processor(client):
    from app import app as flask_app
    for processor in flask_app.template_context_processors[None]:
        if processor.__name__ == "inject_class_context":
            return processor
    return None


@pytest.fixture
def setup_multi_class_student(client):
    teacher1 = User(user_role=UserRole.TEACHER, username_hash="teacher1_hash", username_lookup_hash="teacher1_lookup")
    teacher2 = User(user_role=UserRole.TEACHER, username_hash="teacher2_hash", username_lookup_hash="teacher2_lookup")
    teacher3 = User(user_role=UserRole.TEACHER, username_hash="teacher3_hash", username_lookup_hash="teacher3_lookup")
    db.session.add_all([teacher1, teacher2, teacher3])
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="MultiClass", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student_user = User(user_role=UserRole.STUDENT, username_hash="student_user_hash", username_lookup_hash="student_user_lookup")
    db.session.add(student_user)
    db.session.flush()

    salt = get_random_salt()
    student = Student(
        first_name="MultiClass",
        last_initial="S",
        identity_id=profile.id,
        block="A",
        salt=salt,
        username_hash=hash_username("multiclass_s", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.flush()

    class_1a = ClassEconomy(join_code="TEACHER1A", teacher_id=teacher1.id, display_name="Class 1A")
    class_2b = ClassEconomy(join_code="TEACHER2B", teacher_id=teacher2.id, display_name="Class 2B")
    class_3c = ClassEconomy(join_code="TEACHER3C", teacher_id=teacher3.id, display_name="Class 3C")
    class_unclaimed = ClassEconomy(join_code="UNCLAIMEDZ", teacher_id=teacher1.id, display_name="Unclaimed Z")
    db.session.add_all([class_1a, class_2b, class_3c, class_unclaimed])
    db.session.flush()

    seat1 = Seat(user_id=student_user.id, class_id=class_1a.class_id, join_code="TEACHER1A", block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    seat2 = Seat(user_id=student_user.id, class_id=class_2b.class_id, join_code="TEACHER2B", block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    seat3 = Seat(user_id=student_user.id, class_id=class_3c.class_id, join_code="TEACHER3C", block="C", block_identifier="C", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add_all([seat1, seat2, seat3])
    db.session.flush()
    profile.seat_id = seat1.id
    db.session.commit()

    return {
        "student": student,
        "seats": [seat1, seat2, seat3],
        "classes": {
            "TEACHER1A": class_1a,
            "TEACHER2B": class_2b,
            "TEACHER3C": class_3c,
            "UNCLAIMEDZ": class_unclaimed,
        },
    }


@pytest.fixture
def setup_single_class_student(client):
    teacher = User(user_role=UserRole.TEACHER, username_hash="single_teacher_hash", username_lookup_hash="single_teacher_lookup")
    db.session.add(teacher)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="SingleClass", last_name="X")
    db.session.add(profile)
    db.session.flush()
    student_user = User(user_role=UserRole.STUDENT, username_hash="single_student_user_hash", username_lookup_hash="single_student_user_lookup")
    db.session.add(student_user)
    db.session.flush()

    salt = get_random_salt()
    student = Student(
        first_name="SingleClass",
        last_initial="X",
        identity_id=profile.id,
        block="D",
        salt=salt,
        username_hash=hash_username("singleclass_x", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.flush()

    class_single = ClassEconomy(join_code="SINGLED", teacher_id=teacher.id, display_name="Single D")
    db.session.add(class_single)
    db.session.flush()

    seat = Seat(user_id=student_user.id, class_id=class_single.class_id, join_code="SINGLED", block="D", block_identifier="D", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id
    db.session.commit()

    return {"student": student, "seat": seat}


def test_inject_class_context_no_student(client):
    with client.application.test_request_context("/"):
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_inject_class_context_no_claimed_seats(client):
    profile = IdentityProfile(profile_type="student", first_name="NoSeats", last_name="N")
    db.session.add(profile)
    db.session.flush()
    student_user = User(user_role=UserRole.STUDENT, username_hash="noseats_user_hash", username_lookup_hash="noseats_user_lookup")
    db.session.add(student_user)
    db.session.flush()
    salt = get_random_salt()
    student = Student(
        first_name="NoSeats",
        last_initial="N",
        identity_id=profile.id,
        block="Z",
        salt=salt,
        username_hash=hash_username("noseats_n", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.commit()

    with client.application.test_request_context("/"):
        session["student_id"] = student.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_inject_class_context_requires_explicit_selection(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.application.test_request_context("/"):
        session["student_id"] = student.id
        session["user_id"] = setup_multi_class_student["seats"][0].user_id
        session["current_seat_id"] = setup_multi_class_student["seats"][0].id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert len(context["available_classes"]) == 3


def test_inject_class_context_uses_session_join_code(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    with client.application.test_request_context("/"):
        session["student_id"] = student.id
        session["current_class_id"] = class_row.class_id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert context["current_class_context"]["join_code"] == "TEACHER2B"
        assert context["current_class_context"]["block"] == "B"


def test_inject_class_context_available_classes_list(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    with client.application.test_request_context("/"):
        session["student_id"] = student.id
        session["current_class_id"] = class_row.class_id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert len(context["available_classes"]) == 3
        join_codes = [c["join_code"] for c in context["available_classes"]]
        assert {"TEACHER1A", "TEACHER2B", "TEACHER3C"} <= set(join_codes)
        current_classes = [c for c in context["available_classes"] if c["is_current"]]
        assert len(current_classes) == 1
        assert current_classes[0]["join_code"] == "TEACHER2B"


def test_inject_class_context_handles_missing_teacher(client, setup_single_class_student):
    student = setup_single_class_student["student"]
    with client.application.test_request_context("/"):
        session["student_id"] = student.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert len(context["available_classes"]) == 1


def test_inject_class_context_exception_handling(client):
    with client.application.test_request_context("/"):
        session["student_id"] = 2**31 - 1
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_switch_class_success(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_class_id"] = setup_multi_class_student["classes"]["TEACHER1A"].class_id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = client.post(f"/student/switch-class/{target_class_id}")
    assert response.status_code == 403


def test_switch_class_rejects_missing_runtime_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    Seat.query.delete()
    db.session.commit()

    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_class_id"] = setup_multi_class_student["classes"]["TEACHER1A"].class_id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = client.post(f"/student/switch-class/{target_class_id}")
    assert response.status_code == 403


def test_switch_class_unauthorized(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
    response = client.post("/student/switch-class/invalid-class-id")
    assert response.status_code == 403
    assert response.get_json()["status"] == "error"


def test_switch_class_not_logged_in(client):
    response = client.post("/student/switch-class/any-class-id")
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_switch_class_nonexistent_join_code(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
    response = client.post("/student/switch-class/not-a-real-class")
    assert response.status_code == 403


def test_switch_class_unclaimed_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    unclaimed_seat = Seat(student_id=student.id, class_id=setup_multi_class_student["classes"]["UNCLAIMEDZ"].class_id, join_code="UNCLAIMEDZ", block="Z", block_identifier="Z", role="student")
    db.session.add(unclaimed_seat)
    db.session.commit()
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
    response = client.post(f"/student/switch-class/{setup_multi_class_student['classes']['UNCLAIMEDZ'].class_id}")
    assert response.status_code == 403


def test_switch_class_proper_response_structure(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["current_seat_id"] = setup_multi_class_student["seats"][0].id
        sess["user_id"] = setup_multi_class_student["seats"][0].user_id
        sess["current_join_code"] = "TEACHER1A"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
    response = client.post(f"/student/switch-class/{setup_multi_class_student['classes']['TEACHER3C'].class_id}")
    assert response.status_code == 403


def test_switch_class_between_all_classes(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        sess["login_time"] = datetime.now(timezone.utc).isoformat()

    for join_code, block in [("TEACHER1A", "A"), ("TEACHER2B", "B"), ("TEACHER3C", "C"), ("TEACHER1A", "A")]:
        class_id = setup_multi_class_student["classes"][join_code].class_id
        response = client.post(f"/student/switch-class/{class_id}")
        assert response.status_code in (302, 403)
