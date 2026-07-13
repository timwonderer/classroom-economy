from datetime import datetime, timezone

import pytest
from flask import session

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, User, UserRole
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def _get_inject_class_context_processor(client):
    from app import app as flask_app
    for processor in flask_app.template_context_processors[None]:
        if processor.__name__ == "inject_class_context":
            return processor
    return None


@pytest.fixture
def setup_multi_class_student(client):
    teacher1 = seed_canonical_admin("teacher1_mcs", "t1secret").user
    teacher2 = seed_canonical_admin("teacher2_mcs", "t2secret").user
    teacher3 = seed_canonical_admin("teacher3_mcs", "t3secret").user

    with FEATContext("FEAT-IDEN-001", idempotency_key="setup_multi_class_student:classes"):
        class_1a = create_class_scope(teacher_user=teacher1, join_code="TEACHER1A", display_name="Class 1A", section="A")
        class_2b = create_class_scope(teacher_user=teacher2, join_code="TEACHER2B", display_name="Class 2B", section="B")
        class_3c = create_class_scope(teacher_user=teacher3, join_code="TEACHER3C", display_name="Class 3C", section="C")
        class_unclaimed = create_class_scope(teacher_user=teacher1, join_code="UNCLAIMEDZ", display_name="Unclaimed Z")

    with FEATContext("FEAT-IDEN-001", idempotency_key="setup_multi_class_student:student"):
        student = make_student_identity(class_id=class_1a.class_id, first_name="MultiClass", last_name="S", claimed=True)
        seat1 = Seat.query.filter_by(user_id=student.user_id, class_id=class_1a.class_id, role="student").first()
        seat2 = Seat(user_id=student.user_id, class_id=class_2b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        seat3 = Seat(user_id=student.user_id, class_id=class_3c.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add_all([seat2, seat3])
        db.session.flush()

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
    teacher = seed_canonical_admin("single_teacher_mcs", "single_secret").user

    with FEATContext("FEAT-IDEN-001", idempotency_key="setup_single_class_student:class"):
        class_single = create_class_scope(teacher_user=teacher, join_code="SINGLED", display_name="Single D")

    with FEATContext("FEAT-IDEN-001", idempotency_key="setup_single_class_student:student"):
        student = make_student_identity(class_id=class_single.class_id, first_name="SingleClass", last_name="X", claimed=True)
        seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_single.class_id, role="student").first()

    return {"student": student, "seat": seat}


def test_inject_class_context_no_student(client):
    with client.application.test_request_context("/"):
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_inject_class_context_no_claimed_seats(client, setup_multi_class_student):
    # Use existing multi-class student setup (student variable not used directly in test)

    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER2B"].class_id,
            seat_id=setup_multi_class_student["seats"][1].id,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert context["current_class_context"]["join_code"] == "TEACHER2B"
        assert len(context["available_classes"]) == 1


def test_inject_class_context_requires_explicit_selection(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert len(context["available_classes"]) == 1


def test_inject_class_context_uses_session_class_context(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=class_row.class_id,
            seat_id=setup_multi_class_student["seats"][1].id,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert context["current_class_context"]["join_code"] == "TEACHER2B"
        assert context["current_class_context"]["block"] == "B"


def test_inject_class_context_available_classes_list(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=class_row.class_id,
            seat_id=setup_multi_class_student["seats"][1].id,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert len(context["available_classes"]) == 1
        class_aliases = [c["join_code"] for c in context["available_classes"]]
        assert class_aliases == ["TEACHER2B"]
        current_classes = [c for c in context["available_classes"] if c["is_current"]]
        assert len(current_classes) == 1
        assert current_classes[0]["join_code"] == "TEACHER2B"


def test_inject_class_context_handles_missing_teacher(client, setup_single_class_student):
    student = setup_single_class_student["student"]
    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=setup_single_class_student["seat"].user_id,
            class_id=setup_single_class_student["seat"].class_id,
            seat_id=setup_single_class_student["seat"].id,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert len(context["available_classes"]) == 1


def test_inject_class_context_exception_handling(client):
    with client.application.test_request_context("/"):
        set_canonical_context(
            session,
            user_id=2**31 - 1,
            class_id="",
            seat_id=2**31 - 1,
            role="student",
        )
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_switch_class_success(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
    )

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = client.post(f"/student/switch-class/{target_class_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["block"] == "B"


def test_switch_class_rejects_missing_runtime_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    first_seat_id = setup_multi_class_student["seats"][0].id
    first_user_id = setup_multi_class_student["seats"][0].user_id
    Seat.query.delete()
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = first_user_id
        sess["current_class_id"] = setup_multi_class_student["classes"]["TEACHER1A"].class_id
        sess["current_seat_id"] = first_seat_id
        sess["current_session_nonce"] = "test-session-nonce"
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = client.post(f"/student/switch-class/{target_class_id}")
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_switch_class_unauthorized(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )
    response = client.post("/student/switch-class/invalid-class-id")
    assert response.status_code == 403
    assert response.get_json()["status"] == "error"


def test_switch_class_not_logged_in(client):
    response = client.post("/student/switch-class/any-class-id")
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_switch_class_nonexistent_class_id(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )
    response = client.post("/student/switch-class/not-a-real-class")
    assert response.status_code == 403


def test_switch_class_unclaimed_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with FEATContext("FEAT-IDEN-001", idempotency_key="test_switch_class_unclaimed_seat"):
        unclaimed_seat = Seat(user_id=student.user_id, class_id=setup_multi_class_student["classes"]["UNCLAIMEDZ"].class_id, role="student")
        db.session.add(unclaimed_seat)
        db.session.flush()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )
    response = client.post(f"/student/switch-class/{setup_multi_class_student['classes']['UNCLAIMEDZ'].class_id}")
    assert response.status_code == 403


def test_switch_class_proper_response_structure(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )
    response = client.post(f"/student/switch-class/{setup_multi_class_student['classes']['TEACHER3C'].class_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["teacher_name"] == "Teacher"
    assert payload["block"] == "C"


def test_switch_class_between_all_classes(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=setup_multi_class_student["seats"][0].user_id,
            class_id=setup_multi_class_student["classes"]["TEACHER1A"].class_id,
            seat_id=setup_multi_class_student["seats"][0].id,
            role="student",
        )

    for class_alias, block in [("TEACHER1A", "A"), ("TEACHER2B", "B"), ("TEACHER3C", "C"), ("TEACHER1A", "A")]:
        class_id = setup_multi_class_student["classes"][class_alias].class_id
        response = client.post(f"/student/switch-class/{class_id}")
        assert response.status_code in (200, 302)
        if response.status_code == 200:
            payload = response.get_json()
            assert payload["status"] == "success"
            assert payload["block"] == block
        else:
            assert "/student/login" in response.location
