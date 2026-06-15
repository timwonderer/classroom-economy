"""
Regression tests for the class deletion audit fixes (2026-02-21).

Covers:
  - P1: BalanceCache rows are deleted when a join code is hard-deleted
  - P2: Sysadmin period deletion uses join_code scope, not legacy Student.block
  - P3: PayrollSettings / RentSettings lifecycle does not extend across
        unrelated classes that only share a display label

See docs/security/CLASS_DELETION_AUDIT.md for the full audit report.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Seat, IdentityProfile, Admin, ClassEconomy, Student, StudentTeacher, BalanceCache, PayrollSettings, RentSettings, SystemAdmin, StudentBlock, User, UserRole
from app.hash_utils import get_random_salt, hash_hmac
from tests.helpers.class_scope import create_class_scope
from app.utils.auth_username import build_hashed_username_fields


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _create_teacher(username: str) -> tuple[Admin, str, str]:
    secret = pyotp.random_base32()
    teacher = make_admin(
        username,
        secret,
    )
    db.session.add(teacher)
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    teacher.user_id = user.id
    db.session.commit()
    return teacher, secret, username


def _create_sysadmin(username: str = "sysadmin-audit") -> tuple[SystemAdmin, str, str]:
    secret = pyotp.random_base32()
    sa = make_sysadmin(
        username,
        secret,
    )
    db.session.add(sa)
    db.session.commit()
    return sa, secret, username


def _create_student(teacher: Admin, first_name: str, block: str, join_code: str) -> Student:
    salt = get_random_salt()
    credential = f"{first_name[0].upper()}2025"
    first_half_hash = hash_hmac(credential.encode(), salt)

    student = Student(
        first_name=first_name,
        last_initial=first_name[0].upper(),
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
    )
    db.session.add(student)
    db.session.flush()

    class_row = create_class_scope(
        teacher=teacher,
        join_code=join_code,
        student=student,
        block=block,
        display_name=block,
    )
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    _tb_seat = Seat(student_id=student.id, class_id=class_row.class_id, join_code=join_code, block=block, block_identifier=block, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=first_name, last_initial=first_name[0].upper()))
    db.session.commit()
    return student


def _login_teacher(client, teacher: Admin, secret: str, username: str):
    client.post(
        "/admin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    class_row = (
        db.session.query(ClassEconomy)
        .filter_by(teacher_id=teacher.id)
        .order_by(ClassEconomy.created_at.asc(), ClassEconomy.join_code.asc())
        .first()
    )
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id
        if teacher.user_id:
            sess["user_id"] = teacher.user_id
        if class_row:
            sess["current_class_id"] = class_row.class_id
            sess["current_join_code"] = class_row.join_code
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _login_sysadmin(client, sysadmin: SystemAdmin, secret: str, username: str):
    client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# P1: BalanceCache is deleted on join-code hard-delete
# ---------------------------------------------------------------------------

def test_balance_cache_deleted_when_join_code_deleted(client):
    """BalanceCache rows for a deleted join code must not survive."""
    teacher, secret, teacher_username = _create_teacher("teacher-bc-del")
    student = _create_student(teacher, "Alice", "A", "BCDEL1")

    cache = BalanceCache(
        student_id=student.id,
        join_code="BCDEL1",
        posted_checking_balance_cents=5000,
        posted_savings_balance_cents=1000,
    )
    db.session.add(cache)
    db.session.commit()
    cache_id = cache.id

    _login_teacher(client, teacher, secret, teacher_username)
    resp = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "BCDEL1",
            "gate_phrase": "DELETE JOIN CODE BCDEL1",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"

    # BalanceCache row must be gone
    assert db.session.get(BalanceCache, cache_id) is None


def test_balance_cache_for_other_join_code_not_deleted(client):
    """BalanceCache for a different join code must survive when only one class is deleted."""
    teacher, secret, teacher_username = _create_teacher("teacher-bc-keep")
    student_a = _create_student(teacher, "Alice", "A", "BCDEL2")
    student_b = _create_student(teacher, "Bob", "B", "BCKEEP2")

    cache_del = BalanceCache(
        student_id=student_a.id,
        join_code="BCDEL2",
        posted_checking_balance_cents=1000,
        posted_savings_balance_cents=0,
    )
    cache_keep = BalanceCache(
        student_id=student_b.id,
        join_code="BCKEEP2",
        posted_checking_balance_cents=2000,
        posted_savings_balance_cents=500,
    )
    db.session.add_all([cache_del, cache_keep])
    db.session.commit()
    keep_id = cache_keep.id

    _login_teacher(client, teacher, secret, teacher_username)
    resp = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "BCDEL2",
            "gate_phrase": "DELETE JOIN CODE BCDEL2",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
    )
    assert resp.get_json()["status"] == "success"

    # BCKEEP2 cache row must still be present
    assert db.session.get(BalanceCache, keep_id) is not None


# ---------------------------------------------------------------------------
# P2: Sysadmin deletion endpoints are disabled
# ---------------------------------------------------------------------------

def test_sysadmin_period_deletion_endpoint_is_disabled(client):
    teacher, _, _ = _create_teacher("teacher-sz-jc")
    sysadmin, sys_secret, sysadmin_username = _create_sysadmin("sysadmin-sz")

    # Create student whose Student.block does NOT match the period name
    salt = get_random_salt()
    fhh = hash_hmac(b"A2025", salt)
    student = Student(
        first_name="Zara",
        last_initial="Z",
        block="",          # deliberately does NOT equal "Z"
        salt=salt,
        first_half_hash=fhh,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    _tb_seat = Seat(student_id=student.id, join_code="SZJC1", block="Z", block_identifier="Z", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name="Zara", last_initial="Z"))
    db.session.commit()
    teacher.last_login = None
    db.session.commit()

    _login_sysadmin(client, sysadmin, sys_secret, sysadmin_username)
    resp = client.post(
        f"/sysadmin/delete-period/{teacher.id}/Z",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"System admins cannot delete classes" in resp.data
    assert Seat.query.filter_by(teacher_id=teacher.id, block="Z").count() == 1


def test_sysadmin_teacher_deletion_endpoint_is_disabled(client):
    teacher, _, _ = _create_teacher("teacher-mp-del")
    sysadmin, sys_secret, sysadmin_username = _create_sysadmin("sysadmin-mp")

    _login_sysadmin(client, sysadmin, sys_secret, sysadmin_username)
    resp = client.post(
        f"/sysadmin/manage-teachers/delete/{teacher.id}",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"System admins cannot delete teacher accounts" in resp.data
    assert db.session.get(Admin, teacher.id) is not None


# ---------------------------------------------------------------------------
# P3: Settings orphan cleanup on join-code deletion
# ---------------------------------------------------------------------------

def test_payroll_settings_deleted_when_last_join_code_for_block_removed(client):
    """PayrollSettings for block 'A' must be removed when no TeacherBlock remains for it."""
    teacher, secret, teacher_username = _create_teacher("teacher-ps-del")
    _create_student(teacher, "Pam", "A", "PSDEL1")

    ps = PayrollSettings(teacher_id=teacher.id, block="A", pay_rate=0.25)
    db.session.add(ps)
    db.session.commit()
    ps_id = ps.id

    _login_teacher(client, teacher, secret, teacher_username)
    resp = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "PSDEL1",
            "gate_phrase": "DELETE JOIN CODE PSDEL1",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
    )
    assert resp.get_json()["status"] == "success"

    # PayrollSettings for block A should be gone (no more TeacherBlock for it)
    assert db.session.get(PayrollSettings, ps_id) is None


def test_rent_settings_deleted_when_last_join_code_for_block_removed(client):
    """RentSettings for block 'A' must be removed when no TeacherBlock remains for it."""
    teacher, secret, teacher_username = _create_teacher("teacher-rs-del")
    _create_student(teacher, "Raj", "A", "RSDEL1")
    class_row = db.session.query(ClassEconomy).filter_by(join_code="RSDEL1").first()
    assert class_row is not None

    rs = RentSettings(class_id=class_row.class_id, block="A", rent_amount=50)
    db.session.add(rs)
    db.session.commit()
    rs_id = rs.id

    _login_teacher(client, teacher, secret, teacher_username)
    resp = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "RSDEL1",
            "gate_phrase": "DELETE JOIN CODE RSDEL1",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
    )
    assert resp.get_json()["status"] == "success"

    db.session.expire_all()
    assert db.session.get(RentSettings, rs_id) is None


def test_payroll_settings_deleted_even_if_other_class_shares_block_label(client):
    """
    PayrollSettings for block 'A' are deleted with the class that owns them.

    A second class using the same display label is irrelevant because labels
    are metadata, not an identity or lifecycle boundary.
    """
    teacher, secret, teacher_username = _create_teacher("teacher-ps-keep")
    _create_student(teacher, "Pat", "A", "PSKP1")  # will be deleted

    # Add a second seat in the same block A but different join code
    salt2 = get_random_salt()
    fhh2 = hash_hmac(b"P2025", salt2)
    student2 = Student(
        first_name="Paula",
        last_initial="P",
        block="A",
        salt=salt2,
        first_half_hash=fhh2,
    )
    db.session.add(student2)
    db.session.flush()
    create_class_scope(
        teacher=teacher,
        join_code="PSKP2",
        student=student2,
        block="A",
        display_name="A",
    )
    db.session.add(StudentTeacher(student_id=student2.id, teacher_id=teacher.id))
    db.session.commit()

    ps = PayrollSettings(teacher_id=teacher.id, block="A", pay_rate=0.50)
    db.session.add(ps)
    db.session.commit()
    ps_id = ps.id

    _login_teacher(client, teacher, secret, teacher_username)
    # Delete only PSKP1. PSKP2 shares the label, but not the class identity.
    resp = client.post(
        "/admin/join-code/delete",
        json={
            "join_code": "PSKP1",
            "gate_phrase": "DELETE JOIN CODE PSKP1",
            "gate_countdown_seconds": 30,
            "gate_hold_seconds": 10,
        },
    )
    assert resp.get_json()["status"] == "success"

    # The settings are removed with the deleted class; same-label siblings do
    # not preserve them.
    assert db.session.get(PayrollSettings, ps_id) is None


def test_account_deletion_requires_gate(client):
    """Teacher account deletion must be blocked when gate fields are missing."""
    teacher, secret, teacher_username = _create_teacher("teacher-dr-no-gate")
    _login_teacher(client, teacher, secret, teacher_username)

    previous_ratelimit_enabled = client.application.config.get("RATELIMIT_ENABLED", True)
    client.application.config["RATELIMIT_ENABLED"] = False
    try:
        resp = client.post(
            "/admin/account-delete",
            data={
                "request_type": "account",
            },
            environ_overrides={"REMOTE_ADDR": "127.0.0.31", "HTTP_X_FORWARDED_FOR": "127.0.0.31"},
            follow_redirects=True,
        )
    finally:
        client.application.config["RATELIMIT_ENABLED"] = previous_ratelimit_enabled
    assert resp.status_code == 200
    assert b"Account deletion blocked: confirmation phrase did not match." in resp.data
    assert db.session.get(Admin, teacher.id) is not None

def test_account_deletion_executes_with_valid_gate(client):
    """Teacher account deletion succeeds when timed gate evidence is present."""
    teacher, secret, teacher_username = _create_teacher("teacher-dr-gated")
    _login_teacher(client, teacher, secret, teacher_username)

    previous_ratelimit_enabled = client.application.config.get("RATELIMIT_ENABLED", True)
    client.application.config["RATELIMIT_ENABLED"] = False
    try:
        resp = client.post(
            "/admin/account-delete",
            data={
                "request_type": "account",
                "gate_phrase": f"CONFIRM DELETE {teacher.get_display_name()} ACCOUNT",
                "gate_countdown_seconds": 30,
                "gate_hold_seconds": 10,
            },
            environ_overrides={"REMOTE_ADDR": "127.0.0.32", "HTTP_X_FORWARDED_FOR": "127.0.0.32"},
            follow_redirects=True,
        )
    finally:
        client.application.config["RATELIMIT_ENABLED"] = previous_ratelimit_enabled
    assert resp.status_code == 200
    assert b"permanently deleted" in resp.data
    assert db.session.get(Admin, teacher.id) is None
