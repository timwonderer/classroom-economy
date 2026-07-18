from datetime import datetime, timezone
import pyotp

from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.canonical_session import set_canonical_context

from app import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, Seat
from tests.helpers.class_scope import create_class_scope, make_student_identity


def test_student_status_get_is_read_only_and_reconcile_is_explicit_mutation(client, monkeypatch):
    from app.routes import api as api_routes

    teacher = seed_canonical_admin("status_teacher", pyotp.random_base32()).user
    with FEATContext("FEAT-IDEN-001", idempotency_key="tap-flow:status:create-class"):
        class_row = create_class_scope(teacher_user=teacher, join_code="JOIN-STATUS", section="A")
        student_seat = make_student_identity(class_id=class_row.class_id, first_name="Status", last_name="R")
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_seat.user_id,
            class_id=class_row.class_id,
            seat_id=student_seat.id,
            role="student",
        )

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


def test_auto_tapout_helper_accepts_explicit_canonical_identifiers(client):
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    from app.models import PayrollSettings
    from uuid import uuid4

    with client.application.app_context():
        teacher = seed_canonical_admin("legacy_teacher", pyotp.random_base32()).user
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"tap-flow:no-op:{uuid4().hex}"):
            class_economy = ClassEconomy(
                join_code=f"TAPLEG{uuid4().hex[:6].upper()}",
                user_id=teacher.id,
                display_name="Legacy Class",
                section="A",
                status="active",
            )
            db.session.add(class_economy)
            db.session.flush()

            db.session.add(
                PayrollSettings(
                    class_id=class_economy.class_id,
                    block="A",
                    daily_limit_hours=0.001,
                    settings_mode="simple",
                )
            )
            student_seat = make_student_identity(class_id=class_economy.class_id, first_name="Legacy", last_name="T")
            db.session.flush()
            student_seat_id = student_seat.id
            class_id = class_economy.class_id

    check_and_auto_tapout_if_limit_reached(student_seat_id, class_id, commit=False)


def test_tap_route_rejects_invalid_action_and_period(client):
    teacher = seed_canonical_admin("tapflow-teacher", pyotp.random_base32()).user
    with FEATContext("FEAT-IDEN-001", idempotency_key="tap-flow:invalid-action:create-class"):
        class_row = create_class_scope(teacher_user=teacher, join_code="JOIN-A", section="A")
        student_seat = make_student_identity(class_id=class_row.class_id, first_name="Test", last_name="S", pin="0000")
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_seat.user_id,
            class_id=class_row.class_id,
            seat_id=student_seat.id,
            role="student",
        )

    resp = client.post("/api/tap", json={"period": "Z", "action": "tap_in", "pin": "0000"})
    assert resp.status_code == 400

    resp = client.post("/api/tap", json={"period": "A", "action": "jump", "pin": "0000"})
    assert resp.status_code == 400
