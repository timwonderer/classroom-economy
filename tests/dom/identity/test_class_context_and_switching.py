from datetime import datetime, timezone

import pytest
from flask import session

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat, User, UserRole
from tests.helpers.classroom_initializer import initialize
from tests.helpers.canonical_classroom import login_student
from tests.dom.identity.helpers import student_switch_class


def _get_inject_class_context_processor(client):
    from app import app as flask_app
    for processor in flask_app.template_context_processors[None]:
        if processor.__name__ == "inject_class_context":
            return processor
    return None


def _set_user_active_context(user, class_id, seat_id):
    """Set canonical context pointers on User model for resolve_canonical_context()."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"test:set-context:{user.id}:{class_id}"):
        user.last_active_class_id = class_id
        user.last_active_seat_id = seat_id
        db.session.flush()


@pytest.fixture
def setup_multi_class_student(client):
    class_1a = initialize("chemistry_p1", client.application)
    class_2b = initialize("ap_csp_p3", client.application)
    class_3c = initialize("biology_block_a", client.application)
    class_unclaimed = initialize("duplicate_names", client.application)
    student = class_1a.students[0]
    seat1 = student.seat
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:multi-class-student-seats"):
        seat2 = Seat(user_id=student.user.id, class_id=class_2b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        seat3 = Seat(user_id=student.user.id, class_id=class_3c.class_id, role="student", claimed_at=datetime.now(timezone.utc))
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
    class_single = initialize("chemistry_p1", client.application)
    student = class_single.students[0]
    seat = student.seat

    return {"student": student, "seat": seat}


def test_DOM_IDEN_006__inject_class_context_no_student(client):
    with client.application.test_request_context("/"):
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_DOM_IDEN_006__inject_class_context_no_claimed_seats(client, setup_multi_class_student):
    user = setup_multi_class_student["student"].user
    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    target_seat_id = setup_multi_class_student["seats"][1].id
    _set_user_active_context(user, target_class_id, target_seat_id)

    with client.application.test_request_context("/"):
        session["user_id"] = user.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert context["current_class_context"]["join_code"] == setup_multi_class_student["classes"]["TEACHER2B"].join_code
        assert len(context["available_classes"]) == 1


def test_DOM_IDEN_006__inject_class_context_requires_explicit_selection(client, setup_multi_class_student):
    user = setup_multi_class_student["student"].user
    target_class_id = setup_multi_class_student["classes"]["TEACHER1A"].class_id
    target_seat_id = setup_multi_class_student["seats"][0].id
    _set_user_active_context(user, target_class_id, target_seat_id)

    with client.application.test_request_context("/"):
        session["user_id"] = user.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert len(context["available_classes"]) == 1


def test_DOM_IDEN_006__inject_class_context_uses_session_class_context(client, setup_multi_class_student):
    user = setup_multi_class_student["student"].user
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    target_seat_id = setup_multi_class_student["seats"][1].id
    _set_user_active_context(user, class_row.class_id, target_seat_id)

    with client.application.test_request_context("/"):
        session["user_id"] = user.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert context["current_class_context"]["join_code"] == class_row.join_code
        assert context["current_class_context"]["block"] == "Period 3"


def test_DOM_IDEN_006__inject_class_context_available_classes_list(client, setup_multi_class_student):
    user = setup_multi_class_student["student"].user
    class_row = setup_multi_class_student["classes"]["TEACHER2B"]
    target_seat_id = setup_multi_class_student["seats"][1].id
    _set_user_active_context(user, class_row.class_id, target_seat_id)

    with client.application.test_request_context("/"):
        session["user_id"] = user.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert len(context["available_classes"]) == 1
        class_aliases = [c["join_code"] for c in context["available_classes"]]
        assert class_aliases == [class_row.join_code]
        current_classes = [c for c in context["available_classes"] if c["is_current"]]
        assert len(current_classes) == 1
        assert current_classes[0]["join_code"] == class_row.join_code


def test_DOM_IDEN_006__inject_class_context_handles_missing_teacher(client, setup_single_class_student):
    user = db.session.get(User, setup_single_class_student["seat"].user_id)
    seat = setup_single_class_student["seat"]
    _set_user_active_context(user, seat.class_id, seat.id)

    with client.application.test_request_context("/"):
        session["user_id"] = user.id
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is not None
        assert len(context["available_classes"]) == 1


def test_DOM_IDEN_006__inject_class_context_exception_handling(client):
    with client.application.test_request_context("/"):
        session["user_id"] = 2**31 - 1
        ctx_processor = _get_inject_class_context_processor(client)
        context = ctx_processor()
        assert context["current_class_context"] is None
        assert context["available_classes"] == []


def test_DOM_IDEN_006__switch_class_success(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = student_switch_class(client, target_class_id)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["block"] == "Period 3"


def test_DOM_IDEN_006__switch_class_rejects_missing_runtime_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)
    Seat.query.delete()
    db.session.commit()

    target_class_id = setup_multi_class_student["classes"]["TEACHER2B"].class_id
    response = student_switch_class(client, target_class_id)
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_DOM_IDEN_006__switch_class_unauthorized(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)

    response = student_switch_class(client, "invalid-class-id")
    assert response.status_code == 403
    assert response.get_json()["status"] == "error"


def test_DOM_IDEN_006__switch_class_not_logged_in(client):
    response = student_switch_class(client, "any-class-id")
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_DOM_IDEN_006__switch_class_nonexistent_class_id(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)

    response = student_switch_class(client, "not-a-real-class")
    assert response.status_code == 403


def test_DOM_IDEN_006__switch_class_unclaimed_seat(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    with FEATContext("FEAT-IDEN-001", idempotency_key="test_switch_class_unclaimed_seat"):
        unclaimed_seat = Seat(user_id=student.user.id, class_id=setup_multi_class_student["classes"]["UNCLAIMEDZ"].class_id, role="student")
        db.session.add(unclaimed_seat)
        db.session.flush()
    login_student(client, student)

    response = student_switch_class(client, setup_multi_class_student["classes"]["UNCLAIMEDZ"].class_id)
    assert response.status_code == 403


def test_DOM_IDEN_006__switch_class_proper_response_structure(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)

    response = student_switch_class(client, setup_multi_class_student["classes"]["TEACHER3C"].class_id)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["teacher_name"] == "Teacher"
    assert payload["block"] == "Block A"


def test_DOM_IDEN_006__switch_class_between_all_classes(client, setup_multi_class_student):
    student = setup_multi_class_student["student"]
    login_student(client, student)

    for class_alias, expected_block in [("TEACHER1A", "Period 1"), ("TEACHER2B", "Period 3"), ("TEACHER3C", "Block A"), ("TEACHER1A", "Period 1")]:
        class_id = setup_multi_class_student["classes"][class_alias].class_id
        response = student_switch_class(client, class_id)
        assert response.status_code in (200, 302)
        if response.status_code == 200:
            payload = response.get_json()
            assert payload["status"] == "success"
            assert payload["block"] == expected_block
        else:
            assert "/student/login" in response.location
