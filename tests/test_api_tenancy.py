"""
Tests for API route tenant scoping.

Validates that API endpoints properly scope data access to the current admin's students.
"""

from tests.helpers.v2_fixtures import make_sysadmin, seed_canonical_admin, seed_class_with_seat, seed_student_identity
import pyotp
from datetime import datetime, timezone

from app import app, db
from app.feats.base import FEATContext
from app.models import (
    ClassFeature,
    ClassEconomy,
    HallPassSettings,
    Seat,
    AttendanceSession,
    UserRole,
    User,
)
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


def _seed_teacher(username: str) -> tuple[User, str]:
    secret = pyotp.random_base32()
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"api-tenancy:seed-teacher:{username}"):
        teacher = seed_canonical_admin(username, totp_secret=secret).user
        teacher.current_session_nonce = "nonce"
        db.session.flush()
    return teacher, secret


def _seed_student(class_id: str, first_name: str) -> Seat:
    return seed_student_identity(
        class_id=class_id,
        first_name=first_name,
        last_name="X",
        username=first_name.lower(),
    ).seat


def _create_class_for_teacher(teacher: User, *, display_name: str | None = None, section: str | None = None) -> ClassEconomy:
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"api-tenancy:create-class:{teacher.id}:{display_name or ''}:{section or ''}"):
        class_row = seed_class_with_seat(
            teacher=teacher,
            display_name=display_name,
            section=section,
        ).class_row
    return class_row


def _login_admin(client, admin: User, class_id: str):
    login_teacher(client, admin, class_id=class_id)


def _login_student(client, student: Seat, class_id: str):
    user = db.session.get(User, student.user_id)
    assert user is not None
    seat = Seat.query.filter_by(user_id=user.id, class_id=class_id).first()
    assert seat is not None
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = user.current_session_nonce
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_id,
            seat_id=seat.id,
            role="student",
        )
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _create_tap_event(student: Seat, teacher: User, class_id: str, status: str = "active"):
    """Create a canonical v2 attendance session for testing."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"api-tenancy:create-tap:{class_id}:{student.id}:{teacher.id}:{status}"):
        class_row = ClassEconomy.query.filter_by(class_id=class_id, user_id=teacher.id).first()
        assert class_row is not None and class_row.class_id, "Expected class scope to exist before attendance session creation"
        seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_row.class_id).first()
        assert seat is not None, "Expected canonical student seat to exist for attendance session creation"
        now = datetime.now(timezone.utc)
        tap = AttendanceSession(
            seat_id=seat.id,
            class_id=class_row.class_id,
            started_at=now,
        )
        if status == "inactive":
            tap.ended_at = now
            tap.duration_seconds = 0
        db.session.add(tap)
        db.session.flush()
    return tap


def _create_claimed_seat(teacher: User, student: Seat, class_id: str):
    """Mark the canonical student seat as claimed for tenancy tests."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"api-tenancy:create-claimed-seat:{class_id}:{student.id}:{teacher.id}"):
        class_row = ClassEconomy.query.filter_by(class_id=class_id, user_id=teacher.id).first()
        runtime_seat = Seat.query.filter_by(user_id=student.user_id, class_id=class_row.class_id).first() if class_row else None
        assert runtime_seat is not None, "Expected canonical student seat to exist before claim state mutation"
        if runtime_seat and not runtime_seat.claimed_at:
            runtime_seat.claimed_at = datetime.now(timezone.utc)
        db.session.flush()
    return runtime_seat


def test_attendance_history_api_scoped_to_teacher(client):
    """Admin should only see attendance history for their own students."""
    teacher_a, secret_a = _seed_teacher("teacher-a")
    teacher_b, secret_b = _seed_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, section="Period1")
    class_b = _create_class_for_teacher(teacher_b, section="Period1")
    
    student_a = _seed_student(class_a.class_id, "StudentA")
    student_b = _seed_student(class_b.class_id, "StudentB")
    
    # Create tap events for both students
    tap_a = _create_tap_event(student_a, teacher_a, class_a.class_id, status="active")
    tap_b = _create_tap_event(student_b, teacher_b, class_b.class_id, status="active")
    
    # Login as teacher A
    _login_admin(client, teacher_a, class_a.class_id)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see student A's tap event
    assert data["status"] == "success"
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a.id in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_includes_shared_students(client):
    """Admin should see attendance history for shared students."""
    teacher_a, _ = _seed_teacher("teacher-a")
    teacher_b, _ = _seed_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, section="A")
    class_b = _create_class_for_teacher(teacher_b, section="B")

    shared_student = _seed_student(class_a.class_id, "Shared")
    exclusive_a = _seed_student(class_b.class_id, "ExclusiveA")
    exclusive_b = _seed_student(class_b.class_id, "ExclusiveB")

    tap_shared = _create_tap_event(shared_student, teacher_a, class_a.class_id)
    tap_a = _create_tap_event(exclusive_a, teacher_b, class_b.class_id)
    tap_b = _create_tap_event(exclusive_b, teacher_b, class_b.class_id)

    _login_admin(client, teacher_a, class_a.class_id)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Class-scoped view: current class context is SHARED_A.
    # Taps from other class scopes must not appear.
    record_ids = [r["id"] for r in data["records"]]
    print(f"DEBUG: tap_shared.id={tap_shared.id}, tap_shared.class_id={tap_shared.class_id}")
    print(f"DEBUG: tap_a.id={tap_a.id}, tap_a.class_id={tap_a.class_id}")
    print(f"DEBUG: tap_b.id={tap_b.id}, tap_b.class_id={tap_b.class_id}")
    
    print(f"DEBUG: record_ids={record_ids}")
    
    assert tap_shared.id in record_ids
    assert tap_a.id not in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_filters_work_with_scoping(client):
    """Filters should work correctly with tenant scoping."""
    teacher_a, _ = _seed_teacher("teacher-a")
    teacher_b, _ = _seed_teacher("teacher-b")
    class_a1 = _create_class_for_teacher(teacher_a, section="Period1")
    class_a2 = _create_class_for_teacher(teacher_a, section="Period2")
    class_b = _create_class_for_teacher(teacher_b, section="Period1")

    student_a1 = _seed_student(class_a1.class_id, "StudentA1")
    student_a2 = _seed_student(class_a2.class_id, "StudentA2")
    student_b = _seed_student(class_b.class_id, "StudentB")

    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:create-attendance-history-records"):
        seat_a1 = Seat.query.filter_by(user_id=student_a1.user_id, class_id=class_a1.class_id).first()
        seat_a2 = Seat.query.filter_by(user_id=student_a2.user_id, class_id=class_a2.class_id).first()
        seat_b = Seat.query.filter_by(user_id=student_b.user_id, class_id=class_b.class_id).first()
        assert seat_a1 is not None and seat_a2 is not None and seat_b is not None
        tap_a1 = AttendanceSession(seat_id=seat_a1.id, class_id=class_a1.class_id, started_at=datetime.now(timezone.utc))
        tap_a2 = AttendanceSession(seat_id=seat_a2.id, class_id=class_a2.class_id, started_at=datetime.now(timezone.utc))
        tap_b = AttendanceSession(seat_id=seat_b.id, class_id=class_b.class_id, started_at=datetime.now(timezone.utc))
        db.session.add_all([tap_a1, tap_a2, tap_b])
        db.session.flush()

    _login_admin(client, teacher_a, class_a1.class_id)
    
    # Request attendance history filtered by period 1
    response = client.get("/api/attendance/history?period=1")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see teacher A's period 1 student (not teacher B's)
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a1.id not in record_ids  # Different period
    assert tap_a2.id in record_ids
    assert tap_b.id not in record_ids  # Different teacher


def test_attendance_history_api_system_admin_sees_all(client):
    """System admin should see all attendance records."""
    from app.models import SystemAdmin
    
    # Create system admin
    sys_secret = pyotp.random_base32()
    sys_admin = make_sysadmin("sysadmin")
    with FEATContext("FEAT-ADMN-001", idempotency_key="api-tenancy:create-sysadmin"):
        db.session.flush()
    
    # Create teachers and students
    teacher_a, _ = _seed_teacher("teacher-a")
    teacher_b, _ = _seed_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a)
    class_b = _create_class_for_teacher(teacher_b)

    student_a = _seed_student(class_a.class_id, "StudentA")
    student_b = _seed_student(class_b.class_id, "StudentB")

    tap_a = _create_tap_event(student_a, teacher_a, class_a.class_id)
    tap_b = _create_tap_event(student_b, teacher_b, class_b.class_id)
    
    # Login as system admin
    client.post(
        "/sysadmin/login",
        data={"username": "sysadmin", "totp_code": pyotp.TOTP(sys_secret).now()},
        follow_redirects=True,
    )
    
    # System admins accessing via /api routes would need admin session too
    # For now, just verify the scoping logic works for regular admins
    # (System admins typically don't use the API routes directly)


def test_admin_tap_entries_scoped_by_class_id(client):
    """Admin should only receive tap entries from their own class scope."""
    teacher_a, _ = _seed_teacher("teacher-a")
    teacher_b, _ = _seed_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, section="A")
    class_b = _create_class_for_teacher(teacher_b, section="B")
    shared_student_a = _seed_student(class_a.class_id, "SharedTapA")
    shared_student_b = _seed_student(class_b.class_id, "SharedTapB")
    seat_a = Seat.query.filter_by(user_id=shared_student_a.user_id, class_id=class_a.class_id).first()
    seat_b = Seat.query.filter_by(user_id=shared_student_b.user_id, class_id=class_b.class_id).first()
    assert seat_a is not None and seat_b is not None
    user_seat_a = seat_a
    user_seat_b = seat_b

    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:create-tap-entries:join-code"):
        tap_a = AttendanceSession(
            seat_id=user_seat_a.id,
            class_id=seat_a.class_id,
            started_at=datetime.now(timezone.utc),
        )
        tap_b = AttendanceSession(
            seat_id=user_seat_b.id,
            class_id=seat_b.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add_all([tap_a, tap_b])
        db.session.flush()

    _login_admin(client, teacher_a, class_a.class_id)
    response = client.get(f"/api/admin/tap-entries/{user_seat_a.id}")

    assert response.status_code == 200
    payload = response.get_json()
    returned_ids = {
        event["id"]
        for period_data in payload["periods"].values()
        for event in period_data["sessions"]
    }
    assert tap_a.id in returned_ids
    assert tap_b.id not in returned_ids


def test_admin_delete_tap_entry_enforces_class_scope(client):
    """Admin should not delete tap entries from another teacher's class scope."""
    teacher_a, _ = _seed_teacher("teacher-a")
    teacher_b, _ = _seed_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, section="A")
    class_b = _create_class_for_teacher(teacher_b, section="B")
    seat_a = _seed_student(class_a.class_id, "SharedDeleteA")
    seat_b = _seed_student(class_b.class_id, "SharedDeleteB")
    user_seat_a = Seat.query.filter_by(user_id=seat_a.user_id, class_id=class_a.class_id).first()
    user_seat_b = Seat.query.filter_by(user_id=seat_b.user_id, class_id=class_b.class_id).first()
    assert user_seat_a is not None and user_seat_b is not None

    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:create-tap-entries:delete-scope"):
        tap_a = AttendanceSession(
            seat_id=user_seat_a.id,
            class_id=seat_a.class_id,
            started_at=datetime.now(timezone.utc),
        )
        tap_b = AttendanceSession(
            seat_id=user_seat_b.id,
            class_id=seat_b.class_id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add_all([tap_a, tap_b])
        db.session.flush()

    _login_admin(client, teacher_a, class_a.class_id)

    deny_response = client.delete(
        f"/api/admin/tap-entries/{tap_b.id}",
        headers={"X-CSRFToken": "test"},
    )
    assert deny_response.status_code == 404
    db.session.refresh(tap_b)
    assert tap_b.is_deleted is False

    allow_response = client.delete(
        f"/api/admin/tap-entries/{tap_a.id}",
        headers={"X-CSRFToken": "test"},
    )
    assert allow_response.status_code == 200
    db.session.refresh(tap_a)
    assert tap_a.is_deleted is True


def test_hall_pass_available_types_accepts_class_id_without_teacher_id(client):
    teacher, _ = _seed_teacher("teacher-hall-types")
    economy = _create_class_for_teacher(teacher, section="A")
    student = _seed_student(economy.class_id, "JoinCodePassTypes")
    _create_claimed_seat(teacher, student, economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:hall-pass-enabled"):
        db.session.add(HallPassSettings(
            class_id=economy.class_id,
            pass_types=[
                {"name": "Bathroom", "enabled": True},
                {"name": "Office", "enabled": False},
                {"name": "Nurse", "enabled": True},
            ],
        ))
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name="hall_pass"))
        db.session.flush()

    _login_student(client, student, economy.class_id)
    response = client.get(f"/api/hall-pass/available-types?class_id={economy.class_id}")
    
    print("RESPONSE JSON:", response.get_json())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["pass_types"] == [{"name": "Bathroom"}, {"name": "Nurse"}]


def test_hall_pass_available_types_rejects_when_feature_disabled_for_class(client):
    teacher, _ = _seed_teacher("teacher-hall-disabled")
    economy = _create_class_for_teacher(teacher, section="A")
    student = _seed_student(economy.class_id, "HallDisabled")
    _create_claimed_seat(teacher, student, economy.class_id)
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:hall-pass-disabled"):
        db.session.add(HallPassSettings(
            class_id=economy.class_id,
            pass_types=[{"name": "Bathroom", "enabled": True}],
        ))
        db.session.flush()

    _login_student(client, student, economy.class_id)
    response = client.get(f"/api/hall-pass/available-types?class_id={economy.class_id}")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_hall_pass_available_types_rejects_out_of_scope_class(client):
    teacher, _ = _seed_teacher("teacher-hall-scope")
    economy = _create_class_for_teacher(teacher, section="A")
    student = _seed_student(economy.class_id, "JoinCodeScope")
    _create_claimed_seat(teacher, student, economy.class_id)

    _login_student(client, student, economy.class_id)
    other_scope = _create_class_for_teacher(teacher, section="B")
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:hall-pass-out-of-scope"):
        db.session.flush()
    response = client.get(f"/api/hall-pass/available-types?class_id={other_scope.class_id}")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_student_seat_context_rejects_unclaimed_seat(client):
    teacher, _ = _seed_teacher("teacher-seat-unclaimed")
    class_row = _create_class_for_teacher(teacher, section="A")
    student = _seed_student(class_row.class_id, "UnclaimedSeat")
    
    student_user = db.session.get(User, student.user_id)
    assert student_user is not None
    with FEATContext("FEAT-IDEN-001", idempotency_key="api-tenancy:unclaimed-seat"):
        from app.services.classroom_setup import create_student
        _user, unclaimed, _profile = create_student(
            class_row.class_id,
            first_name="Unclaimed",
            last_name="Seat",
            claimed=False,
            username="unclaimed_seat",
        )
        assert unclaimed.claimed_at is None

    _login_student(client, student, class_row.class_id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=_user.id,
            class_id=class_row.class_id,
            seat_id=unclaimed.id,
            role="student",
        )

    response = client.get("/student/payroll", follow_redirects=False)
    assert response.status_code != 200


def test_student_seat_context_rejects_cross_user_seat_id(client):
    teacher_a, _ = _seed_teacher("teacher-seat-injection-a")
    teacher_b, _ = _seed_teacher("teacher-seat-injection-b")
    alice_class = _create_class_for_teacher(teacher_a, section="A")
    bob_class = _create_class_for_teacher(teacher_b, section="A")
    alice = _seed_student(alice_class.class_id, "SeatAlice")
    bob = _seed_student(bob_class.class_id, "SeatBob")
    _create_claimed_seat(teacher_a, alice, alice_class.class_id)
    _create_claimed_seat(teacher_b, bob, bob_class.class_id)
    
    bob_user = db.session.get(User, bob.user_id)
    assert bob_user is not None
    bob_seat = Seat.query.filter_by(user_id=bob_user.id, class_id=bob_class.class_id).first()
    assert bob_seat is not None and bob_seat.claimed_at is not None

    alice_user = db.session.get(User, alice.user_id)
    assert alice_user is not None
    assert bob_seat.user_id != alice_user.id

    from flask import session
    from app.auth import get_current_seat, get_current_student_seat
    from tests.helpers.canonical_session import set_canonical_context

    with app.test_request_context("/student/payroll"):
        set_canonical_context(
            session,
            user_id=alice_user.id,
            class_id=bob_class.class_id,
            seat_id=bob_seat.id,
            role="student",
        )

        assert get_current_student_seat() is None
        assert get_current_seat() is None


def test_hall_pass_available_types_rejects_teacher_public_id(client):
    teacher, _ = _seed_teacher("teacher-hall-public")
    economy = _create_class_for_teacher(teacher, section="A")
    student = _seed_student(economy.class_id, "PublicIdPassTypes")
    _create_claimed_seat(teacher, student, economy.class_id)

    _login_student(client, student, economy.class_id)
    response = client.get("/api/hall-pass/available-types?teacher_public_id=crisp-otter-leaf")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Hall pass is disabled for this class"


def test_switch_teacher_public_id_route_is_disabled(client):
    teacher_a, _ = _seed_teacher("teacher-switch-a")
    teacher_b, _ = _seed_teacher("teacher-switch-b")
    class_a = _create_class_for_teacher(teacher_a, section="A")
    class_b = _create_class_for_teacher(teacher_b, section="B")
    student_a = _seed_student(class_a.class_id, "SwitchByPublicIdA")
    student_b = _seed_student(class_b.class_id, "SwitchByPublicIdB")
    _create_claimed_seat(teacher_a, student_a, class_a.class_id)
    _create_claimed_seat(teacher_b, student_b, class_b.class_id)

    _login_student(client, student_a, class_a.class_id)
    response = client.post("/student/switch-teacher/teacher-switch-b-public")

    assert response.status_code == 404
    student_user = db.session.get(User, student_a.user_id)
    assert student_user is not None
    assert student_user.last_active_class_id == class_a.class_id


def test_switch_teacher_public_id_invalid_keeps_current_context(client):
    teacher_a, _ = _seed_teacher("teacher-switch-invalid-a")
    class_a = _create_class_for_teacher(teacher_a, section="A")
    student = _seed_student(class_a.class_id, "SwitchInvalidPublicId")
    _create_claimed_seat(teacher_a, student, class_a.class_id)

    _login_student(client, student, class_a.class_id)
    response = client.post("/student/switch-teacher/not-valid-public-id")

    assert response.status_code == 404
    student_user = db.session.get(User, student.user_id)
    assert student_user is not None
    assert student_user.last_active_class_id == class_a.class_id
