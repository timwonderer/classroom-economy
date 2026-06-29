"""
Tests for the admin transaction backfill feature.

Covers:
- Successful backfill with valid selections
- Backend validation rejects submissions with missing/invalid block selections
- Redirect behavior when no blocks are claimed
- Dashboard redirect when students need backfill
- Race condition: new orphaned transactions created between GET and POST are captured
- student.block updated to match selected_block
- Success message reflects actual backfilled count
- Bulk update writes correct join_code to all orphaned transactions
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Admin,
    ClassEconomy,
    ClassMembership,
    IdentityProfile,
    Seat,
    Student,
    StudentTeacher,
    Transaction,
    TransactionStatus,
    TeacherOnboarding,
)
from app.hash_utils import get_random_salt, hash_username

pytestmark = [
    pytest.mark.regression,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin(username: str = "bf_teacher") -> Admin:
    admin = make_admin(username, "secret")
    db.session.add(admin)
    db.session.commit()
    return admin


def _make_student(block: str = "A", first_name: str = "Alice", last_initial: str = "A") -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial=last_initial,
        block=block,
        salt=salt,
        first_half_hash=f"{first_name[0].upper()}2000",
        username_hash=hash_username(f"{first_name.lower()}-{block.lower()}", salt),
        passphrase_hash=generate_password_hash("pass"),
    )
    db.session.add(student)
    db.session.commit()
    return student


def _make_teacher_block(admin_id: int, block: str, join_code: str, student: Student | None = None) -> Seat:
    salt = get_random_salt()
    tb = Seat(student_id=student.id if student else None, join_code=join_code, block=block, block_identifier=block, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name=student.display_first_name if student else "Placeholder", last_name=student.display_last_initial if student else "P"))
    db.session.add(tb)
    db.session.commit()
    return tb


def _link(student: Student, admin: Admin) -> None:
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    db.session.commit()


def _orphaned_tx(student: Student, admin: Admin, amount: float = 50.0) -> Transaction:
    tx = Transaction(
        student_id=student.id,
        teacher_id=admin.id,
        join_code=None,
        amount=amount,
        account_type="checking",
        status=TransactionStatus.POSTED,
        type="Payroll",
        description="Legacy payroll",
    )
    db.session.add(tx)
    db.session.commit()
    return tx


def _login_admin(client, admin: Admin) -> None:
    from app.models import User, UserRole
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    if not user:
        user = User(
            username_hash=admin.username_lookup_hash,
            username_lookup_hash=admin.username_lookup_hash,
            user_role=UserRole.TEACHER,
        )
        db.session.add(user)
        db.session.commit()

    with client.session_transaction() as sess:
        sess["admin_id"] = admin.id
        sess["is_admin"] = True
        sess["user_id"] = user.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _complete_onboarding(admin: Admin) -> None:
    onboarding = TeacherOnboarding(
        teacher_id=admin.id,
        is_completed=True,
        completed_at=datetime.now(timezone.utc),
    )
    db.session.add(onboarding)
    db.session.commit()


# ---------------------------------------------------------------------------
# Tests: dashboard redirect
# ---------------------------------------------------------------------------

def test_dashboard_redirects_to_backfill_when_orphaned_txs_exist(client):
    """Dashboard redirects to /admin/backfill-transactions when orphaned transactions exist."""
    admin = _make_admin("bf_dash_teacher")
    _complete_onboarding(admin)
    student = _make_student("A", "Bob", "B")
    _link(student, admin)
    _make_teacher_block(admin.id, "A", "BLOCK1", student)
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/backfill-transactions" in response.location


def test_dashboard_warns_when_orphaned_txs_exist_but_no_blocks(client):
    """Dashboard shows warning flash when orphaned transactions exist but teacher has no claimed blocks."""
    admin = _make_admin("bf_no_blocks_teacher")
    _complete_onboarding(admin)
    student = _make_student("A", "Carol", "C")
    _link(student, admin)
    # No Seat → teacher cannot backfill; should see warning on dashboard
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.get("/admin/", follow_redirects=True)

    assert response.status_code == 200
    assert b"claimed class blocks with join codes" in response.data


def test_dashboard_loads_normally_when_no_orphaned_txs(client):
    """Dashboard renders normally when all transactions have a join_code."""
    admin = _make_admin("bf_clean_teacher")
    _complete_onboarding(admin)

    _login_admin(client, admin)
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: GET /admin/backfill-transactions
# ---------------------------------------------------------------------------

def test_backfill_page_renders_for_teacher_with_orphaned_txs(client):
    """Backfill page renders student list when orphaned transactions exist."""
    admin = _make_admin("bf_get_teacher")
    student = _make_student("A", "Dana", "D")
    _link(student, admin)
    _make_teacher_block(admin.id, "A", "JCGET1", student)
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.get("/admin/backfill-transactions")

    assert response.status_code == 200
    assert b"Dana" in response.data


def test_backfill_page_redirects_when_no_orphaned_txs(client):
    """Backfill page redirects to dashboard when no orphaned transactions exist."""
    admin = _make_admin("bf_clean2_teacher")
    _login_admin(client, admin)

    response = client.get("/admin/backfill-transactions", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/" in response.location


def test_backfill_page_redirects_when_no_claimed_blocks(client):
    """Backfill page redirects to dashboard when teacher has no claimed blocks with join_codes."""
    admin = _make_admin("bf_noblock_teacher")
    student = _make_student("A", "Eve", "E")
    _link(student, admin)
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.get("/admin/backfill-transactions", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/" in response.location


# ---------------------------------------------------------------------------
# Tests: POST /admin/backfill-transactions
# ---------------------------------------------------------------------------

def test_backfill_post_updates_transactions_and_redirects(client):
    """Successful backfill updates all orphaned transactions with the correct join_code."""
    admin = _make_admin("bf_post_teacher")
    student = _make_student("A", "Frank", "F")
    _link(student, admin)
    join_code = "POSTJC1"
    _make_teacher_block(admin.id, "A", join_code, student)
    tx1 = _orphaned_tx(student, admin, 100.0)
    tx2 = _orphaned_tx(student, admin, 200.0)

    _login_admin(client, admin)
    response = client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "A"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/" in response.location

    db.session.refresh(tx1)
    db.session.refresh(tx2)
    assert tx1.join_code == join_code
    assert tx2.join_code == join_code


def test_backfill_post_updates_student_block(client):
    """After backfill, student.block is updated to match selected_block."""
    admin = _make_admin("bf_block_teacher")
    student = _make_student("OldBlock", "Grace", "G")
    _link(student, admin)
    join_code = "BLKJC1"
    _make_teacher_block(admin.id, "NewBlock", join_code)
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "NewBlock"},
        follow_redirects=False,
    )

    db.session.expire(student)
    refreshed = db.session.get(Student, student.id)
    assert refreshed.block == "NewBlock"


def test_backfill_post_rejects_missing_selection(client):
    """POST with a missing block selection returns an error and does not update transactions."""
    admin = _make_admin("bf_missing_teacher")
    student = _make_student("A", "Hank", "H")
    _link(student, admin)
    join_code = "MISSJC1"
    _make_teacher_block(admin.id, "A", join_code, student)
    tx = _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.post(
        "/admin/backfill-transactions",
        data={},  # No block selected for the student
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please assign a valid period" in response.data

    # Transaction should not have been updated
    db.session.refresh(tx)
    assert tx.join_code is None


def test_backfill_post_rejects_invalid_block_selection(client):
    """POST with an invalid block name returns an error and does not update transactions."""
    admin = _make_admin("bf_invalid_teacher")
    student = _make_student("A", "Iris", "I")
    _link(student, admin)
    _make_teacher_block(admin.id, "A", "INVJC1", student)
    tx = _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "NONEXISTENT"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please assign a valid period" in response.data

    db.session.refresh(tx)
    assert tx.join_code is None


def test_backfill_success_message_shows_actual_count(client):
    """Success flash message reflects the number of students actually backfilled."""
    admin = _make_admin("bf_count_teacher")
    student = _make_student("A", "Jake", "J")
    _link(student, admin)
    join_code = "CNTJC1"
    _make_teacher_block(admin.id, "A", join_code, student)
    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "A"},
        follow_redirects=True,
    )

    assert b"Balances restored for 1 student(s)" in response.data


def test_backfill_captures_new_orphaned_txs_created_between_get_and_post(client):
    """POST re-fetches students so transactions created after the GET are also backfilled."""
    admin = _make_admin("bf_race_teacher")
    student = _make_student("A", "Kim", "K")
    _link(student, admin)
    join_code = "RACEJC1"
    _make_teacher_block(admin.id, "A", join_code, student)
    tx_before = _orphaned_tx(student, admin, 50.0)

    _login_admin(client, admin)
    # Simulate a new orphaned transaction arriving just before the POST
    tx_after = _orphaned_tx(student, admin, 75.0)

    response = client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "A"},
        follow_redirects=False,
    )

    assert response.status_code == 302

    db.session.refresh(tx_before)
    db.session.refresh(tx_after)
    assert tx_before.join_code == join_code
    assert tx_after.join_code == join_code


def test_backfill_multiple_join_codes_per_block_uses_most_frequent(client):
    """When a block has multiple join_codes, the most frequently used one is selected."""
    admin = _make_admin("bf_multi_jc_teacher")
    student = _make_student("A", "Leo", "L")
    _link(student, admin)

    # Create two Seats for block "A" with different join_codes
    salt = get_random_salt()
    for jc, count in [("JC_COMMON", 2), ("JC_RARE", 1)]:
        for _ in range(count):
            tb = Seat(student_id=student.id, join_code=jc, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
            db.session.add(tb)
            db.session.flush()
            db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name=student.display_first_name, last_name=student.display_last_initial))
            db.session.add(tb)
    db.session.commit()

    _orphaned_tx(student, admin)

    _login_admin(client, admin)
    response = client.post(
        "/admin/backfill-transactions",
        data={f"student_{student.id}_block": "A"},
        follow_redirects=False,
    )

    assert response.status_code == 302

    tx = Transaction.query.filter_by(join_code="JC_COMMON").first()
    assert tx is not None
