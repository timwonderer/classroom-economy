"""
Tests for hall pass checkout and checkin API endpoints.

Ensures that students can check out and check in directly from the dashboard
without using the terminal, with proper limit enforcement.
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import Seat, ClassEconomy, HallPassLog, HallPassSettings
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def _login_student(client, *, seat: Seat) -> None:
    class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=seat.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )


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


@pytest.fixture
def hp_ctx(client):
    """Create teacher, class, settings, student seat, and an approved hall pass."""
    teacher = make_admin("hp_co_teacher1")
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="HPTEST1")
    db.session.flush()

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

    student_seat = make_student_identity(
        class_id=class_row.class_id, first_name="Alice", last_name="A"
    )
    db.session.flush()

    now = datetime.now(timezone.utc)
    hall_pass = HallPassLog(
        seat_id=student_seat.id,
        class_id=class_row.class_id,
        reason="Bathroom",
        status="approved",
        period="Period1",
        request_time=now - timedelta(minutes=10),
        decision_time=now - timedelta(minutes=5),
    )
    db.session.add(hall_pass)
    db.session.commit()

    return {
        "teacher": teacher,
        "class_row": class_row,
        "student_seat": student_seat,
        "hall_pass": hall_pass,
        "settings": settings,
    }


def test_checkout_requires_authentication(client, hp_ctx):
    """Checkout endpoint requires an authenticated student session."""
    hall_pass = hp_ctx["hall_pass"]

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code in [302, 401]


def test_checkout_with_approved_pass(client, hp_ctx):
    """Student with an approved pass can check out; status becomes 'left'."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    _login_student(client, seat=seat)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "Bathroom" in json_data["message"]

    db.session.refresh(hall_pass)
    assert hall_pass.status == "left"
    assert hall_pass.left_time is not None


def test_checkout_rejects_wrong_student(client, hp_ctx):
    """A different student cannot check out another student's pass."""
    hall_pass = hp_ctx["hall_pass"]
    class_row = hp_ctx["class_row"]

    other_seat = make_student_identity(
        class_id=class_row.class_id, first_name="Bob", last_name="B"
    )
    db.session.commit()

    _login_student(client, seat=other_seat)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert "unauthorized" in json_data["message"].lower()


def test_checkout_rejects_non_approved_pass(client, hp_ctx):
    """Checkout fails when the pass is in 'pending' (not approved) status."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    hall_pass.status = "pending"
    db.session.commit()

    _login_student(client, seat=seat)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert "not approved" in json_data["message"].lower()


def test_checkin_with_left_pass(client, hp_ctx):
    """Student currently out ('left') can check back in; status becomes 'returned'."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    now = datetime.now(timezone.utc)
    hall_pass.status = "left"
    hall_pass.left_time = now - timedelta(minutes=5)
    db.session.commit()

    _login_student(client, seat=seat)

    response = client.post(
        "/api/hall-pass/checkin",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "checked in" in json_data["message"].lower()

    db.session.refresh(hall_pass)
    assert hall_pass.status == "returned"
    assert hall_pass.return_time is not None


def test_checkin_rejects_non_left_pass(client, hp_ctx):
    """Checkin fails when the pass is 'approved' (student has not left yet)."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    assert hall_pass.status == "approved"

    _login_student(client, seat=seat)

    response = client.post(
        "/api/hall-pass/checkin",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert "not currently checked out" in json_data["message"].lower()


def test_checkout_blocked_by_simultaneous_limit(client, hp_ctx):
    """Checkout is blocked when the simultaneous limit for the pass type is reached."""
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]
    class_row = hp_ctx["class_row"]

    now = datetime.now(timezone.utc)
    for i in range(2):
        other_seat = make_student_identity(
            class_id=class_row.class_id,
            first_name=f"Other{i}",
            last_name="S",
        )
        db.session.flush()
        other_pass = HallPassLog(
            seat_id=other_seat.id,
            class_id=class_row.class_id,
            reason="Bathroom",
            status="left",
            period="Period1",
            request_time=now - timedelta(minutes=15),
            decision_time=now - timedelta(minutes=10),
            left_time=now - timedelta(minutes=5),
        )
        db.session.add(other_pass)
    db.session.commit()

    _login_student(client, seat=seat)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert "limit reached" in json_data["message"].lower()

    db.session.refresh(hall_pass)
    assert hall_pass.status == "approved"


def test_approve_does_not_generate_pass_number(client, hp_ctx):
    """Approving a hall pass does not return or create a pass_number field."""
    teacher = hp_ctx["teacher"]
    class_row = hp_ctx["class_row"]
    hall_pass = hp_ctx["hall_pass"]

    hall_pass.status = "pending"
    hall_pass.reason = "Office"
    hall_pass.decision_time = None
    db.session.commit()

    _login_teacher(client, teacher=teacher, class_row=class_row)

    response = client.post(
        f"/api/hall-pass/{hall_pass.id}/approve",
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert "pass_number" not in payload

    db.session.refresh(hall_pass)
    assert hall_pass.status == "approved"


def test_checkout_rejects_mismatched_class_context(client, hp_ctx):
    """Checkout fails when the student's active class context differs from the pass's class."""
    teacher = hp_ctx["teacher"]
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    class_b = create_class_scope(teacher_user=teacher, join_code="HPTEST2")
    db.session.flush()

    other_seat = make_student_identity(
        class_id=class_b.class_id, first_name="Alice", last_name="A"
    )
    other_seat.user_id = seat.user_id
    db.session.flush()
    db.session.commit()

    _login_student(client, seat=other_seat)

    response = client.post(
        "/api/hall-pass/checkout",
        json={"pass_id": hall_pass.id},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data["status"] == "error"


def test_cancel_rejects_mismatched_class_context(client, hp_ctx):
    """Cancel fails when the student's active class context differs from the pass's class."""
    teacher = hp_ctx["teacher"]
    seat = hp_ctx["student_seat"]
    hall_pass = hp_ctx["hall_pass"]

    hall_pass.status = "pending"
    hall_pass.decision_time = None

    class_b = create_class_scope(teacher_user=teacher, join_code="HPTEST3")
    db.session.flush()

    other_seat = make_student_identity(
        class_id=class_b.class_id, first_name="Alice", last_name="A"
    )
    other_seat.user_id = seat.user_id
    db.session.flush()
    db.session.commit()

    _login_student(client, seat=other_seat)

    response = client.post(
        f"/api/hall-pass/cancel/{hall_pass.id}",
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    json_data = response.get_json()
    assert json_data["status"] == "error"
