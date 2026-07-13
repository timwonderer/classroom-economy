"""
Tests for the student account recovery flow (DOM-IDEN-002 v2.1).

Recovery flow:
  Step 1 — Teacher generates a reset code → written to User.reset_code /
            reset_code_generated_at / reset_code_expires_at
  Step 2 — Student submits ONLY the reset_code at /recovery/lookup
            (no join_code required). Backend finds User by reset_code,
            clears credentials and reset fields, sets onboarding session.
  Step 3 — Student creates a new username at /student/create-username
  Step 4 — Student sets new PIN + passphrase at /student/setup-pin-passphrase
            (atomically updates User credentials, nulls reset fields)

`seat.user_id IS NOT NULL` is the sole indicator that a student has claimed.
`user.pin_hash IS NOT NULL` means credentials are set.
No `has_completed_setup` flag. No recovery fields on IdentityProfile.
"""
import re
import pytest
from datetime import timedelta

from app import db
from app.models import Seat, IdentityProfile, User, UserRole, Transaction
from app.utils.money_guard import check_financial_cooldown
from app.utils.time import ensure_utc, utc_now
from app.feats.base import FEATContext
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.admin_context import login_teacher
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def recovery_data(client):
    """Set up a teacher, class, and a claimed student for recovery tests."""
    teacher = seed_canonical_admin("teacher_rec").user
    db.session.flush()

    join_code = "A123"
    class_row = create_class_scope(
        teacher_user=teacher,
        join_code=join_code,
        display_name="Recovery Class",
    )
    db.session.flush()

    seat = make_student_identity(
        class_id=class_row.class_id,
        first_name="Original",
        last_name="Student",
        username="orig_student",
        pin="1111",
        claimed=True,
    )
    db.session.flush()

    user = db.session.get(User, seat.user_id)

    return {
        "teacher": teacher,
        "user": user,
        "seat": seat,
        "join_code": join_code,
        "class_id": class_row.class_id,
    }


# ------------------------------------------------------------------
# Step 1 — Teacher Initiates Reset
# ------------------------------------------------------------------

def test_teacher_generates_reset_code(client, recovery_data):
    """Teacher posts to generate-code -> reset_code written to User."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    login_teacher(client, teacher, class_id=recovery_data["class_id"])

    resp = client.post(
        f"/recovery/admin/generate-code/{seat.id}",
        follow_redirects=False,
    )
    # Redirects back to student detail on success
    assert resp.status_code == 302

    linked_user = db.session.get(User, seat.user_id)
    assert linked_user is not None
    assert linked_user.reset_code is not None
    assert len(linked_user.reset_code) == 8
    assert ensure_utc(linked_user.reset_code_expires_at) > utc_now()


def test_multiple_resets_invalidate_prior_codes(client, recovery_data):
    """Multiple reset requests overwrite the previous reset code."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    login_teacher(client, teacher, class_id=recovery_data["class_id"])

    client.post(f"/recovery/admin/generate-code/{seat.id}")
    linked_user = db.session.get(User, seat.user_id)
    db.session.refresh(linked_user)
    first_code = linked_user.reset_code

    client.post(f"/recovery/admin/generate-code/{seat.id}")
    db.session.refresh(linked_user)
    second_code = linked_user.reset_code

    assert first_code != second_code
    assert linked_user.reset_code_expires_at is not None


# ------------------------------------------------------------------
# Step 2 — Student Submits Reset Code
# ------------------------------------------------------------------

def test_student_lookup_success(client, recovery_data):
    """Valid reset_code -> credentials cleared, redirect to create-username."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_success"):
        db.session.flush()

    resp = client.post("/recovery/lookup", data={
        "reset_code": "RESET123",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    with client.session_transaction() as sess:
        assert sess.get("onboarding_seat_ref") is not None
        assert sess.get("onboarding_user_ref") is not None

    # Credentials cleared; reset fields nulled
    db.session.refresh(user)
    assert user.pin_hash is None
    assert user.passphrase_hash is None
    assert user.reset_code is None
    assert user.reset_code_expires_at is None


def test_student_lookup_expired_code(client, recovery_data):
    """Expired reset_code -> generic error."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now() - timedelta(minutes=20)
    user.reset_code_expires_at = utc_now() - timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_expired_code"):
        db.session.flush()

    resp = client.post("/recovery/lookup", data={
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_nonexistent_code(client, recovery_data):
    """Completely invalid code -> generic error, no identity revealed."""
    resp = client.post("/recovery/lookup", data={
        "reset_code": "NOTEXIST",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_recovery_does_not_create_new_user_row(client, recovery_data):
    """Recovering an account must not create a new User row."""
    user = recovery_data["user"]
    original_user_count = User.query.filter_by(user_role=UserRole.STUDENT).count()

    user.reset_code = "ROWTEST1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_does_not_create_new_user_row"):
        db.session.flush()

    client.post("/recovery/lookup", data={
        "reset_code": "ROWTEST1",
    }, follow_redirects=True)

    assert User.query.filter_by(user_role=UserRole.STUDENT).count() == original_user_count


def test_recovery_preserves_seat_binding(client, recovery_data):
    """Recovery lookup must not disturb seat.user_id binding."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "KEEPCLM1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_seat_binding"):
        db.session.flush()

    client.post("/recovery/lookup", data={
        "reset_code": "KEEPCLM1",
    }, follow_redirects=False)

    db.session.refresh(seat)
    assert seat.user_id == user.id
    assert seat.claimed_at is not None


def test_recovery_preserves_identity(client, recovery_data):
    """Recovery lookup preserves IdentityProfile first_name/last_name."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "IDTEST01"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_identity"):
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    client.post("/recovery/lookup", data={
        "reset_code": "IDTEST01",
    }, follow_redirects=True)

    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert profile is not None
    assert profile.first_name == "Original"


# ------------------------------------------------------------------
# Economic Invariance
# ------------------------------------------------------------------

def test_recovery_preserves_balance_and_transactions(client, recovery_data):
    """Transaction count unchanged through recovery lookup."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]
    join_code = recovery_data["join_code"]

    tx = Transaction(
        user_id=user.id,
        seat_id=seat.id,
        class_id=recovery_data["class_id"],
        amount=200.0,
        type="deposit",
        description="Initial deposit",
        account_type="checking",
        join_code=join_code,
    )
    with FEATContext("FEAT-LED-001", idempotency_key="recovery:preserve_transactions"):
        db.session.add(tx)
        db.session.flush()

    tx_count_before = Transaction.query.filter_by(seat_id=seat.id, class_id=recovery_data["class_id"]).count()

    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:reset_code_preserve"):
        user.reset_code = "PRESRV01"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    client.post("/recovery/lookup", data={
        "reset_code": "PRESRV01",
    }, follow_redirects=True)

    tx_count_after = Transaction.query.filter_by(seat_id=seat.id, class_id=recovery_data["class_id"]).count()
    assert tx_count_after == tx_count_before


# ------------------------------------------------------------------
# Reset Code Security
# ------------------------------------------------------------------

def test_reset_code_invalid_after_credential_setup(client, recovery_data):
    """Reset code is consumed and nulled after setup_pin_passphrase completes."""
    user = recovery_data["user"]
    join_code = recovery_data["join_code"]

    user.reset_code = "ONETIME1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    user.pin_hash = None
    user.passphrase_hash = None
    user.username_lookup_hash = None
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_reset_code_invalid_after_setup"):
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=recovery_data["class_id"],
            seat_id=recovery_data["seat"].id,
            role="student",
        )

    client.post("/recovery/lookup", data={"reset_code": "ONETIME1"}, follow_redirects=True)
    client.post("/student/create-username", data={"write_in_word": "planet"}, follow_redirects=True)
    client.post("/student/setup-pin-passphrase", data={
        "pin": "1234", "confirm_pin": "1234",
        "passphrase": "updated-passphrase", "confirm_passphrase": "updated-passphrase",
    }, follow_redirects=True)

    db.session.refresh(user)
    assert user.reset_code is None
    assert user.reset_code_expires_at is None
    assert user.pin_hash is not None

    # Attempt reuse
    resp = client.post("/recovery/lookup", data={"reset_code": "ONETIME1"}, follow_redirects=True)
    assert b"Invalid or expired recovery code" in resp.data


def test_only_one_active_reset_code_per_user(client, recovery_data):
    """Generating a second reset code overwrites the first on the User row."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]
    user = recovery_data["user"]

    login_teacher(client, teacher, class_id=recovery_data["class_id"])

    client.post(f"/recovery/admin/generate-code/{seat.id}")
    db.session.refresh(user)
    first_code = user.reset_code

    client.post(f"/recovery/admin/generate-code/{seat.id}")
    db.session.refresh(user)

    assert user.reset_code != first_code
    # Only one reset_code column on User — no way for both to coexist
    users_with_first = User.query.filter_by(reset_code=first_code).count()
    assert users_with_first == 0


# ------------------------------------------------------------------
# Edge Cases
# ------------------------------------------------------------------

def test_interrupting_reclaim_after_lookup(client, recovery_data):
    """After lookup, credentials cleared; identity profile preserved."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]
    join_code = recovery_data["join_code"]

    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:midflow_guard"):
        user.reset_code = "MIDFLOW1"
        user.reset_code_generated_at = utc_now()
        user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
        user.pin_hash = None
        user.passphrase_hash = None
        db.session.flush()

    resp = client.post("/recovery/lookup", data={"reset_code": "MIDFLOW1"}, follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(user)
    db.session.refresh(seat)

    # Seat binding preserved
    assert seat.user_id == user.id
    # Credentials cleared
    assert user.pin_hash is None
    assert user.passphrase_hash is None
    # Identity profile intact
    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert profile is not None
    assert profile.first_name == "Original"


def test_recovery_username_uses_random_segment(client, recovery_data, monkeypatch):
    """Recovery username generation stores value in session."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "RAND4001"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    user.pin_hash = None
    user.passphrase_hash = None
    user.username_lookup_hash = None
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_username_random_segment"):
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=recovery_data["class_id"],
            seat_id=seat.id,
            role="student",
        )

    client.post("/recovery/lookup", data={"reset_code": "RAND4001"}, follow_redirects=False)

    monkeypatch.setattr("app.routes.student.random.randint", lambda _a, _b: 4242)

    resp = client.post("/student/create-username", data={"write_in_word": "galaxy"}, follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        generated_username = sess.get("generated_username")

    assert generated_username is not None
    assert "4242" in generated_username


# ------------------------------------------------------------------
# Financial Cooldown Utility (money_guard.check_financial_cooldown)
# ------------------------------------------------------------------

def test_financial_cooldown_always_permits(recovery_data):
    """check_financial_cooldown always returns (True, '') after field removal."""
    seat = recovery_data["seat"]
    allowed, msg = check_financial_cooldown(seat)
    assert allowed is True
    assert msg == ""
