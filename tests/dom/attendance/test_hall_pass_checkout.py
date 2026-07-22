"""Route tests for v2 hall-pass leave/return attendance writes."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session, record_hall_pass_log
from app.models import AttendanceReasonCode, AttendanceSession, EntitlementEvent, HallPassLog, HallPassSettings
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from tests.helpers.classroom_initializer import initialize, login_student


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


@pytest.fixture
def hp_ctx(client):
    """Create a class, hall-pass settings, student seat, and issued hall pass."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall-pass-checkout:seed"):
        classroom = initialize("chemistry_p1", client.application)
        class_row = classroom.economy
        student = classroom.students[0]
        settings = HallPassSettings(
            class_id=class_row.class_id,
            queue_enabled=True,
            queue_limit=10,
            pass_types=[
                {"name": "Bathroom", "simultaneous_limit": 2, "enabled": True},
                {"name": "Office", "simultaneous_limit": None, "enabled": True},
            ],
        )
        db.session.add(settings)
        grant_hall_passes(
            student.seat,
            1,
            trigger_id="seed:hall-pass-checkout",
            correlation_id="corr-hall-pass-checkout-grant",
        )

    hall_pass = record_hall_pass_log(
        ctx=_teacher_ctx(classroom),
        requested_by_seat_id=student.seat.id,
        approved_by_seat_id=classroom.teacher_seat.id,
        destination="Bathroom",
        reason="teacher_approved",
        idempotency_key="hall-pass-checkout:issued-pass",
        reference_time_utc=datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc),
    ).hall_pass_log
    db.session.flush()
    consume_event = EntitlementEvent.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
        quantity_delta=-1,
        event_type="CONSUME",
    ).one()
    assert hall_pass.correlation_id == consume_event.correlation_id
    assert hall_pass.hall_pass_id == consume_event.entitlement_id

    return {
        "classroom": classroom,
        "class_row": class_row,
        "student": student,
        "student_seat": student.seat,
        "hall_pass": hall_pass,
        "settings": settings,
    }


def _latest_attendance_row(seat_id: int, class_id: str) -> AttendanceSession | None:
    return (
        AttendanceSession.query.filter_by(target_seat_id=seat_id, class_id=class_id)
        .order_by(AttendanceSession.timestamp.desc(), AttendanceSession.id.desc())
        .first()
    )


def test_DOM_PROD_002__checkout_requires_authentication(client, hp_ctx):
    """Checkout endpoint requires an authenticated student session."""
    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hp_ctx["hall_pass"].id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code in [302, 401]


def test_DOM_PROD_002__checkout_with_issued_pass_appends_inactive_attendance(client, hp_ctx):
    """Student checkout appends inactive/hall_pass; the issued pass row is immutable."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]
    original_timestamp = hall_pass.timestamp
    original_correlation_id = hall_pass.correlation_id

    login_student(client, hp_ctx["student"])

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["destination"] == "Bathroom"

    db.session.refresh(hall_pass)
    assert hall_pass.timestamp == original_timestamp
    assert hall_pass.correlation_id == original_correlation_id
    assert hall_pass.requested_by_seat_id == seat.id

    attendance_row = _latest_attendance_row(seat.id, hp_ctx["class_row"].class_id)
    assert attendance_row is not None
    assert attendance_row.target_seat_id == seat.id
    assert attendance_row.actor_seat_id == seat.id
    assert attendance_row.class_id == hp_ctx["class_row"].class_id
    assert attendance_row.mechanism == "self"
    assert attendance_row.status == "inactive"
    assert attendance_row.reason_code == AttendanceReasonCode.HALL_PASS.value
    assert attendance_row.hall_pass_id == hall_pass.hall_pass_id


def test_DOM_PROD_002__checkout_rejects_wrong_student(client, hp_ctx):
    """A different student cannot check out another student's issued pass."""
    hall_pass = hp_ctx["hall_pass"]
    other_student = hp_ctx["classroom"].students[1]

    login_student(client, other_student)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert "unauthorized" in json_data["message"].lower()


def test_DOM_PROD_002__checkout_rejects_pending_request_not_committed_as_pass(client, hp_ctx):
    """Pending hall-pass requests are ephemeral; no HallPassLog row means no checkout."""
    login_student(client, hp_ctx["student"])

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": 999999},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 404


def test_DOM_PROD_002__checkin_after_checkout_appends_active_attendance(client, hp_ctx):
    """Student return appends active/start_work after inactive/hall_pass."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    record_attendance_session(
        ctx=CanonicalContext(
            user_id=hp_ctx["student"].user.id,
            class_id=hp_ctx["class_row"].class_id,
            seat_id=seat.id,
            actor_role="student",
        ),
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        status="inactive",
        reason="Bathroom",
        reason_code=AttendanceReasonCode.HALL_PASS,
        hall_pass_id=hall_pass.hall_pass_id,
        idempotency_key="hall-pass-checkout:preexisting-leave",
        reference_time_utc=datetime(2026, 7, 19, 15, 5, tzinfo=timezone.utc),
    )

    login_student(client, hp_ctx["student"])

    response = client.post(
        "/api/hall-pass/checkin",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "checked in" in json_data["message"].lower()

    attendance_row = _latest_attendance_row(seat.id, hp_ctx["class_row"].class_id)
    assert attendance_row is not None
    assert attendance_row.target_seat_id == seat.id
    assert attendance_row.actor_seat_id == seat.id
    assert attendance_row.class_id == hp_ctx["class_row"].class_id
    assert attendance_row.mechanism == "self"
    assert attendance_row.status == "active"
    assert attendance_row.reason_code == AttendanceReasonCode.START_WORK.value


def test_DOM_PROD_002__checkin_is_idempotent_when_already_active(client, hp_ctx):
    """Checkin does not mutate HallPassLog and reports success if already active."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    record_attendance_session(
        ctx=CanonicalContext(
            user_id=hp_ctx["student"].user.id,
            class_id=hp_ctx["class_row"].class_id,
            seat_id=seat.id,
            actor_role="student",
        ),
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
        status="active",
        reason="Start work",
        idempotency_key="hall-pass-checkout:already-active",
        reference_time_utc=datetime(2026, 7, 19, 15, 10, tzinfo=timezone.utc),
    )
    row_count_before = AttendanceSession.query.filter_by(
        target_seat_id=seat.id,
        class_id=hp_ctx["class_row"].class_id,
    ).count()

    login_student(client, hp_ctx["student"])

    response = client.post(
        "/api/hall-pass/checkin",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "already checked in" in json_data["message"].lower()
    assert AttendanceSession.query.filter_by(
        target_seat_id=seat.id,
        class_id=hp_ctx["class_row"].class_id,
    ).count() == row_count_before


def test_DOM_PROD_002__issued_pass_reuses_consumed_entitlement_correlation(client, hp_ctx):
    """Hall-pass consumption uses the same correlation as the entitlement grant."""
    hall_pass = hp_ctx["hall_pass"]
    consume_event = EntitlementEvent.query.filter_by(
        seat_id=hp_ctx["student_seat"].id,
        class_id=hp_ctx["class_row"].class_id,
        quantity_delta=-1,
    ).one()

    assert hall_pass.correlation_id == "corr-hall-pass-checkout-grant"
    assert consume_event.correlation_id == hall_pass.correlation_id
    assert HallPassLog.query.filter_by(correlation_id=hall_pass.correlation_id).count() == 1
