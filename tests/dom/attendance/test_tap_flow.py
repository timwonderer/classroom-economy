from app import db
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize, initialize_as_student


def test_DOM_ATT_001__student_status_get_is_read_only_and_reconcile_is_explicit_mutation(client, monkeypatch):
    from app.routes import api as api_routes

    classroom, student = initialize_as_student("chemistry_p1", client, client.application)

    called = {"count": 0}

    def _fake_auto_tapout(*args, **kwargs):
        called["count"] += 1

    monkeypatch.setattr(api_routes, "check_and_auto_tapout_if_limit_reached", _fake_auto_tapout)

    get_resp = client.get("/api/student-status")
    assert get_resp.status_code == 200
    assert called["count"] == 0

    post_resp = client.post("/api/student-status/reconcile")
    assert post_resp.status_code == 200
    assert called["count"] == 1


def test_DOM_ATT_001__auto_tapout_helper_accepts_explicit_canonical_identifiers(client):
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    from app.models import PayrollSettings
    classroom = initialize("ap_csp_p3")
    student_seat_id = classroom.students[0].seat.id
    class_id = classroom.class_id

    check_and_auto_tapout_if_limit_reached(student_seat_id, class_id, commit=False)


def test_DOM_ATT_001__tap_route_rejects_invalid_action_and_period(client):
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    student_seat = student.seat

    resp = client.post("/api/tap", json={"period": "Z", "action": "tap_in", "pin": "0000"})
    assert resp.status_code == 400

    resp = client.post("/api/tap", json={"period": "A", "action": "jump", "pin": "0000"})
    assert resp.status_code == 400
