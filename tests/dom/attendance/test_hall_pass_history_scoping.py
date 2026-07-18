"""
Tests for hall pass history API endpoint scoping.

Ensures that GET /api/hall-pass/history scopes results by the teacher's
active class context, preventing cross-class data leakage.
"""

from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import HallPassLog
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def test_DOM_ATT_001__hall_pass_history_requires_admin_login(client):
    """History endpoint requires an authenticated teacher session."""
    response = client.get("/api/hall-pass/history")
    assert response.status_code in [302, 401, 403]


def test_DOM_ATT_001__hall_pass_history_scoped_to_class(client):
    """Teacher logged into class A only sees class A hall pass history."""
    class_a = initialize("chemistry_p1")
    class_b = initialize("ap_csp_p3")
    seat_a = class_a.students[0].seat
    seat_b = class_b.students[0].seat

    now = datetime.now(timezone.utc)
    with FEATContext("FEAT-ATTN-001", idempotency_key="hall_pass_history_scoping:seed"):
        pass_a = HallPassLog(
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            reason="Bathroom",
            status="returned",
            period="Period1",
            request_time=now - timedelta(hours=2),
            decision_time=now - timedelta(hours=2) + timedelta(minutes=5),
            left_time=now - timedelta(hours=2) + timedelta(minutes=10),
            return_time=now - timedelta(hours=2) + timedelta(minutes=15),
        )

        pass_b = HallPassLog(
            seat_id=seat_b.id,
            class_id=class_b.class_id,
            reason="Office",
            status="returned",
            period="Period2",
            request_time=now - timedelta(hours=1),
            decision_time=now - timedelta(hours=1) + timedelta(minutes=5),
            left_time=now - timedelta(hours=1) + timedelta(minutes=10),
            return_time=now - timedelta(hours=1) + timedelta(minutes=15),
        )

        db.session.add_all([pass_a, pass_b])
        db.session.flush()

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get("/api/hall-pass/history")
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data["status"] == "success"

    record_ids = [record.get("id") for record in json_data["records"]]
    assert pass_a.id in record_ids
    assert pass_b.id not in record_ids
