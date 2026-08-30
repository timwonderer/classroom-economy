"""Identity domain Phase 8 verification: context processor view models and class switching.

Tests that the production context processors inject StudentLayoutContextView into
real HTTP responses, and that the class switching API route works correctly.

All tests use SPEC-TEST-001 canonical initializer. No synthetic context processor
invocations — every assertion is against a real HTTP response produced by production code.

Multi-class fixtures follow SPEC-TEST-001 §VIII: initialize() for base classroom,
provision_classroom() for additional classes, _provision_roster_seat() for proper
seat construction with IdentityProfile and claim hashes.
"""

import warnings

import pytest
from sqlalchemy.exc import SAWarning

from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, SYSTEM_LEVEL_EVALUATION
from tests.helpers.classroom_initializer import initialize, initialize_as_student, initialize_as_teacher
from tests.helpers.canonical_classroom import login_student, provision_classroom, _provision_roster_seat
from tests.helpers.canonical_identities import CLASSROOMS
from tests.dom.identity.helpers import student_switch_class


# ---------------------------------------------------------------------------
# Phase 8: View model injection verification via real HTTP responses
# ---------------------------------------------------------------------------


def test_student_dashboard_injects_layout_view(client, app):
    """Student dashboard HTML contains view model fields (not legacy variables)."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    response = client.get("/student/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    # View model fields should be rendered in the layout
    assert student.first_name.upper() in html
    # Legacy variable names must NOT appear as raw template output
    assert "student_display_first_name" not in html


def test_student_dashboard_contains_class_context(client, app):
    """Student dashboard renders class display name and join code from view model."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)
    response = client.get("/student/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    assert classroom.join_code in html


def test_teacher_dashboard_injects_admin_layout_view(client, app):
    """Teacher dashboard HTML contains admin view model fields."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        response = client.get("/admin/")
    assert response.status_code == 200
    html = response.data.decode()
    # Admin layout view should have class join code rendered
    assert classroom.join_code in html


def test_student_no_session_gets_empty_view(client, app):
    """Unauthenticated student request redirects (no crash from empty view model)."""
    initialize("chemistry_p1", app)  # provision DB but no session
    response = client.get("/student/dashboard")
    # Should redirect to login, not crash
    assert response.status_code == 302
    assert "/student/login" in response.location


# ---------------------------------------------------------------------------
# Helpers: cross-class seat binding via production code
# ---------------------------------------------------------------------------


def _bind_user_to_class_seat(user, classroom, classroom_key, roster_row_index=0):
    """Bind an existing User to a new seat in another class via production helpers.

    Creates a proper Seat with IdentityProfile, claim hashes, and roster
    fingerprint via _provision_roster_seat, then binds the user to it.
    """
    roster_row = CLASSROOMS[classroom_key]["roster"][roster_row_index]
    seat = _provision_roster_seat(classroom.class_id, roster_row)
    seat.user_id = user.id
    seat.claimed_at = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="current_time",
    ).canonical_now_utc
    db.session.flush()
    return seat


# ---------------------------------------------------------------------------
# Class switching API tests (production route, canonical fixtures)
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_class_student(client, app):
    """Student enrolled in 3 classes per SPEC-TEST-001 §VIII.

    Uses initialize() for base classroom, provision_classroom() for additional
    classes, and _provision_roster_seat() for proper seat construction with
    IdentityProfile and claim hashes.
    """
    classroom_a = initialize("chemistry_p1", app)
    classroom_b = provision_classroom("ap_csp_p3")
    classroom_c = provision_classroom("biology_block_a")

    student = classroom_a.students[0]
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:multi-class-seats"):
        _bind_user_to_class_seat(student.user, classroom_b, "ap_csp_p3")
        _bind_user_to_class_seat(student.user, classroom_c, "biology_block_a")

    login_student(client, student)
    return {
        "student": student,
        "classrooms": {
            "A": classroom_a,
            "B": classroom_b,
            "C": classroom_c,
        },
    }


def test_switch_class_success(client, app, multi_class_student):
    target_class_id = multi_class_student["classrooms"]["B"].class_id
    response = student_switch_class(client, target_class_id)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"


def test_switch_class_unauthorized_class(client, app, multi_class_student):
    response = student_switch_class(client, "invalid-class-id")
    assert response.status_code == 403
    assert response.get_json()["status"] == "error"


def test_switch_class_not_logged_in(client, app):
    initialize("chemistry_p1", app)
    response = student_switch_class(client, "any-class-id")
    assert response.status_code == 302
    assert "/student/login" in response.location


def test_switch_class_nonexistent_class_id(client, app, multi_class_student):
    response = student_switch_class(client, "not-a-real-class")
    assert response.status_code == 403


def test_switch_class_unclaimed_seat(client, app, multi_class_student):
    """Switching to a class where the seat is not claimed should be rejected."""
    unclaimed_classroom = provision_classroom("duplicate_names")
    student = multi_class_student["student"]
    with FEATContext("FEAT-IDEN-001", idempotency_key="test:unclaimed-seat"):
        roster_row = CLASSROOMS["duplicate_names"]["roster"][0]
        unclaimed_seat = _provision_roster_seat(unclaimed_classroom.class_id, roster_row)
        unclaimed_seat.user_id = student.user.id
        db.session.flush()

    response = student_switch_class(client, unclaimed_classroom.class_id)
    assert response.status_code == 403


def test_switch_class_between_all_classes(client, app, multi_class_student):
    """Switching between all enrolled classes works in sequence."""
    classrooms = multi_class_student["classrooms"]
    for key in ["A", "B", "C", "A"]:
        class_id = classrooms[key].class_id
        response = student_switch_class(client, class_id)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "success"


def test_switch_class_rejects_missing_runtime_seat(client, app, multi_class_student):
    """If all seats are deleted, switching should fail."""
    student = multi_class_student["student"]
    Seat.query.filter_by(user_id=student.user.id).delete(synchronize_session=False)
    db.session.flush()
    # Bulk delete with synchronize_session=False leaves stale Seat/User objects in
    # the identity map. A real production switch is a fresh request with a fresh
    # session, so it would observe the committed post-delete state (including the
    # ON DELETE SET NULL cascade that nulls users.last_active_seat_id). Expire the
    # identity map so this in-process request sees that same truth; otherwise the
    # auth boundary reads a phantom cached seat and never exercises fail-closed
    # resolution (INV-ARC-008 no-seat-fallback / INV-ARC-013 membership-by-existence).
    db.session.expire_all()

    target_class_id = multi_class_student["classrooms"]["B"].class_id
    response = student_switch_class(client, target_class_id)
    assert response.status_code == 302
    assert "/student/login" in response.location
