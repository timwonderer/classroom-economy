from tests.helpers.v2_fixtures import make_admin
import pyotp
from datetime import datetime, timezone, timedelta
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.models import (
    Admin, Transaction, AttendanceSession,
    PayrollSettings, Seat, ClassEconomy, SeatAttendanceState,
    IdentityProfile, User,
)
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope


def _create_admin(username: str) -> tuple:
    """Create Admin + User pair, return (admin, secret, user).

    Note: Admin model has no user_id column. The User is linked via
    matching username_hash. We return the User object for direct use.
    """
    secret = pyotp.random_base32()
    admin = make_admin(username, secret)
    db.session.add(admin)
    db.session.flush()
    user = User(
        user_role="teacher",
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    db.session.commit()
    return admin, secret, user


def _create_student(first_name: str, teacher_user: User) -> tuple:
    """Create canonical student identity + class scope. Returns (seat, student_user, class_row)."""
    student_user = User(
        user_role="student",
        username_hash=f"student_{first_name.lower()}_hash",
        username_lookup_hash=f"student_{first_name.lower()}_lookup",
    )
    db.session.add(student_user)
    db.session.flush()

    class_row = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_user.id,
        join_code=f"T{teacher_user.id}S{student_user.id}",
        student_user_id=student_user.id,
        block="A",
        display_name="A",
        create_seat=True,
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
    )

    seat = Seat.query.filter_by(
        user_id=student_user.id, class_id=class_row.class_id, role="student"
    ).first()
    if seat:
        profile = IdentityProfile.query.filter_by(seat_id=seat.id).first()
        if profile:
            db.session.flush()

    db.session.commit()
    return seat, student_user, class_row


def _login_admin(client, user: User):
    nonce = "test_nonce_123"
    user.current_session_nonce = nonce

    class_row = (
        db.session.query(ClassEconomy.class_id, ClassEconomy.join_code)
        .filter(ClassEconomy.user_id == user.id)
        .order_by(ClassEconomy.join_code.asc())
        .first()
    )
    if class_row:
        user.last_active_class_id = class_row.class_id
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = nonce


def _build_student_detail_public_url(client, teacher_user: User, student_user: User) -> str:
    selected_class_id = teacher_user.last_active_class_id

    seat_query = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.user_id == student_user.id,
            Seat.role == "student",
            Seat.public_id.isnot(None),
            ClassEconomy.user_id == teacher_user.id,
        )
    )
    seat = None
    if selected_class_id:
        seat = seat_query.filter(Seat.class_id == selected_class_id).first()
    if not seat:
        seat = seat_query.order_by(Seat.id.asc()).first()
    assert seat is not None, "No seat found for student in teacher's classes"

    serializer = URLSafeTimedSerializer(
        client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1"
    )
    nav = serializer.dumps({
        "seat_public_id": str(seat.public_id),
        "class_id": str(seat.class_id) if seat.class_id else None,
        "admin_id": int(teacher_user.id),
    })
    return f"/admin/students/{seat.public_id}?nav={nav}"


# ---- Tests ----


def test_student_listing_scoped_to_teacher(client):
    _, _, teacher_a_user = _create_admin("teacher-a")
    _, _, teacher_b_user = _create_admin("teacher-b")
    student_a, _, _ = _create_student("Alice", teacher_a_user)
    _create_student("Bob", teacher_b_user)

    _login_admin(client, teacher_a_user)

    response = client.get("/admin/students")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert student_a.display_first_name in body
    assert "Bob" not in body


def test_student_detail_forbids_cross_tenant_access(client):
    _, _, teacher_a_user = _create_admin("teacher-a")
    _, _, teacher_b_user = _create_admin("teacher-b")
    _create_student("Alice", teacher_a_user)
    student_b, _, _ = _create_student("Bob", teacher_b_user)

    _login_admin(client, teacher_a_user)

    response = client.get(f"/admin/students/{student_b.id}")
    assert response.status_code == 404


def test_shared_student_accessible_to_multiple_teachers(client):
    _, _, teacher_a_user = _create_admin("teacher-a")
    _, _, teacher_b_user = _create_admin("teacher-b")
    shared_student, shared_student_user, _ = _create_student("Shared", teacher_a_user)

    # Give teacher B their own class with the shared student
    create_class_scope(
        teacher=None,
        teacher_user_id=teacher_b_user.id,
        join_code=f"T{teacher_b_user.id}SHARED",
        student=shared_student,
        student_user_id=shared_student_user.id,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()

    _login_admin(client, teacher_b_user)

    detail_url = _build_student_detail_public_url(client, teacher_b_user, shared_student_user)
    detail_response = client.get(detail_url, follow_redirects=True)
    list_response = client.get("/admin/students")

    assert detail_response.status_code == 200
    assert "Shared" in list_response.get_data(as_text=True)


def test_student_detail_recovers_from_stale_class_context(client):
    _, _, teacher_user = _create_admin("teacher-a")
    student_a, student_a_user, _ = _create_student("Alice", teacher_user)
    student_b, student_b_user, _ = _create_student("Bob", teacher_user)

    class_a = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_user.id,
        join_code="JOINA",
        student=student_a,
        student_user_id=student_a_user.id,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_b = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_user.id,
        join_code="JOINB",
        student=student_b,
        student_user_id=student_b_user.id,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()

    seat_a = Seat.query.filter_by(
        user_id=student_a_user.id, class_id=class_a.class_id, role="student"
    ).first()
    assert seat_a is not None

    from app.feats.base import FEATContext
    with FEATContext("FEAT-ADMN-001"):
        db.session.add(
            Transaction(
                user_id=student_a_user.id,
                seat_id=seat_a.id,
                amount=25,
                type="bonus",
                account_type="checking",
                description="Scoped tx",
                join_code="JOINA",
                class_id=class_a.class_id,
            ),
        )
        db.session.flush()

    _login_admin(client, teacher_user)

    # Point session to class B (stale context for student A)
    teacher_user.last_active_class_id = class_b.class_id
    db.session.commit()

    serializer = URLSafeTimedSerializer(
        client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1"
    )
    nav = serializer.dumps({
        "seat_public_id": str(seat_a.public_id),
        "class_id": str(class_a.class_id),
        "admin_id": int(teacher_user.id),
    })
    detail_url = f"/admin/students/{seat_a.public_id}?nav={nav}"
    response = client.get(detail_url, follow_redirects=True)
    assert response.status_code == 200


def test_enforce_daily_limits_ignores_other_join_code_activity(client):
    _, _, teacher_a_user = _create_admin("teacher-a")
    _, _, teacher_b_user = _create_admin("teacher-b")
    shared_student, shared_student_user, _ = _create_student("SharedLimit", teacher_a_user)

    class_scope_a = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_a_user.id,
        join_code="JOINA",
        student=shared_student,
        student_user_id=shared_student_user.id,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_scope_b = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_b_user.id,
        join_code="JOINB",
        student=shared_student,
        student_user_id=shared_student_user.id,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()

    seat_b = Seat.query.filter_by(
        user_id=shared_student_user.id, class_id=class_scope_b.class_id, role="student"
    ).first()
    assert seat_b is not None

    db.session.add_all([
        PayrollSettings(
            class_id=class_scope_a.class_id,
            block="A",
            is_active=True,
            settings_mode="simple",
            daily_limit_hours=0.001,  # ~3.6 seconds
            pay_rate=0.25,
            payroll_frequency_days=14,
        ),
        AttendanceSession(
            seat_id=seat_b.id,
            class_id=class_scope_b.class_id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            start_reason="Start work",
        ),
        SeatAttendanceState(
            seat_id=seat_b.id,
            class_id=class_scope_b.class_id,
            is_active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a_user)
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    # Teacher A's classes have no active states, so nothing checked
    assert payload["checked"] == 0
    assert payload["tapped_out"] == []


def test_enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    _, _, teacher_user = _create_admin("teacher-a")
    student, student_user, _ = _create_student("AliceLimit", teacher_user)

    class_scope = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_user.id,
        join_code="JOINA",
        student=student,
        student_user_id=student_user.id,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()

    seat = Seat.query.filter_by(
        user_id=student_user.id, class_id=class_scope.class_id, role="student"
    ).first()
    assert seat is not None

    db.session.add_all([
        PayrollSettings(
            class_id=class_scope.class_id,
            block="A",
            is_active=True,
            settings_mode="simple",
            daily_limit_hours=0.001,
            pay_rate=0.25,
            payroll_frequency_days=14,
        ),
        AttendanceSession(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            start_reason="Start work",
        ),
        SeatAttendanceState(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            is_active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_user)
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] >= 1
    assert len(payload["tapped_out"]) >= 1

    att_state = SeatAttendanceState.query.filter_by(
        seat_id=seat.id, class_id=class_scope.class_id
    ).first()
    assert att_state is not None
    assert att_state.done_for_day_date is not None

    inactive_count = AttendanceSession.query.filter(
        AttendanceSession.seat_id == seat.id,
        AttendanceSession.class_id == class_scope.class_id,
        AttendanceSession.end_reason.ilike("Daily limit%"),
    ).count()
    assert inactive_count == 1


def test_student_detail_public_url_requires_nav_token(client):
    _, _, teacher_user = _create_admin("teacher-public")
    _, student_user, _ = _create_student("PublicDetail", teacher_user)

    _login_admin(client, teacher_user)

    nav_url = _build_student_detail_public_url(client, teacher_user, student_user)
    ok = client.get(nav_url, follow_redirects=False)
    assert ok.status_code == 200

    public_path = nav_url.split("?", 1)[0]
    direct = client.get(public_path, follow_redirects=False)
    assert direct.status_code == 404


def test_student_detail_public_id_is_seat_scoped_for_shared_student(client):
    _, _, teacher_a_user = _create_admin("teacher-seat-scope-a")
    _, _, teacher_b_user = _create_admin("teacher-seat-scope-b")
    shared_student, shared_student_user, _ = _create_student("SharedSeatScope", teacher_a_user)

    class_b = create_class_scope(
        teacher=None,
        teacher_user_id=teacher_b_user.id,
        join_code="SHAREDSEATB",
        student=shared_student,
        student_user_id=shared_student_user.id,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()

    class_a = ClassEconomy.query.filter(
        ClassEconomy.user_id == teacher_a_user.id,
        ClassEconomy.class_id != class_b.class_id,
    ).first()
    seat_a = Seat.query.filter_by(
        user_id=shared_student_user.id, class_id=class_a.class_id, role="student"
    ).first()
    seat_b = Seat.query.filter_by(
        user_id=shared_student_user.id, class_id=class_b.class_id, role="student"
    ).first()
    assert seat_a is not None
    assert seat_b is not None
    assert seat_a.public_id != seat_b.public_id

    _login_admin(client, teacher_a_user)
    own_detail_url = _build_student_detail_public_url(client, teacher_a_user, shared_student_user)
    assert f"/admin/students/{seat_a.public_id}?" in own_detail_url
    assert client.get(own_detail_url, follow_redirects=False).status_code == 200

    serializer = URLSafeTimedSerializer(
        client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1"
    )
    forged_nav = serializer.dumps({
        "seat_public_id": str(seat_b.public_id),
        "class_id": str(seat_b.class_id),
        "admin_id": int(teacher_a_user.id),
    })
    cross_class_response = client.get(
        f"/admin/students/{seat_b.public_id}?nav={forged_nav}",
        follow_redirects=False,
    )
    assert cross_class_response.status_code == 404
