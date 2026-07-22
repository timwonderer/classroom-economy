"""Tests for hall-pass history API class scoping."""

from __future__ import annotations

from datetime import datetime, timezone

from app.feats.base import FEATContext
from app.feats.prod import record_hall_pass_log
from app.models import HallPassSettings
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import grant_hall_passes
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _seed_hall_pass_settings(classroom) -> None:
    settings = HallPassSettings(
        class_id=classroom.class_id,
        queue_enabled=True,
        queue_limit=10,
        pass_types=[{"name": "Bathroom", "simultaneous_limit": None, "enabled": True}],
    )
    from app.extensions import db

    db.session.add(settings)
    db.session.flush()


def _issue_hall_pass(classroom, *, hall_pass_id: str, correlation_id: str):
    student = classroom.students[0]
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
        hall_pass_id=hall_pass_id,
        destination="Bathroom",
        reason="teacher_approved",
        idempotency_key=f"hall-pass-history:{hall_pass_id}",
        reference_time_utc=datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc),
    ).hall_pass_log


def test_DOM_PROD_002__hall_pass_history_requires_admin_login(client):
    """History endpoint requires an authenticated teacher session."""
    response = client.get("/api/hall-pass/history")
    assert response.status_code in [302, 401, 403]


def test_DOM_PROD_002__hall_pass_history_scoped_to_active_class(client):
    """Teacher logged into class A only sees class A hall-pass history."""
    class_a = initialize_as_teacher("chemistry_p1", client, client.application)
    class_b = initialize("biology_block_a", client.application)

    with FEATContext("FEAT-IDEN-001", idempotency_key="hall-pass-history:settings"):
        _seed_hall_pass_settings(class_a)
        _seed_hall_pass_settings(class_b)

    pass_a = _issue_hall_pass(
        class_a,
        hall_pass_id="HP-HISTORY-A",
        correlation_id="corr-hall-pass-history-a",
    )
    pass_b = _issue_hall_pass(
        class_b,
        hall_pass_id="HP-HISTORY-B",
        correlation_id="corr-hall-pass-history-b",
    )

    response = client.get("/api/hall-pass/history")
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data["status"] == "success"

    record_ids = [record.get("id") for record in json_data["records"]]
    assert pass_a.id in record_ids
    assert pass_b.id not in record_ids
