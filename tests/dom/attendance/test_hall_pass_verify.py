"""
Tests for the new Hall Pass Public Verification endpoint.

Validates the privacy-respecting single-student verification per spec v1.0:
- Token-based access (not teacher_id)
- No roster exposure
- No multi-day history
- Today-only scoping
- Input normalization
- Correct outcomes (no_match, ambiguous, match)
- Rate limiting not tested here (requires integration harness)
"""

import pytest
from datetime import datetime, timezone, timedelta

from app import app, db
from app.feats.base import FEATContext
from app.models import User, HallPassLog
from tests.helpers.classroom_initializer import initialize


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hp_teacher(client):
    """Create a teacher with a hall pass verify token."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:teacher"):
        teacher = initialize("chemistry_p1").teacher_user
        teacher.hall_pass_verify_token = User.generate_verify_token()
        db.session.flush()
    return teacher


@pytest.fixture
def hp_class(client, hp_teacher):
    """Create a class for hp_teacher."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:class"):
        class_row = initialize("chemistry_p1", app)
        db.session.flush()
    return class_row


@pytest.fixture
def hp_student(client, hp_teacher, hp_class):
    """Create a student in hp_class."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:student"):
        student = hp_class.students[0].seat
        db.session.flush()
    return student


@pytest.fixture
def hp_pass_today(client, hp_student, hp_class):
    """Create a 'left' hall pass for today for Maria G."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:pass_today"):
        now = datetime.now(timezone.utc)
        log = HallPassLog(
            seat_id=hp_student.id,
            class_id=hp_class.class_id,
            reason="Bathroom",
            status="left",
            join_code="jc_chem3",
            period="Period3",
            request_time=now - timedelta(minutes=15),
            decision_time=now - timedelta(minutes=14),
            left_time=now - timedelta(minutes=9),
        )
        db.session.add(log)
        db.session.flush()
    return log


# ---------------------------------------------------------------------------
# GET: page rendering
# ---------------------------------------------------------------------------

def test_DOM_ATT_001__get_verify_page_valid_token(client, hp_teacher, hp_student):
    """GET with a valid token renders the verification form."""
    resp = client.get(f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Hall Pass Verification" in html
    assert "Verify" in html
    # Should not expose teacher_id as a query parameter or attribute
    assert f"teacher_id={hp_teacher.id}" not in html


def test_DOM_ATT_001__get_verify_page_invalid_token(client):
    """GET with an invalid token returns a generic unavailable response."""
    resp = client.get("/verify/hallpass/deadbeef1234deadbeef1234deadbeef1234deadbeef1234deadbeef1234dead")
    assert resp.status_code == 404
    html = resp.data.decode()
    assert "Verification page not available" in html
    # Must not expose any teacher info
    assert "teacher_id" not in html.lower()


def test_DOM_ATT_001__get_verify_page_rejects_null_token_teacher(client):
    """Teacher records with null token must not be publicly reachable."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:null_token"):
        teacher = initialize("ap_csp_p3").teacher_user
        teacher.hall_pass_verify_token = None
        db.session.flush()

    # URL token 'None' must not resolve to the null token row.
    resp = client.get("/verify/hallpass/None")
    assert resp.status_code == 404
    html = resp.data.decode()
    assert "Verification page not available" in html


# ---------------------------------------------------------------------------
# POST: verification outcomes
# ---------------------------------------------------------------------------

def test_DOM_ATT_001__post_verify_no_match(client, hp_teacher, hp_student, hp_class):
    """POST with a name that does not match any pass returns no_match."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Nonexistent",
            "last_name": "Zimmer",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_DOM_ATT_001__post_verify_match_left(client, hp_teacher, hp_student, hp_pass_today, hp_class):
    """POST with a matching student who is currently out returns match with status."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "Currently Out" in html
    assert "No hall pass record" not in html
    # Must not expose internal pass ID in URL-style patterns
    assert f"pass_id={hp_pass_today.id}" not in html
    assert f"/hall-pass/{hp_pass_today.id}" not in html


def test_DOM_ATT_001__post_verify_match_returned(client, hp_teacher, hp_student, hp_class):
    """POST matching a student who has returned shows returned status."""
    now = datetime.now(timezone.utc)
    log = HallPassLog(
        seat_id=hp_student.id,
        class_id=hp_student.class_id,
        reason="Office",
        status="returned",
        join_code="jc_chem3",
        period="Period3",
        request_time=now - timedelta(minutes=30),
        decision_time=now - timedelta(minutes=29),
        left_time=now - timedelta(minutes=25),
        return_time=now - timedelta(minutes=10),
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:return_log"):
        db.session.add(log)
        db.session.flush()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "Returned" in html


def test_DOM_ATT_001__post_verify_ambiguous(client, hp_teacher, hp_student, hp_class):
    """POST matching multiple students returns ambiguous response."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:ambiguous"):
        student2 = initialize("ap_csp_p3").students[0].seat
        now = datetime.now(timezone.utc)
        for s in [hp_student, student2]:
            db.session.add(HallPassLog(
                seat_id=s.id,
                class_id=hp_student.class_id,
                reason="Bathroom",
                status="left",
                join_code="jc_chem3",
                period="Period3",
                request_time=now - timedelta(minutes=10),
                decision_time=now - timedelta(minutes=9),
                left_time=now - timedelta(minutes=5),
            ))
        db.session.flush()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Unable to uniquely verify" in html
    # Must not show count, timestamps, or destinations
    assert "Bathroom" not in html


def test_DOM_ATT_001__post_verify_no_history_shown(client, hp_teacher, hp_student, hp_pass_today, hp_class):
    """POST result must not expose any list of passes or roster."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    html = resp.data.decode()
    # Should never expose a table of multiple passes
    assert "<table" not in html
    # Must not expose internal pass ID in URL or JSON
    assert f"pass_id={hp_pass_today.id}" not in html
    assert f'"id": {hp_pass_today.id}' not in html


def test_DOM_ATT_001__post_verify_wrong_class_rejected(client, hp_teacher, hp_student, hp_pass_today):
    """POST with a class_id that doesn't belong to this teacher returns no_match."""
    other_class = initialize("ap_csp_p3")
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": other_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_DOM_ATT_001__post_verify_old_pass_not_shown(client, hp_teacher, hp_student, hp_class):
    """Passes from yesterday are not returned by today-scoped query."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:old_pass"):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        old_log = HallPassLog(
            seat_id=hp_student.id,
            class_id=hp_student.class_id,
            reason="Bathroom",
            status="left",
            join_code="jc_chem3",
            period="Period3",
            request_time=yesterday,
            decision_time=yesterday + timedelta(minutes=1),
            left_time=yesterday + timedelta(minutes=5),
        )
        db.session.add(old_log)
        db.session.flush()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_DOM_ATT_001__post_verify_finds_match_beyond_first_20_records(client, hp_teacher, hp_student, hp_class):
    """Matching search must not be truncated by an arbitrary fixed result window."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="hall_pass_verify:result_window"):
        now = datetime.now(timezone.utc)

        # Insert many newer non-matching records for the same class/day.
        for i in range(25):
            other = initialize("ap_csp_p3").students[0].seat
            db.session.add(HallPassLog(
                seat_id=other.id,
                class_id=hp_student.class_id,
                reason="Office",
                status="left",
                join_code="jc_chem3",
                period="Period3",
                request_time=now - timedelta(minutes=i),
                decision_time=now - timedelta(minutes=i),
                left_time=now - timedelta(minutes=i),
            ))

        # Add the target match as an older same-day record.
        db.session.add(HallPassLog(
            seat_id=hp_student.id,
            class_id=hp_student.class_id,
            reason="Bathroom",
            status="left",
            join_code="jc_chem3",
            period="Period3",
            request_time=now - timedelta(hours=2),
            decision_time=now - timedelta(hours=2),
            left_time=now - timedelta(hours=2),
        ))
        db.session.flush()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "No hall pass record found" not in html


def test_DOM_ATT_001__post_verify_input_normalization(client, hp_teacher, hp_student, hp_pass_today, hp_class):
    """Input normalization: mixed-case first name and last name should still match."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "class_id": hp_class.class_id,
            "first_name": "  MARIA  ",
            "last_name": " garcia ",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "Currently Out" in html


def test_DOM_ATT_001__post_verify_malformed_last_name(client, hp_teacher, hp_student, hp_class):
    """POST with invalid or empty last_name returns no_match."""
    for bad_last_name in ["", "   "]:
        resp = client.post(
            f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
            data={
                "class_id": hp_class.class_id,
                "first_name": "Maria",
                "last_name": bad_last_name,
            },
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "No hall pass record found" in html, f"Expected no_match for last_name={bad_last_name!r}"


# ---------------------------------------------------------------------------
# Token rotation
# ---------------------------------------------------------------------------

def test_DOM_ATT_001__rotate_token_requires_auth(client, hp_teacher):
    """Token rotation endpoint requires admin authentication."""
    resp = client.post("/api/hall-pass/verify-token/rotate")
    assert resp.status_code in [302, 401, 403]


def test_DOM_ATT_001__rotate_token_invalidates_old_token(client, hp_teacher, hp_class):
    """After rotation, old token returns unavailable."""
    old_token = hp_teacher.hall_pass_verify_token

    initialize_as_teacher("chemistry_p1", client, client.application)

    resp = client.post("/api/hall-pass/verify-token/rotate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    new_token = data['token']
    assert new_token != old_token

    # Old token is now invalid
    resp_old = client.get(f"/verify/hallpass/{old_token}")
    assert resp_old.status_code == 404

    # New token works
    resp_new = client.get(f"/verify/hallpass/{new_token}")
    assert resp_new.status_code == 200


def test_DOM_ATT_001__token_not_derived_from_teacher_id(hp_teacher):
    """The token must not be derived from or equal to the teacher's numeric ID."""
    token = hp_teacher.hall_pass_verify_token
    # Token must be a 64-character hex string (256-bit random)
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)
    # Token must not equal the teacher_id in any simple encoding
    assert token != str(hp_teacher.id)
    assert token != hex(hp_teacher.id)
    assert token != f"{hp_teacher.id:064d}"
