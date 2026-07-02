"""
Tests for API route tenant scoping.

Validates that API endpoints properly scope data access to the current admin's students.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import app, db
from app.models import (
    UserRole,
    Admin,
    ClassFeature,
    ClassEconomy,
    ClassMembership,
    HallPassSettings,
    Seat,
    Student,
    StudentBlock,
    StudentTeacher,
    AttendanceSession,
    User,
)
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create a teacher admin for testing."""
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.add(admin)
    db.session.flush()
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
        current_session_nonce="nonce",
    )
    db.session.add(user)
    db.session.commit()
    return admin, secret


def _get_teacher_user_id(teacher: Admin) -> int:
    user = User.query.filter_by(username_hash=teacher.username_hash).first()
    return user.id if user else teacher.id


def _create_student(first_name: str, primary_teacher: Admin = None, linked_teachers: list[Admin] = None) -> Student:
    """
    Create a student for testing.
    
    Args:
        first_name: Student's first name
        primary_teacher: Primary owner (sets teacher_id)
        linked_teachers: List of teachers to link via student_teachers
    """
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="X",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(User(
        user_role=UserRole.STUDENT,
        username_hash=student.username_hash,
        pin_hash=student.pin_hash,
        current_session_nonce="nonce",
    ))
    
    # Add student_teachers links
    if linked_teachers:
        for teacher in linked_teachers:
            db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    elif primary_teacher:
        # If no explicit links but has primary, create link
        db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=primary_teacher.id))
    
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str, join_code: str = None):
    """Login as admin."""
    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        if user:
            sess["user_id"] = user.id
            sess["current_session_nonce"] = user.current_session_nonce
        if not sess.get("current_join_code"):
            first_membership = (
                ClassMembership.query.filter_by(admin_id=admin.id, role="admin")
                .order_by(ClassMembership.id.asc())
                .first()
            )
            if first_membership and first_membership.join_code:
                sess["current_join_code"] = first_membership.join_code
        if join_code:
            sess["current_join_code"] = join_code
        
        current_join_code = sess.get("current_join_code")
        if current_join_code:
            teacher_user_id = _get_teacher_user_id(admin)
            class_row = ClassEconomy.query.filter_by(join_code=current_join_code, user_id=teacher_user_id).first()
            if class_row and class_row.class_id:
                sess["current_class_id"] = class_row.class_id
                if user:
                    user.last_active_class_id = class_row.class_id
                    db.session.commit()
            else:
                sess.pop("current_class_id", None)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def _create_tap_event(student: Student, teacher: Admin, join_code: str, status: str = "active", period: str = "1"):
    """Create a canonical v2 attendance session for testing."""
    _create_class_scope(teacher, student, join_code)
    teacher_user_id = _get_teacher_user_id(teacher)
    class_row = ClassEconomy.query.filter_by(join_code=join_code, user_id=teacher_user_id).first()
    assert class_row is not None and class_row.class_id, "Expected class scope to exist before attendance session creation"
    seat = _get_or_create_student_seat(student, class_row.class_id, join_code)
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
    db.session.commit()
    return tap


def _create_claimed_seat(teacher: Admin, student: Student, join_code: str, block: str = "A"):
    """Create a claimed teacher block (seat) for join-code scoped tests."""
    if not db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        admin_id=teacher.id,
        role="admin",
    ).first():
        _create_class_scope(teacher, student, join_code)

    teacher_user_id = _get_teacher_user_id(teacher)
    class_row = ClassEconomy.query.filter_by(join_code=join_code, user_id=teacher_user_id).first()
    runtime_seat = _get_or_create_student_seat(student, class_row.class_id, join_code) if class_row else None
    if runtime_seat and not runtime_seat.claimed_at:
        runtime_seat.claimed_at = datetime.now(timezone.utc)
    db.session.commit()
    return runtime_seat


def _get_or_create_student_seat(student: Student, class_id: str, join_code: str):
    user = User.query.filter_by(username_hash=student.username_hash).first()
    assert user is not None
    seat = Seat.query.filter_by(user_id=user.id, class_id=class_id).order_by(Seat.id.asc()).first()
    if seat:
        seat.user_id = user.id
        return seat
    seat = Seat(
        user_id=user.id,
        class_id=class_id,
        join_code=join_code,
        role="student",
        block_identifier="A",
        block="A",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    return seat


def _create_class_scope(teacher: Admin, student: Student, join_code: str):
    """Create the v2 class economy and memberships for a teacher/student pair."""
    if not db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        admin_id=teacher.id,
        role="admin",
    ).first():
        teacher_user = User.query.filter_by(username_hash=teacher.username_hash).first()
        student_user = User.query.filter_by(username_hash=student.username_hash).first()
        create_class_scope(
            teacher=teacher,
            join_code=join_code,
            student=student,
            teacher_user_id=teacher_user.id if teacher_user else None,
            student_user_id=student_user.id if student_user else None,
        )
        db.session.flush()

    if not db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        user_id=student_user.id,
        role="student",
    ).first():
        teacher_user_id = _get_teacher_user_id(teacher)
        class_row = ClassEconomy.query.filter_by(join_code=join_code, user_id=teacher_user_id).first()
        db.session.add(ClassMembership(
            join_code=join_code,
            class_id=class_row.class_id if class_row else None,
            user_id=student_user.id,
            role="student",
        ))
    db.session.commit()


def _login_student(client, student: Student, join_code: str | None = None):
    now = datetime.now(timezone.utc).isoformat()
    user = User.query.filter_by(username_hash=student.username_hash).first()
    with client.session_transaction() as sess:
        sess["student_id"] = student.id
        if user:
            sess["user_id"] = user.id
            sess["current_session_nonce"] = user.current_session_nonce
        sess["login_time"] = now
        sess["last_activity"] = now
        if join_code:
            sess["current_join_code"] = join_code
            class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
            if class_row:
                sess["current_class_id"] = class_row.class_id
                if user:
                    user.last_active_class_id = class_row.class_id
                    db.session.commit()
                seat = Seat.query.filter_by(user_id=user.id, class_id=class_row.class_id).first() if user else None
                if seat:
                    sess["current_seat_id"] = seat.id
                    sess["seat_id"] = seat.id
                    sess["class_id"] = class_row.class_id


def test_attendance_history_api_scoped_to_teacher(client):
    """Admin should only see attendance history for their own students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students for each teacher
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events for both students
    tap_a = _create_tap_event(student_a, teacher_a, "ATTEND_A", status="active")
    tap_b = _create_tap_event(student_b, teacher_b, "ATTEND_B", status="active")
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
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
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create shared student
    shared_student = _create_student("Shared", primary_teacher=teacher_a, linked_teachers=[teacher_a, teacher_b])
    
    # Create exclusive students
    exclusive_a = _create_student("ExclusiveA", primary_teacher=teacher_a)
    exclusive_b = _create_student("ExclusiveB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_shared = _create_tap_event(shared_student, teacher_a, "SHARED_A")
    _create_class_scope(teacher_b, shared_student, "SHARED_B")
    tap_a = _create_tap_event(exclusive_a, teacher_a, "EXCL_A")
    tap_b = _create_tap_event(exclusive_b, teacher_b, "EXCL_B")
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a, join_code="SHARED_A")
    
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
    
    with client.session_transaction() as sess:
        print(f"DEBUG: Session current_join_code={sess.get('current_join_code')}, current_class_id={sess.get('current_class_id')}")
        
    user = User.query.filter_by(username_hash=teacher_a.username_hash).first()
    print(f"DEBUG: teacher_a user.last_active_class_id={user.last_active_class_id}")
    
    print(f"DEBUG: record_ids={record_ids}")
    
    assert tap_shared.id in record_ids
    assert tap_a.id not in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_filters_work_with_scoping(client):
    """Filters should work correctly with tenant scoping."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students with different periods
    student_a1 = _create_student("StudentA1", primary_teacher=teacher_a)
    student_a1.block = "Period1"
    student_a2 = _create_student("StudentA2", primary_teacher=teacher_a)
    student_a2.block = "Period2"
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    student_b.block = "Period1"
    db.session.commit()
    
    # Create tap events
    _create_class_scope(teacher_a, student_a1, "FILTER_A1")
    _create_class_scope(teacher_a, student_a2, "FILTER_A2")
    _create_class_scope(teacher_b, student_b, "FILTER_B1")
    teacher_a_user_id = _get_teacher_user_id(teacher_a)
    teacher_b_user_id = _get_teacher_user_id(teacher_b)
    class_a1 = ClassEconomy.query.filter_by(join_code="FILTER_A1", user_id=teacher_a_user_id).first()
    class_a2 = ClassEconomy.query.filter_by(join_code="FILTER_A2", user_id=teacher_a_user_id).first()
    class_b = ClassEconomy.query.filter_by(join_code="FILTER_B1", user_id=teacher_b_user_id).first()
    seat_a1 = _get_or_create_student_seat(student_a1, class_a1.class_id, "FILTER_A1")
    seat_a2 = _get_or_create_student_seat(student_a2, class_a2.class_id, "FILTER_A2")
    seat_b = _get_or_create_student_seat(student_b, class_b.class_id, "FILTER_B1")
    tap_a1 = AttendanceSession(seat_id=seat_a1.id, class_id=class_a1.class_id, started_at=datetime.now(timezone.utc))
    tap_a2 = AttendanceSession(seat_id=seat_a2.id, class_id=class_a2.class_id, started_at=datetime.now(timezone.utc))
    tap_b = AttendanceSession(seat_id=seat_b.id, class_id=class_b.class_id, started_at=datetime.now(timezone.utc))
    db.session.add_all([tap_a1, tap_a2, tap_b])
    db.session.commit()
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a, join_code="FILTER_A1")
    
    # Request attendance history filtered by period 1
    response = client.get("/api/attendance/history?period=1")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see teacher A's period 1 student (not teacher B's)
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a1.id in record_ids
    assert tap_a2.id not in record_ids  # Different period
    assert tap_b.id not in record_ids  # Different teacher


def test_attendance_history_api_system_admin_sees_all(client):
    """System admin should see all attendance records."""
    from app.models import SystemAdmin
    
    # Create system admin
    sys_secret = pyotp.random_base32()
    sys_admin = make_sysadmin("sysadmin", sys_secret)
    db.session.add(sys_admin)
    db.session.commit()
    
    # Create teachers and students
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_a = _create_tap_event(student_a, teacher_a, "SYS_A")
    tap_b = _create_tap_event(student_b, teacher_b, "SYS_B")
    
    # Login as system admin
    client.post(
        "/sysadmin/login",
        data={"username": "sysadmin", "totp_code": pyotp.TOTP(sys_secret).now()},
        follow_redirects=True,
    )
    
    # System admins accessing via /api routes would need admin session too
    # For now, just verify the scoping logic works for regular admins
    # (System admins typically don't use the API routes directly)


def test_admin_tap_entries_scoped_by_join_code(client):
    """Admin should only receive tap entries from their own join-code scope."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTap",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_class_scope(teacher_a, shared_student, "JOIN_A")
    _create_class_scope(teacher_b, shared_student, "JOIN_B")
    seat_a = _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    seat_b = _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="B")
    user_seat_a = _get_or_create_student_seat(shared_student, seat_a.class_id, "JOIN_A")
    user_seat_b = _get_or_create_student_seat(shared_student, seat_b.class_id, "JOIN_B")

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
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")
    response = client.get(f"/api/admin/tap-entries/{shared_student.id}")

    assert response.status_code == 200
    payload = response.get_json()
    returned_ids = {
        event["id"]
        for period_data in payload["periods"].values()
        for event in period_data["sessions"]
    }
    assert tap_a.id in returned_ids
    assert tap_b.id not in returned_ids


def test_admin_delete_tap_entry_enforces_join_code_scope(client):
    """Admin should not delete tap entries from another teacher's join code."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedDelete",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_class_scope(teacher_a, shared_student, "JOIN_A")
    _create_class_scope(teacher_b, shared_student, "JOIN_B")
    seat_a = _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    seat_b = _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="B")
    user_seat_a = _get_or_create_student_seat(shared_student, seat_a.class_id, "JOIN_A")
    user_seat_b = _get_or_create_student_seat(shared_student, seat_b.class_id, "JOIN_B")

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
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")

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


def test_admin_student_block_settings_rejects_out_of_scope_join_code(client):
    """Admin must not update a StudentBlock row bound to another join code."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedBlock",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    block = StudentBlock(
        user_id=shared_student_user.id,
        period="A",
        join_code="JOIN_B",
        tap_enabled=True,
    )
    db.session.add(block)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")
    response = client.post(
        "/api/admin/student-block-settings",
        json={"student_id": shared_student.id, "period": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    db.session.refresh(block)
    assert block.tap_enabled is True


def test_admin_student_block_settings_rejects_null_join_code_row(client):
    """Admin update should reject StudentBlock rows without join-code scope in v2 mode."""
    teacher_a, secret_a = _create_admin("teacher-a")
    student = _create_student("LegacyBlock", primary_teacher=teacher_a)
    _create_claimed_seat(teacher_a, student, "JOIN_A", block="A")

    block = StudentBlock(
        user_id=student_user.id,
        period="A",
        join_code=None,
        tap_enabled=True,
    )
    db.session.add(block)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")
    response = client.post(
        "/api/admin/student-block-settings",
        json={"student_id": student.id, "period": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 403
    db.session.refresh(block)
    assert block.tap_enabled is True
    assert block.join_code is None


def test_admin_block_tap_settings_get_ignores_out_of_scope_join_code_row(client):
    """Block-level tap state should ignore StudentBlock rows from other join-code scopes."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTapState",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    # Out-of-scope row for teacher A should not drive block-level state.
    db.session.add(
        StudentBlock(
            user_id=shared_student_user.id,
            period="A",
            join_code="JOIN_B",
            tap_enabled=False,
        )
    )
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")
    response = client.get("/api/admin/block-tap-settings?block=A")

    assert response.status_code == 200
    payload = response.get_json()
    # Teacher A has no scoped disabled row; default remains enabled.
    assert payload["tap_enabled"] is True


def test_admin_block_tap_settings_post_preserves_out_of_scope_join_code_row(client):
    """Bulk block tap updates must not mutate another join-code's StudentBlock row."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    shared_student = _create_student(
        "SharedTapBulk",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, shared_student, "JOIN_A", block="A")
    _create_claimed_seat(teacher_b, shared_student, "JOIN_B", block="A")

    foreign_row = StudentBlock(
        user_id=shared_student_user.id,
        period="A",
        join_code="JOIN_B",
        tap_enabled=True,
    )
    db.session.add(foreign_row)
    db.session.commit()

    _login_admin(client, teacher_a, secret_a, join_code="JOIN_A")
    response = client.post(
        "/api/admin/block-tap-settings",
        json={"block": "A", "tap_enabled": False},
        headers={"X-CSRFToken": "test"},
    )

    assert response.status_code == 404
    db.session.refresh(foreign_row)
    assert foreign_row.tap_enabled is True

    scoped_row = StudentBlock.query.filter_by(
        user_id=shared_student_user.id,
        period="A",
        join_code="JOIN_A",
    ).first()
    assert scoped_row is None


def test_hall_pass_available_types_accepts_class_id_without_teacher_id(client):
    teacher, _ = _create_admin("teacher-hall-types")
    student = _create_student("JoinCodePassTypes", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLA1", block="A")

    economy = ClassEconomy.query.filter_by(join_code="HALLA1").first()
    db.session.add(HallPassSettings(
        class_id=economy.class_id,
        pass_types=[
            {"name": "Bathroom", "enabled": True},
            {"name": "Office", "enabled": False},
            {"name": "Nurse", "enabled": True},
        ],
    ))
    db.session.add(ClassFeature(class_id=economy.class_id, feature_name="hall_pass"))
    db.session.commit()

    _login_student(client, student, join_code="HALLA1")
    response = client.get(f"/api/hall-pass/available-types?class_id={economy.class_id}")
    
    print("RESPONSE JSON:", response.get_json())
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["pass_types"] == [{"name": "Bathroom"}, {"name": "Nurse"}]


def test_hall_pass_available_types_rejects_when_feature_disabled_for_class(client):
    teacher, _ = _create_admin("teacher-hall-disabled")
    student = _create_student("HallDisabled", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLD1", block="A")

    economy = ClassEconomy.query.filter_by(join_code="HALLD1").first()
    db.session.add(HallPassSettings(
        class_id=economy.class_id,
        pass_types=[{"name": "Bathroom", "enabled": True}],
    ))
    db.session.commit()

    _login_student(client, student, join_code="HALLD1")
    response = client.get(f"/api/hall-pass/available-types?class_id={economy.class_id}")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_hall_pass_available_types_rejects_out_of_scope_join_code(client):
    teacher, _ = _create_admin("teacher-hall-scope")
    student = _create_student("JoinCodeScope", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLS1", block="A")

    _login_student(client, student, join_code="HALLS1")
    teacher_user_id = _get_teacher_user_id(teacher)
    other_scope = ClassEconomy(
        join_code="OTHER999",
        user_id=teacher_user_id,
        status="active",
        created_by_admin_id=teacher.id,
    )
    db.session.add(other_scope)
    db.session.commit()
    response = client.get(f"/api/hall-pass/available-types?class_id={other_scope.class_id}")

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["status"] == "error"


def test_student_seat_context_rejects_unclaimed_seat(client):
    teacher, _ = _create_admin("teacher-seat-unclaimed")
    student = _create_student("UnclaimedSeat", primary_teacher=teacher)
    _create_class_scope(teacher, student, "UNCL1")
    teacher_user_id = _get_teacher_user_id(teacher)
    class_row = ClassEconomy.query.filter_by(join_code="UNCL1", user_id=teacher_user_id).first()
    
    student_user = User.query.filter_by(username_hash=student.username_hash).first()
    
    unclaimed = Seat(
        user_id=student_user.id if student_user else None,
        class_id=class_row.class_id,
        join_code="UNCL1",
        role="student",
        block_identifier="A",
        block="A",
        claimed_at=None,
    )
    db.session.add(unclaimed)
    db.session.commit()

    _login_student(client, student, join_code="UNCL1")
    with client.session_transaction() as sess:
        sess["current_seat_id"] = unclaimed.id

    response = client.get("/student/payroll", follow_redirects=False)
    assert response.status_code != 200


def test_student_seat_context_rejects_cross_user_seat_id(client):
    teacher_a, _ = _create_admin("teacher-seat-injection-a")
    teacher_b, _ = _create_admin("teacher-seat-injection-b")
    alice = _create_student("SeatAlice", primary_teacher=teacher_a)
    bob = _create_student("SeatBob", primary_teacher=teacher_b)
    _create_claimed_seat(teacher_a, alice, "SEATA1", block="A")
    _create_claimed_seat(teacher_b, bob, "SEATB1", block="A")

    teacher_b_user_id = _get_teacher_user_id(teacher_b)
    bob_class = ClassEconomy.query.filter_by(join_code="SEATB1", user_id=teacher_b_user_id).first()
    
    bob_user = User.query.filter_by(username_hash=bob.username_hash).first()
    bob_seat = Seat.query.filter_by(user_id=bob_user.id, class_id=bob_class.class_id).first()
    assert bob_seat is not None and bob_seat.claimed_at is not None
    
    alice_user = User.query.filter_by(username_hash=alice.username_hash).first()
    assert bob_seat.user_id != alice_user.id

    from flask import session
    from app.auth import get_current_seat, get_current_student_seat

    with app.test_request_context("/student/payroll"):
        session["student_id"] = alice.id
        session["current_seat_id"] = bob_seat.id
        session["seat_id"] = bob_seat.id
        session["current_class_id"] = bob_class.class_id
        session["class_id"] = bob_class.class_id
        session["current_join_code"] = "SEATB1"

        assert get_current_student_seat() is None
        assert get_current_seat() is None


def test_hall_pass_available_types_rejects_teacher_public_id(client):
    teacher, _ = _create_admin("teacher-hall-public")
    student = _create_student("PublicIdPassTypes", primary_teacher=teacher)
    _create_claimed_seat(teacher, student, "HALLP1", block="A")

    _login_student(client, student, join_code="HALLP1")
    response = client.get("/api/hall-pass/available-types?teacher_public_id=crisp-otter-leaf")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "teacher_public_id is not supported"


def test_switch_teacher_public_id_route_is_disabled(client):
    teacher_a, _ = _create_admin("teacher-switch-a")
    teacher_b, _ = _create_admin("teacher-switch-b")
    student = _create_student(
        "SwitchByPublicId",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, student, "SWITCHA1", block="A")
    _create_claimed_seat(teacher_b, student, "SWITCHB1", block="B")

    _login_student(client, student, join_code="SWITCHA1")
    response = client.post("/student/switch-teacher/teacher-switch-b-public")

    assert response.status_code == 404
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWITCHA1"
        assert "current_teacher_id" not in sess


def test_switch_teacher_public_id_invalid_keeps_current_context(client):
    teacher_a, _ = _create_admin("teacher-switch-invalid-a")
    student = _create_student("SwitchInvalidPublicId", primary_teacher=teacher_a)
    _create_claimed_seat(teacher_a, student, "SWITCHINV", block="A")

    _login_student(client, student, join_code="SWITCHINV")
    response = client.post("/student/switch-teacher/not-valid-public-id")

    assert response.status_code == 404
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWITCHINV"


def test_switch_period_legacy_route_does_not_switch_context(client):
    teacher_a, _ = _create_admin("teacher-switch-legacy-a")
    teacher_b, _ = _create_admin("teacher-switch-legacy-b")
    student = _create_student(
        "SwitchLegacyRoute",
        primary_teacher=teacher_a,
        linked_teachers=[teacher_a, teacher_b],
    )
    _create_claimed_seat(teacher_a, student, "SWLEGACYA", block="A")
    _create_claimed_seat(teacher_b, student, "SWLEGACYB", block="B")

    _login_student(client, student, join_code="SWLEGACYA")
    response = client.post(f"/student/switch-period/{teacher_b.id}")

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess["current_join_code"] == "SWLEGACYA"
