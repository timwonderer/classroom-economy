"""
Tests for the student account recovery flow.

The simplified recovery flow:
  Step 1 — Teacher generates a reset code for the student
  Step 2 — Student enters join_code + reset_code at /recovery/lookup
            (credentials cleared here; first_name/last_initial unchanged)
  Step 3 — Student creates a new username at /student/create-username
  Step 4 — Student sets new PIN + passphrase at /student/setup-pin-passphrase

No PII re-entry is required. Identity (first_name, last_initial) is preserved
from the teacher-managed roster and is not editable by the student.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import re
import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Seat, IdentityProfile, ClassEconomy, Admin, StudentTeacher, Transaction, StudentBlock, User, UserRole
from app.hash_utils import get_random_salt, hash_username, hash_username_lookup
from app.utils.money_guard import check_financial_cooldown
from app.utils.time import ensure_utc, utc_now
from tests.helpers.class_scope import make_student_identity

# ----------------------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------------------

@pytest.fixture
def recovery_data(client):
    """Setup a teacher, student, and class for recovery tests."""
    teacher = make_admin("teacher_rec", "base32secret3232")
    teacher_user = User(
        user_role=UserRole.TEACHER,
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        totp_secret_encrypted=teacher.totp_secret,
    )
    db.session.add_all([teacher, teacher_user])
    db.session.flush()

    join_code = "A123"
    class_row = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name="Recovery Class",
    )
    profile = IdentityProfile(profile_type="student", first_name="Original", last_name="O")
    db.session.add_all([class_row, profile])
    db.session.flush()

    student = make_student_identity(
        class_id=class_row.class_id,
        join_code=join_code,
        block="A",
        first_name="Original",
        last_name="O",
        claimed=True,
    )
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username_lookup("orig_user"),
        username_lookup_hash=hash_username_lookup("orig_user"),
        has_completed_setup=True,
    )
    db.session.add_all([user])
    db.session.flush()
    seat = student
    db.session.add(StudentTeacher(
        user_id=student.user_id,
        teacher_id=teacher.id,
        class_id=class_row.class_id,
        join_code=join_code,
    ))
    db.session.commit()

    return {
        "teacher": teacher,
        "teacher_user": teacher_user,
        "student": student,
        "seat": seat,
        "join_code": join_code,
    }


# ------------------------------------------------------------------
# Step 1 — Teacher Initiates Reset
# ------------------------------------------------------------------

def test_teacher_generates_reset_code(client, recovery_data):
    """Teacher clicks 'Reset Student Account' -> system generates code."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["user_id"] = recovery_data["teacher_user"].id
        sess["is_admin"] = True

    resp = client.post(
        f"/recovery/admin/generate-code/{student.id}",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Reset code generated" in resp.data

    db.session.refresh(student)
    assert student.reset_code is not None
    assert len(student.reset_code) == 8
    assert ensure_utc(student.reset_code_expires_at) > utc_now()
    assert student.recovery_status == 'to_be_claimed'


def test_multiple_resets_invalidate_prior_codes(client, recovery_data):
    """Multiple reset attempts regenerate and invalidate prior codes."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["user_id"] = recovery_data["teacher_user"].id
        sess["is_admin"] = True

    # First reset
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    first_code = student.reset_code

    # Second reset
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    second_code = student.reset_code

    assert first_code != second_code
    assert student.recovery_status == 'to_be_claimed'


# ------------------------------------------------------------------
# Step 2 — Student Enters Join Code + Reset Code
# ------------------------------------------------------------------

def test_student_lookup_success(client, recovery_data):
    """Valid join_code + reset_code -> credentials cleared, redirect to create-username."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "RESET123",
    }, follow_redirects=False)

    assert resp.status_code == 302
    assert "/student/create-username" in resp.location

    with client.session_transaction() as sess:
        assert sess.get("onboarding_student_ref") == student.id
        assert sess.get("onboarding_seat_ref") is not None
        assert sess.get("onboarding_user_ref") is not None
        assert "recovery_student_ref" not in sess

    # Credentials cleared; identity preserved
    db.session.refresh(student)
    assert student.username_hash is None
    assert student.pin_hash is None
    assert student.passphrase_hash is None
    assert student.has_completed_setup is False
    assert student.display_first_name == "Original"
    assert student.display_last_initial == "O"
    # Reset code still active until credential setup completes
    assert student.reset_code == "RESET123"
    assert student.recovery_status == 'to_be_claimed'


def test_student_lookup_wrong_join_code(client, recovery_data):
    """Reset code valid but join_code doesn't match -> generic error."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": "WRONG999",
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_expired_code(client, recovery_data):
    """Expired reset_code -> generic error."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() - timedelta(minutes=1)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_wrong_status(client, recovery_data):
    """Reset code present but student not in to_be_claimed -> fail."""
    student = recovery_data["student"]

    student.reset_code = "RESET123"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'active'   # Not to_be_claimed
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "RESET123",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_student_lookup_nonexistent_code(client, recovery_data):
    """Completely invalid code -> generic error, no identity revealed."""
    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "NOTEXIST",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


# ------------------------------------------------------------------
# Verify Identity Route (deprecated — now just redirects)
# ------------------------------------------------------------------

def test_verify_identity_redirects_to_lookup(client, recovery_data):
    """GET /recovery/verify-identity redirects to account_lookup (deprecated route)."""
    resp = client.get("/recovery/verify-identity", follow_redirects=False)
    assert resp.status_code == 302
    assert "/recovery/lookup" in resp.location


def test_verify_identity_post_redirects_to_lookup(client, recovery_data):
    """POST /recovery/verify-identity also redirects (no longer processes PII)."""
    resp = client.post("/recovery/verify-identity", data={
        "first_name": "Test",
        "last_name": "User",
        "dob": "2015-06-15",
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert "/recovery/lookup" in resp.location


def test_recovery_does_not_create_new_student_row(client, recovery_data):
    """Recovering an account must not create a new student row."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]
    original_id = student.id
    original_count = IdentityProfile.query.count()

    student.reset_code = "ROWTEST1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "ROWTEST1",
    }, follow_redirects=True)

    assert IdentityProfile.query.count() == original_count
    db.session.refresh(student)
    assert student.id == original_id


def test_recovery_preserves_teacher_block_claimed(client, recovery_data):
    """Recovery lookup must not disturb claimed seat status."""
    student = recovery_data["student"]
    teacher = recovery_data["teacher"]
    join_code = recovery_data["join_code"]

    student.reset_code = "KEEPCLM1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "KEEPCLM1",
    }, follow_redirects=False)

    assert resp.status_code == 302

    seat = Seat.query.filter_by(user_id=student_user.id, join_code=join_code, block='A').first()
    assert seat is not None
    assert seat.claimed_at is not None


def test_recovery_preserves_identity(client, recovery_data):
    """Recovery lookup preserves first_name and last_initial (teacher-managed)."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "IDTEST01"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "IDTEST01",
    }, follow_redirects=True)

    db.session.refresh(student)
    assert student.display_first_name == "Original"
    assert student.display_last_initial == "O"


# ------------------------------------------------------------------
# Economic Invariance Tests
# ------------------------------------------------------------------

def test_recovery_preserves_balance_and_transactions(client, recovery_data):
    """Balance and transaction count unchanged through recovery."""
    student = recovery_data["student"]
    seat = recovery_data["seat"]
    teacher = recovery_data["teacher"]
    join_code = recovery_data["join_code"]

    # Give student a balance
    db.session.add(StudentBlock(
        user_id=student_user.id,
        period="A",
        join_code=join_code,
    ))
    tx = Transaction(
        user_id=student_user.id,amount=200.0,
        type='deposit',
        description='Initial deposit',
        account_type='checking',
        join_code=join_code,
    )
    db.session.add(tx)
    db.session.commit()

    tx_count_before = Transaction.query.filter_by(
        seat_id=seat.id, join_code=join_code
    ).count()

    student.reset_code = "PRESRV01"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    # Run recovery (new simplified flow — just lookup)
    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "PRESRV01",
    }, follow_redirects=True)

    # Verify economic data untouched
    tx_count_after = Transaction.query.filter_by(
        seat_id=seat.id, join_code=join_code
    ).count()
    assert tx_count_after == tx_count_before

    # No new economic transactions created during recovery
    recovery_txns = Transaction.query.filter_by(
        seat_id=seat.id, type='recovery'
    ).count()
    assert recovery_txns == 0


# ------------------------------------------------------------------
# Reset Code Security Tests
# ------------------------------------------------------------------

def test_reset_code_invalid_after_use(client, recovery_data):
    """Reset code is single-use — invalid after full credential setup is completed."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "ONETIME1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    # Complete the full recovery flow via account_lookup
    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "ONETIME1",
    }, follow_redirects=True)

    client.post('/student/create-username', data={
        'write_in_word': 'planet',
    }, follow_redirects=True)
    client.post('/student/setup-pin-passphrase', data={
        'pin': '1234',
        'confirm_pin': '1234',
        'passphrase': 'updated-passphrase',
        'confirm_passphrase': 'updated-passphrase',
    }, follow_redirects=True)

    db.session.refresh(student)
    assert student.reset_code is None
    assert student.recovery_status == 'active'

    # Attempt reuse
    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "ONETIME1",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_only_one_active_reset_code_per_student(client, recovery_data):
    """Only one active reset_code per student at a time."""
    teacher = recovery_data["teacher"]
    student = recovery_data["student"]

    with client.session_transaction() as sess:
        sess["admin_id"] = teacher.id
        sess["user_id"] = recovery_data["teacher_user"].id
        sess["is_admin"] = True

    # Generate first code
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)
    first_code = student.reset_code

    # Generate second code (overwrites first)
    client.post(f"/recovery/admin/generate-code/{student.id}")
    db.session.refresh(student)

    assert student.reset_code != first_code
    # Only one reset_code stored
    students_with_first = IdentityProfile.query.filter_by(reset_code=first_code).count()
    assert students_with_first == 0


# ------------------------------------------------------------------
# Edge Case Tests
# ------------------------------------------------------------------

def test_reclaim_when_not_to_be_claimed_fails(client, recovery_data):
    """Attempt reclaim when status != to_be_claimed -> fail."""
    student = recovery_data["student"]
    student.reset_code = "EDGECASE"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'active'
    db.session.commit()

    resp = client.post("/recovery/lookup", data={
        "join_code": recovery_data["join_code"],
        "reset_code": "EDGECASE",
    }, follow_redirects=True)

    assert b"Invalid or expired recovery code" in resp.data


def test_interrupting_reclaim_after_lookup(client, recovery_data):
    """After lookup, credentials are cleared but reset_code stays valid for retry."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]
    original_name = student.display_first_name

    student.reset_code = "MIDFLOW1"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    # Complete Step 2 (lookup) then abandon — don't finish username/credential setup
    resp = client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "MIDFLOW1",
    }, follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(student)

    # Identity preserved (teacher-managed)
    assert student.display_first_name == original_name
    # Credentials cleared (setup must be re-completed)
    assert student.username_hash is None
    assert student.pin_hash is None
    assert student.has_completed_setup is False
    # Reset code still valid — student can retry credential setup
    assert student.reset_code == "MIDFLOW1"
    assert student.recovery_status == 'to_be_claimed'


def test_recovery_username_uses_random_four_digit_segment(client, recovery_data, monkeypatch):
    """Recovery username generation uses a transient random 4-digit segment."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    student.reset_code = "RAND4001"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "RAND4001",
    }, follow_redirects=False)

    monkeypatch.setattr("app.routes.student.random.randint", lambda _a, _b: 4242)

    resp = client.post('/student/create-username', data={
        'write_in_word': 'galaxy',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with client.session_transaction() as sess:
        generated_username = sess.get('generated_username')

    assert generated_username is not None
    assert "4242" in generated_username
    assert re.search(r"4242OO$", generated_username) is not None


# ------------------------------------------------------------------
# Post-Setup Completion Tests
# ------------------------------------------------------------------

def test_setup_completion_nulls_student_pii(client, recovery_data):
    """After setup_pin_passphrase, recovery state is fully consumed."""
    student = recovery_data["student"]
    join_code = recovery_data["join_code"]

    # Recovery lookup — clears credentials
    student.reset_code = "PIICLN01"
    student.reset_code_expires_at = utc_now() + timedelta(minutes=10)
    student.recovery_status = 'to_be_claimed'
    db.session.commit()

    client.post("/recovery/lookup", data={
        "join_code": join_code,
        "reset_code": "PIICLN01",
    }, follow_redirects=True)

    # Create username
    client.post('/student/create-username', data={
        'write_in_word': 'galaxy',
    }, follow_redirects=True)

    # Complete setup
    client.post('/student/setup-pin-passphrase', data={
        'pin': '4321',
        'confirm_pin': '4321',
        'passphrase': 'cleanup-phrase',
        'confirm_passphrase': 'cleanup-phrase',
    }, follow_redirects=True)

    db.session.refresh(student)
    assert student.has_completed_profile_migration is True
    assert student.recovery_status == 'active'
    assert student.reset_code is None


# ------------------------------------------------------------------
# Financial Cooldown Utility (preserved from original)
# ------------------------------------------------------------------

def test_financial_cooldown_enforcement(recovery_data):
    """Test the utility function check_financial_cooldown."""
    student = recovery_data["student"]

    # No cooldown
    student.money_action_cooldown_until = None
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True

    # Active cooldown
    student.money_action_cooldown_until = utc_now() + timedelta(minutes=30)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is False
    assert "29 min" in msg or "30 min" in msg

    # Expired cooldown
    student.money_action_cooldown_until = utc_now() - timedelta(minutes=1)
    allowed, msg = check_financial_cooldown(student)
    assert allowed is True
