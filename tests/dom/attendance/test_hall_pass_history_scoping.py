"""
Tests for hall pass history API endpoint scoping.

Ensures that GET /api/hall-pass/history scopes results by the teacher's
active class context, preventing cross-class data leakage.
"""

from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, ClassEconomy, HallPassLog
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def _login_teacher(client, *, teacher, class_row: ClassEconomy) -> None:
    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher.id,
            class_id=class_row.class_id,
            seat_id=teacher_seat.id if teacher_seat else teacher.id,
            role="teacher",
        )


def test_hall_pass_history_requires_admin_login(client):
    """History endpoint requires an authenticated teacher session."""
    response = client.get("/api/hall-pass/history")
    assert response.status_code in [302, 401, 403]


def test_hall_pass_history_scoped_to_class(client):
    """Teacher logged into class A only sees class A hall pass history."""
    teacher = seed_canonical_admin("hp_hist_t1").user
    db.session.flush()

    class_a = create_class_scope(teacher_user=teacher, join_code="HPHISTA")
    class_b = create_class_scope(teacher_user=teacher, join_code="HPHISTB")
    db.session.flush()

    seat_a = make_student_identity(class_id=class_a.class_id, first_name="Alice", last_name="A")
    seat_b = make_student_identity(class_id=class_b.class_id, first_name="Bob", last_name="B")
    db.session.flush()

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

    _login_teacher(client, teacher=teacher, class_row=class_a)

    response = client.get("/api/hall-pass/history")
    assert response.status_code == 200

    json_data = response.get_json()
    assert json_data["status"] == "success"

    record_ids = [record.get("id") for record in json_data["records"]]
    assert pass_a.id in record_ids
    assert pass_b.id not in record_ids
