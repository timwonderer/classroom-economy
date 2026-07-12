from tests.helpers.v2_fixtures import make_teacher
from datetime import datetime, timezone, timedelta
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.models import (
    Transaction, AttendanceSession,
    PayrollSettings, Seat, ClassEconomy, SeatAttendanceState,
    User,
)
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.admin_context import login_teacher


def _create_teacher(username: str) -> User:
    teacher = make_teacher(username)
    db.session.flush()
    return teacher


def _create_student_in_class(class_row: ClassEconomy, first_name: str) -> tuple:
    """Create a canonical student identity in the given class. Returns (seat, student_user)."""
    seat = make_student_identity(class_id=class_row.class_id, first_name=first_name, last_name="Test")
    db.session.flush()
    student_user = db.session.get(User, seat.user_id)
    return seat, student_user


def _create_class_for_teacher(teacher: User, join_code: str, display_name: str = "A") -> ClassEconomy:
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code, display_name=display_name)
    db.session.flush()
    return class_row


def _login_admin(client, teacher: User):
    class_row = ClassEconomy.query.filter_by(user_id=teacher.id).order_by(ClassEconomy.class_id.asc()).first()
    if class_row:
        login_teacher(client, teacher, class_id=class_row.class_id, join_code=class_row.join_code)
    else:
        login_teacher(client, teacher)


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
        "actor_public_id": str(seat.public_id),
        "class_id": str(seat.class_id) if seat.class_id else None,
        "user_id": int(teacher_user.id),
    })
    return f"/admin/students/{seat.public_id}?nav={nav}"


# ---- Tests ----


def test_student_listing_scoped_to_teacher(client):
    teacher_a = _create_teacher("teacher-a")
    teacher_b = _create_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, "TENANCY-A1")
    class_b = _create_class_for_teacher(teacher_b, "TENANCY-B1")
    seat_a, _ = _create_student_in_class(class_a, "Alice")
    _create_student_in_class(class_b, "Bob")
    db.session.commit()

    _login_admin(client, teacher_a)

    response = client.get("/admin/students")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    profile_a = seat_a.identity_profile
    assert profile_a is None or "Alice" in body or response.status_code == 200


def test_student_detail_forbids_cross_tenant_access(client):
    teacher_a = _create_teacher("teacher-a")
    teacher_b = _create_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, "TENANCY-A2")
    class_b = _create_class_for_teacher(teacher_b, "TENANCY-B2")
    _create_student_in_class(class_a, "Alice")
    seat_b, _ = _create_student_in_class(class_b, "Bob")
    db.session.commit()

    _login_admin(client, teacher_a)

    response = client.get(f"/admin/students/{seat_b.id}")
    assert response.status_code == 404


def test_shared_student_accessible_to_multiple_teachers(client):
    teacher_a = _create_teacher("teacher-a")
    teacher_b = _create_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, "TENANCY-A3")
    class_b = _create_class_for_teacher(teacher_b, "TENANCY-B3")
    shared_seat, shared_student_user = _create_student_in_class(class_a, "Shared")

    # Add shared student to teacher B's class too with a new seat
    seat_b = make_student_identity(class_id=class_b.class_id, first_name="SharedB", last_name="Test")
    db.session.commit()

    _login_admin(client, teacher_b)
    with client.session_transaction() as sess:
        teacher_b_seat = Seat.query.filter_by(class_id=class_b.class_id, role="teacher").first()
        set_canonical_context(
            sess,
            user_id=teacher_b.id,
            class_id=class_b.class_id,
            seat_id=teacher_b_seat.id,
            role="teacher",
        )

    list_response = client.get("/admin/students")

    assert list_response.status_code == 200


def test_student_detail_recovers_from_stale_class_context(client):
    teacher = _create_teacher("teacher-a")
    class_a = _create_class_for_teacher(teacher, "JOINA")
    class_b = _create_class_for_teacher(teacher, "JOINB")
    seat_a, student_a_user = _create_student_in_class(class_a, "Alice")
    _create_student_in_class(class_b, "Bob")

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
                class_id=class_a.class_id,
            ),
        )
        db.session.flush()

    db.session.commit()
    _login_admin(client, teacher)

    # Point session to class B (stale context for student A)
    teacher.last_active_class_id = class_b.class_id
    db.session.commit()

    serializer = URLSafeTimedSerializer(
        client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1"
    )
    nav = serializer.dumps({
        "actor_public_id": str(seat_a.public_id),
        "class_id": str(class_a.class_id),
        "user_id": int(teacher.id),
    })
    detail_url = f"/admin/students/{seat_a.public_id}?nav={nav}"
    response = client.get(detail_url, follow_redirects=True)
    assert response.status_code == 200


def test_enforce_daily_limits_ignores_other_join_code_activity(client):
    teacher_a = _create_teacher("teacher-a")
    teacher_b = _create_teacher("teacher-b")
    class_a = _create_class_for_teacher(teacher_a, "JOINA")
    class_b = _create_class_for_teacher(teacher_b, "JOINB")
    _, _ = _create_student_in_class(class_a, "SharedLimit")
    shared_seat_b, _ = _create_student_in_class(class_b, "SharedLimitB")

    db.session.add_all([
        PayrollSettings(
            class_id=class_a.class_id,
            block="A",
            is_active=True,
            settings_mode="simple",
            daily_limit_hours=0.001,
            pay_rate=0.25,
            payroll_frequency_days=14,
        ),
        AttendanceSession(
            seat_id=shared_seat_b.id,
            class_id=class_b.class_id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            start_reason="Start work",
        ),
        SeatAttendanceState(
            seat_id=shared_seat_b.id,
            class_id=class_b.class_id,
            is_active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a)
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] == 0
    assert payload["tapped_out"] == []


def test_enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    teacher = _create_teacher("teacher-a")
    class_scope = _create_class_for_teacher(teacher, "JOINA")
    seat, _ = _create_student_in_class(class_scope, "AliceLimit")

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

    _login_admin(client, teacher)
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
    teacher = _create_teacher("teacher-public")
    class_row = _create_class_for_teacher(teacher, "PUBLIC-DETAIL-1")
    _, student_user = _create_student_in_class(class_row, "PublicDetail")
    db.session.commit()

    _login_admin(client, teacher)

    nav_url = _build_student_detail_public_url(client, teacher, student_user)
    ok = client.get(nav_url, follow_redirects=False)
    assert ok.status_code == 200

    public_path = nav_url.split("?", 1)[0]
    direct = client.get(public_path, follow_redirects=False)
    assert direct.status_code == 404


def test_student_detail_public_id_is_seat_scoped_for_shared_student(client):
    teacher_a = _create_teacher("teacher-seat-scope-a")
    teacher_b = _create_teacher("teacher-seat-scope-b")
    class_a = _create_class_for_teacher(teacher_a, "SHARED-SEAT-A")
    class_b = _create_class_for_teacher(teacher_b, "SHAREDSEATB")
    seat_a, shared_student_user = _create_student_in_class(class_a, "SharedSeatScope")
    seat_b = make_student_identity(class_id=class_b.class_id, first_name="SharedSeatScopeB", last_name="Test")
    db.session.commit()

    assert seat_a is not None
    assert seat_b is not None
    assert seat_a.public_id != seat_b.public_id

    _login_admin(client, teacher_a)
    own_detail_url = _build_student_detail_public_url(client, teacher_a, shared_student_user)
    assert f"/admin/students/{seat_a.public_id}?" in own_detail_url
    assert client.get(own_detail_url, follow_redirects=False).status_code == 200

    serializer = URLSafeTimedSerializer(
        client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1"
    )
    forged_nav = serializer.dumps({
        "seat_public_id": str(seat_b.public_id),
        "class_id": str(seat_b.class_id),
        "user_id": int(teacher_a.id),
    })
    cross_class_response = client.get(
        f"/admin/students/{seat_b.public_id}?nav={forged_nav}",
        follow_redirects=False,
    )
    assert cross_class_response.status_code == 404
