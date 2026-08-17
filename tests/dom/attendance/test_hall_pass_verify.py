"""Public hall-pass verification route tests for the v2 PROD model."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session, record_hall_pass_log
from app.models import AttendanceReasonCode, HallPassSettings, User
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from app.utils.canonical_temporal_resolver import SYSTEM_LEVEL_EVALUATION, canonical_temporal_resolver
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _current_utc():
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
    ).canonical_now_utc


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _student_ctx(classroom, index: int = 0) -> CanonicalContext:
    student = classroom.students[index]
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _seed_hall_pass_settings(classroom) -> None:
    settings = HallPassSettings.query.filter_by(class_id=classroom.class_id).first()
    if settings:
        settings.queue_enabled = True
        settings.queue_limit = 50
        settings.pass_types = [
            {"name": "Bathroom", "simultaneous_limit": None, "enabled": True},
            {"name": "Office", "simultaneous_limit": None, "enabled": True},
        ]
    else:
        db.session.add(
            HallPassSettings(
                class_id=classroom.class_id,
                queue_enabled=True,
                queue_limit=50,
                pass_types=[
                    {"name": "Bathroom", "simultaneous_limit": None, "enabled": True},
                    {"name": "Office", "simultaneous_limit": None, "enabled": True},
                ],
            )
        )
    db.session.flush()


def _set_verify_token(classroom) -> str:
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"hall-pass-verify:token:{classroom.class_id}"):
        classroom.teacher_user.hall_pass_verify_token = User.generate_verify_token()
        db.session.flush()
    return classroom.teacher_user.hall_pass_verify_token


def _issue_hall_pass(
    classroom,
    *,
    student_index: int = 0,
    hall_pass_id: str,
    destination: str = "Bathroom",
    issued_at=None,
):
    student = classroom.students[student_index]
    correlation_id = f"corr-{hall_pass_id.lower()}"
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"bypass:{correlation_id}"):
        grant_hall_passes(
            student.seat,
            1,
            correlation_id=correlation_id,
        )

    return record_hall_pass_log(
        ctx=_teacher_ctx(classroom),
        requested_by_seat_id=student.seat.id,
        approved_by_seat_id=classroom.teacher_seat.id,
        destination=destination,
        reason="teacher_approved",
        idempotency_key=f"hall-pass-verify:{hall_pass_id}",
        reference_time_utc=issued_at or _current_utc(),
    ).hall_pass_log


def _mark_left(classroom, log, *, student_index: int = 0, at_time=None):
    return record_attendance_session(
        ctx=_student_ctx(classroom, student_index),
        target_seat_id=classroom.students[student_index].seat.id,
        actor_seat_id=classroom.students[student_index].seat.id,
        mechanism="self",
        status="inactive",
        reason=log.destination,
        reason_code=AttendanceReasonCode.HALL_PASS,
        hall_pass_id=log.hall_pass_id,
        idempotency_key=f"hall-pass-verify:left:{log.hall_pass_id}",
        reference_time_utc=at_time or _current_utc(),
    ).session


def _mark_returned(classroom, log, *, student_index: int = 0, at_time=None):
    return record_attendance_session(
        ctx=_student_ctx(classroom, student_index),
        target_seat_id=classroom.students[student_index].seat.id,
        actor_seat_id=classroom.students[student_index].seat.id,
        mechanism="self",
        status="active",
        reason="Return from hall pass",
        hall_pass_id=log.hall_pass_id,
        idempotency_key=f"hall-pass-verify:return:{log.hall_pass_id}",
        reference_time_utc=at_time or _current_utc(),
    ).session


@pytest.fixture
def verification_context(client):
    classroom = initialize("chemistry_p1", client.application)
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall-pass-verify:settings"):
        _seed_hall_pass_settings(classroom)
    token = _set_verify_token(classroom)
    return {
        "classroom": classroom,
        "teacher": classroom.teacher_user,
        "token": token,
    }


def _post_verify(client, token: str, classroom, *, first_name: str = "Ava", last_name: str = "Chen"):
    return client.post(
        f"/verify/hallpass/{token}",
        data={
            "class_id": classroom.class_id,
            "first_name": first_name,
            "last_name": last_name,
        },
    )


def test_DOM_PROD_002__get_verify_page_valid_token(client, verification_context):
    """GET with a valid token renders the verification form."""
    teacher = verification_context["teacher"]
    response = client.get(f"/verify/hallpass/{verification_context['token']}")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Hall Pass Verification" in html
    assert "Verify" in html
    assert f"teacher_id={teacher.id}" not in html


def test_DOM_PROD_002__get_verify_page_invalid_token(client):
    """GET with an invalid token returns a generic unavailable response."""
    response = client.get("/verify/hallpass/deadbeef1234deadbeef1234deadbeef1234deadbeef1234deadbeef1234dead")

    assert response.status_code == 404
    html = response.data.decode()
    assert "Verification page not available" in html
    assert "teacher_id" not in html.lower()


def test_DOM_PROD_002__get_verify_page_rejects_null_token_teacher(client):
    """Teacher records with null token must not be publicly reachable."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall-pass-verify:null-token"):
        classroom = initialize("biology_block_a", client.application)
        classroom.teacher_user.hall_pass_verify_token = None
        db.session.flush()

    response = client.get("/verify/hallpass/None")

    assert response.status_code == 404
    assert "Verification page not available" in response.data.decode()


def test_DOM_PROD_002__post_verify_no_match(client, verification_context):
    """POST with a name that does not match any pass returns no_match."""
    response = _post_verify(
        client,
        verification_context["token"],
        verification_context["classroom"],
        first_name="Nonexistent",
        last_name="Zimmer",
    )

    assert response.status_code == 200
    assert "No hall pass record found" in response.data.decode()


def test_DOM_PROD_002__post_verify_match_left(client, verification_context):
    """POST with a matching student who is currently out returns match with status."""
    classroom = verification_context["classroom"]
    now = _current_utc()
    log = _issue_hall_pass(
        classroom,
        hall_pass_id="HP-VERIFY-LEFT",
        issued_at=now - timedelta(minutes=15),
    )
    _mark_left(classroom, log, at_time=now - timedelta(minutes=9))

    response = _post_verify(client, verification_context["token"], classroom)

    assert response.status_code == 200
    html = response.data.decode()
    assert "Ava Chen" in html
    assert "Currently Out" in html
    assert "No hall pass record" not in html
    assert f"pass_id={log.id}" not in html
    assert f"/hall-pass/{log.id}" not in html


def test_DOM_PROD_002__post_verify_match_returned(client, verification_context):
    """POST matching a student who has returned shows returned status."""
    classroom = verification_context["classroom"]
    now = _current_utc()
    log = _issue_hall_pass(
        classroom,
        hall_pass_id="HP-VERIFY-RETURNED",
        destination="Office",
        issued_at=now - timedelta(minutes=30),
    )
    _mark_left(classroom, log, at_time=now - timedelta(minutes=25))
    _mark_returned(classroom, log, at_time=now - timedelta(minutes=10))

    response = _post_verify(client, verification_context["token"], classroom)

    assert response.status_code == 200
    html = response.data.decode()
    assert "Ava Chen" in html
    assert "Returned" in html


def test_DOM_PROD_002__post_verify_ambiguous(client):
    """POST matching multiple students returns ambiguous response."""
    classroom = initialize("duplicate_names", client.application)
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall-pass-verify:ambiguous-settings"):
        _seed_hall_pass_settings(classroom)
    token = _set_verify_token(classroom)
    now = _current_utc()

    first_log = _issue_hall_pass(
        classroom,
        student_index=0,
        hall_pass_id="HP-VERIFY-AMBIGUOUS-1",
        issued_at=now - timedelta(minutes=10),
    )
    second_log = _issue_hall_pass(
        classroom,
        student_index=1,
        hall_pass_id="HP-VERIFY-AMBIGUOUS-2",
        issued_at=now - timedelta(minutes=9),
    )
    _mark_left(classroom, first_log, student_index=0, at_time=now - timedelta(minutes=5))
    _mark_left(classroom, second_log, student_index=1, at_time=now - timedelta(minutes=4))

    response = _post_verify(client, token, classroom, first_name="Alex", last_name="Lee")

    assert response.status_code == 200
    html = response.data.decode()
    assert "Unable to uniquely verify" in html
    assert "Bathroom" not in html


def test_DOM_PROD_002__post_verify_no_history_shown(client, verification_context):
    """POST result must not expose a list of passes or internal pass IDs."""
    classroom = verification_context["classroom"]
    log = _issue_hall_pass(classroom, hall_pass_id="HP-VERIFY-NO-HISTORY")
    _mark_left(classroom, log)

    response = _post_verify(client, verification_context["token"], classroom)
    html = response.data.decode()

    assert "<table" not in html
    assert f"pass_id={log.id}" not in html
    assert f'"id": {log.id}' not in html


def test_DOM_PROD_002__post_verify_wrong_class_rejected(client, verification_context):
    """POST with a class_id that does not belong to this teacher returns no_match."""
    other_class = initialize("biology_block_a", client.application)
    response = _post_verify(client, verification_context["token"], other_class)

    assert response.status_code == 200
    assert "No hall pass record found" in response.data.decode()


def test_DOM_PROD_002__post_verify_old_pass_not_shown(client, verification_context):
    """Passes outside today's class-local window are not returned."""
    classroom = verification_context["classroom"]
    yesterday = _current_utc() - timedelta(days=1)
    log = _issue_hall_pass(
        classroom,
        hall_pass_id="HP-VERIFY-OLD",
        issued_at=yesterday,
    )
    _mark_left(classroom, log, at_time=yesterday + timedelta(minutes=5))

    response = _post_verify(client, verification_context["token"], classroom)

    assert response.status_code == 200
    assert "No hall pass record found" in response.data.decode()


def test_DOM_PROD_002__post_verify_finds_match_beyond_first_20_records(client, verification_context):
    """Matching search must not be truncated by an arbitrary fixed result window."""
    classroom = verification_context["classroom"]
    now = _current_utc()

    for i in range(25):
        log = _issue_hall_pass(
            classroom,
            student_index=1,
            hall_pass_id=f"HP-VERIFY-WINDOW-{i}",
            destination="Office",
            issued_at=now - timedelta(minutes=i),
        )
        _mark_left(classroom, log, student_index=1, at_time=now - timedelta(minutes=i))

    target_log = _issue_hall_pass(
        classroom,
        student_index=0,
        hall_pass_id="HP-VERIFY-WINDOW-TARGET",
        issued_at=now - timedelta(minutes=30),
    )
    _mark_left(classroom, target_log, student_index=0, at_time=now - timedelta(minutes=30))

    response = _post_verify(client, verification_context["token"], classroom)

    html = response.data.decode()
    assert response.status_code == 200
    assert "Ava Chen" in html
    assert "No hall pass record found" not in html


def test_DOM_PROD_002__post_verify_input_normalization(client, verification_context):
    """Mixed-case first name and last name should still match hashed seat names."""
    classroom = verification_context["classroom"]
    log = _issue_hall_pass(classroom, hall_pass_id="HP-VERIFY-NORMALIZED")
    _mark_left(classroom, log)

    response = _post_verify(
        client,
        verification_context["token"],
        classroom,
        first_name="  AVA  ",
        last_name=" chen ",
    )

    html = response.data.decode()
    assert response.status_code == 200
    assert "Ava Chen" in html
    assert "Currently Out" in html


def test_DOM_PROD_002__post_verify_malformed_last_name(client, verification_context):
    """POST with invalid or empty last_name returns no_match."""
    classroom = verification_context["classroom"]
    for bad_last_name in ["", "   "]:
        response = _post_verify(
            client,
            verification_context["token"],
            classroom,
            last_name=bad_last_name,
        )

        assert response.status_code == 200
        assert "No hall pass record found" in response.data.decode()


def test_DOM_PROD_002__rotate_token_requires_auth(client, verification_context):
    """Token rotation endpoint requires admin authentication."""
    response = client.post("/api/hall-pass/verify-token/rotate")
    assert response.status_code in [302, 401, 403]


def test_DOM_PROD_002__rotate_token_invalidates_old_token(client):
    """After rotation, old token returns unavailable and new token renders."""
    classroom = initialize_as_teacher("biology_block_a", client, client.application)
    old_token = _set_verify_token(classroom)

    response = client.post("/api/hall-pass/verify-token/rotate")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    new_token = data["token"]
    assert new_token != old_token

    old_response = client.get(f"/verify/hallpass/{old_token}")
    assert old_response.status_code == 404

    new_response = client.get(f"/verify/hallpass/{new_token}")
    assert new_response.status_code == 200


def test_DOM_PROD_002__token_not_derived_from_teacher_id(verification_context):
    """The public token must not be derived from the teacher's numeric ID."""
    teacher = verification_context["teacher"]
    token = verification_context["token"]

    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)
    assert token != str(teacher.id)
    assert token != hex(teacher.id)
    assert token != f"{teacher.id:064d}"
