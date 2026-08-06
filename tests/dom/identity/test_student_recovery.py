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
from app.hash_utils import hash_username_lookup
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import (
    admin_generate_recovery_code,
    student_create_username,
    student_lookup_recovery_code,
    student_setup_pin_passphrase,
)


# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def recovery_data(client):
    """Set up a teacher, class, and a claimed student for recovery tests."""
    class_row = initialize("chemistry_p1", client.application)
    teacher = class_row.teacher_user
    teacher_seat = class_row.teacher_seat
    seat = class_row.students[0].seat
    user = class_row.students[0].user
    profile = class_row.students[0].profile
    with FEATContext("FEAT-IDEN-001", idempotency_key="recovery:fixture:name-override"):
        profile.first_name = "Original"
        profile.last_name = "Student"
        db.session.flush()
    class_row.students[0].first_name = "Original"
    class_row.students[0].last_name = "Student"

    return {
        "teacher": teacher,
        "teacher_seat": teacher_seat,
        "user": user,
        "seat": seat,
        "join_code": class_row.join_code,
        "class_id": class_row.class_id,
    }


# ------------------------------------------------------------------
# Step 1 — Teacher Initiates Reset
# ------------------------------------------------------------------

def test_DOM_IDEN_002__teacher_generates_reset_code(client, recovery_data):
    """Teacher posts to generate-code -> reset_code written to User."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    resp = admin_generate_recovery_code(client, seat.id)
    # Redirects back to student detail on success
    assert resp.status_code == 302

    linked_user = db.session.get(User, seat.user_id)
    assert linked_user is not None
    assert linked_user.reset_code is not None
    assert len(linked_user.reset_code) == 8
    assert ensure_utc(linked_user.reset_code_expires_at) > utc_now()


def test_DOM_IDEN_002__multiple_resets_invalidate_prior_codes(client, recovery_data):
    """Multiple reset requests overwrite the previous reset code."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    admin_generate_recovery_code(client, seat.id)
    linked_user = db.session.get(User, seat.user_id)
    db.session.refresh(linked_user)
    first_code = linked_user.reset_code

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(linked_user)
    second_code = linked_user.reset_code

    assert first_code != second_code
    assert linked_user.reset_code_expires_at is not None


# ------------------------------------------------------------------
# Step 2 — Student Submits Reset Code
# ------------------------------------------------------------------

def test_DOM_IDEN_002__student_lookup_success(client, recovery_data):
    """Valid reset_code -> credentials cleared, redirect to create-username."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_success"):
        db.session.flush()

    resp = student_lookup_recovery_code(client, "RESET123", follow_redirects=False)

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


def test_DOM_IDEN_002__student_lookup_expired_code(client, recovery_data):
    """Expired reset_code -> generic error."""
    user = recovery_data["user"]

    user.reset_code = "RESET123"
    user.reset_code_generated_at = utc_now() - timedelta(minutes=20)
    user.reset_code_expires_at = utc_now() - timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_student_lookup_expired_code"):
        db.session.flush()

    resp = student_lookup_recovery_code(client, "RESET123")

    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__student_lookup_nonexistent_code(client, recovery_data):
    """Completely invalid code -> generic error, no identity revealed."""
    resp = student_lookup_recovery_code(client, "NOTEXIST")

    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__recovery_does_not_create_new_user_row(client, recovery_data):
    """Recovering an account must not create a new User row."""
    user = recovery_data["user"]
    original_user_count = User.query.filter_by(user_role=UserRole.STUDENT).count()

    user.reset_code = "ROWTEST1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_does_not_create_new_user_row"):
        db.session.flush()

    student_lookup_recovery_code(client, "ROWTEST1")

    assert User.query.filter_by(user_role=UserRole.STUDENT).count() == original_user_count


def test_DOM_IDEN_002__recovery_preserves_seat_binding(client, recovery_data):
    """Recovery lookup must not disturb seat.user_id binding."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "KEEPCLM1"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_seat_binding"):
        db.session.flush()

    student_lookup_recovery_code(client, "KEEPCLM1", follow_redirects=False)

    db.session.refresh(seat)
    assert seat.user_id == user.id
    assert seat.claimed_at is not None


def test_DOM_IDEN_002__recovery_preserves_identity(client, recovery_data):
    """Recovery lookup preserves IdentityProfile first_name/last_name."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]

    user.reset_code = "IDTEST01"
    user.reset_code_generated_at = utc_now()
    user.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    with FEATContext("FEAT-IDEN-002", idempotency_key="recovery:test_preserves_identity"):
        db.session.flush()

    student_lookup_recovery_code(client, "IDTEST01")

    profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
    assert profile is not None
    assert profile.first_name == "Original"


# ------------------------------------------------------------------
# Economic Invariance
# ------------------------------------------------------------------

def test_DOM_IDEN_002__recovery_preserves_balance_and_transactions(client, recovery_data):
    """Transaction count unchanged through recovery lookup."""
    user = recovery_data["user"]
    seat = recovery_data["seat"]
    join_code = recovery_data["join_code"]

    tx = Transaction(
        user_id=user.id,
        seat_id=seat.id,
        class_id=recovery_data["class_id"],
        target_seat_id=seat.id,
        actor_seat_id=seat.id,
        mechanism="self",
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

    student_lookup_recovery_code(client, "PRESRV01")

    tx_count_after = Transaction.query.filter_by(seat_id=seat.id, class_id=recovery_data["class_id"]).count()
    assert tx_count_after == tx_count_before


# ------------------------------------------------------------------
# Reset Code Security
# ------------------------------------------------------------------

def test_DOM_IDEN_002__reset_code_invalid_after_credential_setup(client, recovery_data):
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

    student_lookup_recovery_code(client, "ONETIME1")
    student_create_username(client, "planet")
    student_setup_pin_passphrase(
        client,
        pin="1234",
        confirm_pin="1234",
        passphrase="updated-passphrase",
        confirm_passphrase="updated-passphrase",
    )

    db.session.refresh(user)
    assert user.reset_code is None
    assert user.reset_code_expires_at is None
    assert user.pin_hash is not None

    # Attempt reuse
    resp = student_lookup_recovery_code(client, "ONETIME1")
    assert b"Invalid or expired recovery code" in resp.data


def test_DOM_IDEN_002__only_one_active_reset_code_per_user(client, recovery_data):
    """Generating a second reset code overwrites the first on the User row."""
    teacher = recovery_data["teacher"]
    seat = recovery_data["seat"]
    user = recovery_data["user"]

    with client.session_transaction() as sess:
        set_canonical_context(sess, user_id=teacher.id, class_id=recovery_data["class_id"], seat_id=recovery_data["teacher_seat"].id, role="admin")

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(user)
    first_code = user.reset_code

    admin_generate_recovery_code(client, seat.id)
    db.session.refresh(user)

    assert user.reset_code != first_code
    # Only one reset_code column on User — no way for both to coexist
    users_with_first = User.query.filter_by(reset_code=first_code).count()
    assert users_with_first == 0


# ------------------------------------------------------------------
# Edge Cases
# ------------------------------------------------------------------

def test_DOM_IDEN_002__interrupting_reclaim_after_lookup(client, recovery_data):
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

    resp = student_lookup_recovery_code(client, "MIDFLOW1", follow_redirects=False)
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


def test_DOM_IDEN_002__recovery_username_uses_random_segment(client, recovery_data):
    """Recovery username generation stores a generated username in session."""
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

    student_lookup_recovery_code(client, "RAND4001", follow_redirects=False)

    resp = student_create_username(client, "galaxy", follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        generated_username = sess.get("generated_username")

    assert generated_username is not None
    assert "galaxy" in generated_username
    assert len(generated_username) > len("galaxy"), "Username must include generated segments beyond the base word"


def test_DOM_IDEN_006__claim_account_resolves_join_code_to_class_id(client):
    class_row = initialize("chemistry_p1", client.application)
    from app.models import Seat, User, UserRole
    with FEATContext("FEAT-IDEN-001", idempotency_key="claim_account:test_unclaimed_seat"):
        student = User(user_role=UserRole.STUDENT, username_hash="claim-student")
        db.session.add(student)
        db.session.flush()
        seat = Seat(
            user_id=None,
            class_id=class_row.class_id,
            role="student",
            claimed_at=None,
            claim_first_name_hash=hash_username_lookup("First".lower()),
            claim_last_name_hash=hash_username_lookup("Last".lower()),
        )
        db.session.add(seat)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=seat.id,
                class_id=class_row.class_id,
                profile_type="student_unclaimed",
                first_name="First",
                last_name="Last",
            )
        )
        db.session.flush()

    resp = client.post(
        "/student/claim-account",
        data={
            "join_code": class_row.join_code,
            "first_name": "First",
            "last_name": "Last",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    with client.session_transaction() as sess:
        assert sess.get("onboarding_seat_ref") == seat.id


# ------------------------------------------------------------------
# Financial Cooldown Utility (money_guard.check_financial_cooldown)
# ------------------------------------------------------------------

def test_DOM_IDEN_002__financial_cooldown_always_permits(recovery_data):
    """check_financial_cooldown always returns (True, '') after field removal."""
    seat = recovery_data["seat"]
    allowed, msg = check_financial_cooldown(seat)
    assert allowed is True
    assert msg == ""
