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

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
import unicodedata
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models import Admin, Student, StudentTeacher, HallPassLog, Seat, IdentityProfile, ClassEconomy
from app.hash_utils import get_random_salt, hash_username


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hp_teacher(client):
    """Create a teacher with a hall pass verify token."""
    teacher = make_admin("hpteacher", "hpsecret1")
    teacher.hall_pass_verify_token = Admin.generate_verify_token()
    db.session.add(teacher)
    db.session.commit()
    return teacher


@pytest.fixture
def hp_student(client, hp_teacher):
    """Create a student with a TeacherBlock and StudentTeacher link."""
    salt = get_random_salt()
    class_row = ClassEconomy(
        join_code="jc_chem3",
        teacher_id=hp_teacher.id,
        created_by_admin_id=hp_teacher.id,
        section="Period3",
        display_name="Period3",
    )
    db.session.add(class_row)
    db.session.flush()

    block = Seat(
        class_id=class_row.class_id,
        join_code="jc_chem3",
        block="Period3",
        block_identifier="Period3",
        role="student",
    )

    db.session.add(block)

    db.session.flush()

    profile = IdentityProfile(seat_id=block.id, profile_type='student_unclaimed', first_name="Maria", last_name="Garcia")
    student = Student(
        first_name="Maria",
        last_initial="G",
        identity_profile=profile,
        block="Period3",
        salt=salt,
        username_hash=hash_username("maria_g", salt),
    )
    db.session.add_all([profile, student])
    db.session.flush()

    block.student_id = student.id
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=hp_teacher.id))
    db.session.add(block)
    db.session.commit()
    return student


@pytest.fixture
def hp_pass_today(client, hp_student):
    """Create a 'left' hall pass for today for Maria G."""
    now = datetime.now(timezone.utc)
    log = HallPassLog(
        student_id=hp_student.id,
        class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
        reason="Bathroom",
        status="left",
        join_code="jc_chem3",
        period="Period3",
        request_time=now - timedelta(minutes=15),
        decision_time=now - timedelta(minutes=14),
        left_time=now - timedelta(minutes=9),
    )
    db.session.add(log)
    db.session.commit()
    return log


# ---------------------------------------------------------------------------
# GET: page rendering
# ---------------------------------------------------------------------------

def test_get_verify_page_valid_token(client, hp_teacher, hp_student):
    """GET with a valid token renders the verification form."""
    resp = client.get(f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Hall Pass Verification" in html
    assert "Verify" in html
    # Should not expose teacher_id as a query parameter or attribute
    assert f"teacher_id={hp_teacher.id}" not in html


def test_get_verify_page_invalid_token(client):
    """GET with an invalid token returns a generic unavailable response."""
    resp = client.get("/verify/hallpass/deadbeef1234deadbeef1234deadbeef1234deadbeef1234deadbeef1234dead")
    assert resp.status_code == 404
    html = resp.data.decode()
    assert "Verification page not available" in html
    # Must not expose any teacher info
    assert "teacher_id" not in html.lower()


def test_get_verify_page_rejects_null_token_teacher(client):
    """Teacher records with null token must not be publicly reachable."""
    teacher = make_admin("nulltoken_teacher", "hpsecret_null")
    teacher.hall_pass_verify_token = None
    db.session.add(teacher)
    db.session.commit()

    # URL token 'None' must not resolve to the null token row.
    resp = client.get("/verify/hallpass/None")
    assert resp.status_code == 404
    html = resp.data.decode()
    assert "Verification page not available" in html


def test_get_verify_page_no_id_in_url(client, hp_teacher):
    """The new verification URL must not contain any numeric teacher ID."""
    token = hp_teacher.hall_pass_verify_token
    assert token.isalnum() and not token.isdigit()
    # Old URL style must not be routed
    resp_old = client.get(f"/hall-pass/verification?teacher_id={hp_teacher.id}")
    assert resp_old.status_code == 404


# ---------------------------------------------------------------------------
# POST: verification outcomes
# ---------------------------------------------------------------------------

def test_post_verify_no_match(client, hp_teacher, hp_student):
    """POST with a name that does not match any pass returns no_match."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "Nonexistent",
            "last_name": "Zimmer",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_post_verify_match_left(client, hp_teacher, hp_student, hp_pass_today):
    """POST with a matching student who is currently out returns match with status."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
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


def test_post_verify_match_returned(client, hp_teacher, hp_student):
    """POST matching a student who has returned shows returned status."""
    now = datetime.now(timezone.utc)
    log = HallPassLog(
        student_id=hp_student.id,
        class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
        reason="Office",
        status="returned",
        join_code="jc_chem3",
        period="Period3",
        request_time=now - timedelta(minutes=30),
        decision_time=now - timedelta(minutes=29),
        left_time=now - timedelta(minutes=25),
        return_time=now - timedelta(minutes=10),
    )
    db.session.add(log)
    db.session.commit()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "Returned" in html


def test_post_verify_ambiguous(client, hp_teacher, hp_student):
    """POST matching multiple students returns ambiguous response."""
    salt2 = get_random_salt()
    student2 = Student(
        first_name="Maria",
        last_initial="G",
        identity_profile=IdentityProfile(profile_type="student", first_name="Maria", last_name="Garcia"),
        block="Period3",
        salt=salt2,
        username_hash=hash_username("maria_g_2", salt2),
    )
    db.session.add(student2)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student2.id, teacher_id=hp_teacher.id))

    now = datetime.now(timezone.utc)
    for s in [hp_student, student2]:
        db.session.add(HallPassLog(
            student_id=s.id,
            class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
            reason="Bathroom",
            status="left",
            join_code="jc_chem3",
            period="Period3",
            request_time=now - timedelta(minutes=10),
            decision_time=now - timedelta(minutes=9),
            left_time=now - timedelta(minutes=5),
        ))
    db.session.commit()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Unable to uniquely verify" in html
    # Must not show count, timestamps, or destinations
    assert "Bathroom" not in html


def test_post_verify_no_history_shown(client, hp_teacher, hp_student, hp_pass_today):
    """POST result must not expose any list of passes or roster."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
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


def test_post_verify_wrong_join_code_rejected(client, hp_teacher, hp_student, hp_pass_today):
    """POST with a join_code that doesn't belong to this teacher returns no_match."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_other_class",
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_post_verify_old_pass_not_shown(client, hp_teacher, hp_student):
    """Passes from yesterday are not returned by today-scoped query."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    old_log = HallPassLog(
        student_id=hp_student.id,
        class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
        reason="Bathroom",
        status="left",
        join_code="jc_chem3",
        period="Period3",
        request_time=yesterday,
        decision_time=yesterday + timedelta(minutes=1),
        left_time=yesterday + timedelta(minutes=5),
    )
    db.session.add(old_log)
    db.session.commit()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No hall pass record found" in html


def test_post_verify_finds_match_beyond_first_20_records(client, hp_teacher, hp_student):
    """Matching search must not be truncated by an arbitrary fixed result window."""
    now = datetime.now(timezone.utc)

    # Insert many newer non-matching records for the same class/day.
    for i in range(25):
        salt = get_random_salt()
        other = Student(
            first_name=f"Other{i}",
            last_initial="Z",
            identity_profile=IdentityProfile(
                profile_type="student",
                first_name=f"Other{i}",
                last_name="Zimmer",
            ),
            block="Period3",
            salt=salt,
            username_hash=hash_username(f"other_{i}", salt),
        )
        db.session.add(other)
        db.session.flush()
        db.session.add(StudentTeacher(student_id=other.id, teacher_id=hp_teacher.id))
        db.session.add(HallPassLog(
            student_id=other.id,
            class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
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
        student_id=hp_student.id,
        class_id=ClassEconomy.query.filter_by(join_code="jc_chem3").first().class_id,
        reason="Bathroom",
        status="left",
        join_code="jc_chem3",
        period="Period3",
        request_time=now - timedelta(hours=2),
        decision_time=now - timedelta(hours=2),
        left_time=now - timedelta(hours=2),
    ))
    db.session.commit()

    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "Maria",
            "last_name": "Garcia",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "No hall pass record found" not in html


def test_post_verify_input_normalization(client, hp_teacher, hp_student, hp_pass_today):
    """Input normalization: mixed-case first name and last name should still match."""
    resp = client.post(
        f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
        data={
            "join_code": "jc_chem3",
            "first_name": "  MARIA  ",
            "last_name": " garcia ",
        },
    )
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Maria Garcia" in html
    assert "Currently Out" in html


def test_post_verify_malformed_last_name(client, hp_teacher, hp_student):
    """POST with invalid or empty last_name returns no_match."""
    for bad_last_name in ["", "   "]:
        resp = client.post(
            f"/verify/hallpass/{hp_teacher.hall_pass_verify_token}",
            data={
                "join_code": "jc_chem3",
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

def test_rotate_token_requires_auth(client, hp_teacher):
    """Token rotation endpoint requires admin authentication."""
    resp = client.post("/api/hall-pass/verify-token/rotate")
    assert resp.status_code in [302, 401, 403]


def test_rotate_token_invalidates_old_token(client, hp_teacher):
    """After rotation, old token returns unavailable."""
    old_token = hp_teacher.hall_pass_verify_token

    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = hp_teacher.id

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


def test_token_not_derived_from_teacher_id(hp_teacher):
    """The token must not be derived from or equal to the teacher's numeric ID."""
    token = hp_teacher.hall_pass_verify_token
    # Token must be a 64-character hex string (256-bit random)
    assert len(token) == 64
    assert all(c in "0123456789abcdef" for c in token)
    # Token must not equal the teacher_id in any simple encoding
    assert token != str(hp_teacher.id)
    assert token != hex(hp_teacher.id)
    assert token != f"{hp_teacher.id:064d}"
