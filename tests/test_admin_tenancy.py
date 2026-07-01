from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
import re
from datetime import datetime, timezone, timedelta
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.models import Admin, Student, StudentTeacher, Transaction, AttendanceSession, StudentBlock, PayrollSettings, Seat, ClassEconomy, SeatAttendanceState
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.class_scope import create_class_scope


def _create_admin(username: str) -> tuple[Admin, str]:
    from app.models import User
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
    admin.user_id = user.id
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, teacher: Admin) -> Student:
    from app.models import IdentityProfile
    salt = get_random_salt()
    
    identity = IdentityProfile(
        profile_type="student",
        first_name=first_name,
        last_name="A"
    )
    db.session.add(identity)
    db.session.flush()

    student = Student(
        first_name=first_name,
        last_initial="A",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        identity_id=identity.id,
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.add(StudentBlock(user_id=student_user.id, period="1", join_code=f"T{teacher.id}S{student.id}"))
    db.session.commit()
    create_class_scope(
        teacher=teacher,
        teacher_user_id=teacher.user_id,
        join_code=f"T{teacher.id}S{student.id}",
        student=student,
        block="1",
        display_name="1",
        create_seat=True,
        teacher_block_claimed=True,
    )
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    from app.models import User
    user = db.session.get(User, admin.user_id)
    
    # Pre-configure the database state outside the session transaction
    class_row = (
        db.session.query(ClassEconomy.class_id, ClassEconomy.join_code)
        .filter(ClassEconomy.user_id == user.id)
        .order_by(ClassEconomy.join_code.asc())
        .first()
    )
    if class_row:
        user.last_active_class_id = class_row.class_id
    
    # Use a real nonce to match application behavior
    nonce = "test_nonce_123"
    user.current_session_nonce = nonce
    db.session.commit()
    
    # We bypass the actual route to force canonical context directly,
    # as the legacy test setup doesn't use real passwords.
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = nonce
        
    # Return a dummy 200 response to satisfy callers expecting a response object
    from flask import Response
    return Response("OK", status=200)


def _build_student_detail_public_url(client, admin: Admin, student: Student) -> str:
    from app.models import User
    user = db.session.get(User, admin.user_id)
    selected_class_id = user.last_active_class_id
    selected_join_code = ""

    seat_query = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.user_id == student.id,
            Seat.role == "student",
            Seat.public_id.isnot(None),
            ClassEconomy.user_id == admin.id,
        )
    )
    seat = None
    if selected_class_id:
        seat = seat_query.filter(Seat.class_id == selected_class_id).first()
    if not seat and selected_join_code:
        seat = seat_query.filter(Seat.join_code == selected_join_code).first()
    if not seat:
        seat = seat_query.order_by(Seat.id.asc()).first()
    assert seat is not None

    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
    nav = serializer.dumps({
        "student_id": int(student.id),
        "seat_public_id": str(seat.public_id),
        "class_id": str(seat.class_id) if seat.class_id else None,
        "admin_id": int(admin.id),
    })
    return f"/admin/students/{seat.public_id}?nav={nav}"


def test_student_listing_scoped_to_teacher(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    student_a = _create_student("Alice", teacher_a)
    _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get("/admin/students")
    body = response.get_data(as_text=True)
    if response.status_code != 200 or student_a.display_first_name not in body:
        print(f"DEBUG_BODY: status={response.status_code} len={len(body)}")
        with client.session_transaction() as sess:
            print(f"DEBUG_SESSION: {sess}")
            print(f"DEBUG_FLASHES: {sess.get('_flashes', [])}")

    assert response.status_code == 200
    assert student_a.display_first_name in body
    assert "Bob" not in body


def test_student_detail_forbids_cross_tenant_access(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    _create_student("Alice", teacher_a)
    student_b = _create_student("Bob", teacher_b)

    _login_admin(client, teacher_a, secret_a)

    response = client.get(f"/admin/students/{student_b.id}")

    assert response.status_code == 404


def test_shared_student_accessible_to_multiple_teachers(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    shared_student = _create_student("Shared", teacher_a)

    # Grant teacher B access to the shared student without changing the primary teacher
    db.session.add(StudentTeacher(user_id=shared_student_user.id, teacher_id=teacher_b.id))
    create_class_scope(
        teacher=teacher_b,
        teacher_user_id=teacher_b.user_id,
        join_code=f"T{teacher_b.id}SHARED",
        student=shared_student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()

    _login_admin(client, teacher_b, secret_b)

    detail_url = _build_student_detail_public_url(client, teacher_b, shared_student)
    detail_response = client.get(detail_url, follow_redirects=True)
    list_response = client.get("/admin/students")

    assert detail_response.status_code == 200
    assert "Shared" in list_response.get_data(as_text=True)


def test_student_detail_recovers_from_stale_class_context(client):
    teacher, secret = _create_admin("teacher-a")
    student_a = _create_student("Alice", teacher)
    student_b = _create_student("Bob", teacher)

    class_a = create_class_scope(
        teacher=teacher,
        teacher_user_id=teacher.user_id,
        join_code="JOINA",
        student=student_a,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_b = create_class_scope(
        teacher=teacher,
        teacher_user_id=teacher.user_id,
        join_code="JOINB",
        student=student_b,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.flush()
    seat_a = Seat.query.filter_by(user_id=student_a_user.id, join_code="JOINA", class_id=class_a.class_id).first()
    assert seat_a is not None
    Seat.query.filter_by(user_id=student_b_user.id, join_code="JOINB", class_id=class_b.class_id).first()

    # Teacher has two class contexts; stale session context points to the other student.
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

    _login_admin(client, teacher, secret)
    from app.models import User
    user = db.session.get(User, teacher.user_id)
    user.last_active_class_id = class_b.class_id
    db.session.commit()

    from itsdangerous import URLSafeTimedSerializer
    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
    nav = serializer.dumps({
        "student_id": int(student_a.id),
        "seat_public_id": str(seat_a.public_id),
        "class_id": str(class_a.class_id),
        "admin_id": int(teacher.id),
    })
    detail_url = f"/admin/students/{seat_a.public_id}?nav={nav}"
    response = client.get(detail_url, follow_redirects=True)
def test_enforce_daily_limits_ignores_other_join_code_activity(client):
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    shared_student = _create_student("SharedLimit", teacher_a)
    db.session.add(StudentTeacher(user_id=shared_student_user.id, teacher_id=teacher_b.id))
    class_scope_a = create_class_scope(
        teacher=teacher_a,
        teacher_user_id=teacher_a.user_id,
        join_code="JOINA",
        student=shared_student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    class_scope_b = create_class_scope(
        teacher=teacher_b,
        teacher_user_id=teacher_b.user_id,
        join_code="JOINB",
        student=shared_student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )

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
            user_id=shared_student_user.id,
            seat_id=Seat.query.filter_by(user_id=shared_student_user.id, class_id=class_scope_b.class_id).first().id,
            class_id=class_scope_b.class_id,
            period="A",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            start_reason="Start work",
        ),
        SeatAttendanceState(
            user_id=shared_student_user.id,
            seat_id=Seat.query.filter_by(user_id=shared_student_user.id, class_id=class_scope_b.class_id).first().id,
            class_id=class_scope_b.class_id,
            period="A",
            is_active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(hours=2),

        ),
        StudentBlock(
            user_id=shared_student_user.id,
            period="A",
            join_code="JOINA",
            tap_enabled=True,
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] == 0
    assert payload["tapped_out"] == []

    inactive_count = AttendanceSession.query.filter(
        AttendanceSession.student_id == shared_student.id,
        AttendanceSession.period == "A",
        AttendanceSession.ended_at.isnot(None),
        AttendanceSession.class_id == class_scope_a.class_id,
    ).count()
    assert inactive_count == 0


def test_enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    teacher, secret = _create_admin("teacher-a")
    student = _create_student("AliceLimit", teacher)

    class_scope = create_class_scope(
        teacher=teacher,
        teacher_user_id=teacher.user_id,
        join_code="JOINA",
        student=student,
        block="A",
        display_name="A",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
        create_student_membership=True,
    )
    db.session.flush()
    seat = Seat.query.filter_by(user_id=student_user.id, join_code="JOINA", class_id=class_scope.class_id).first()
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
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=class_scope.class_id,
            period="A",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            start_reason="Start work",
        ),
        SeatAttendanceState(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=class_scope.class_id,
            period="A",
            is_active=True,
            last_event_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ),
        StudentBlock(
            user_id=student_user.id,
            period="A",
            join_code="JOINA",
            tap_enabled=True,
        )
    ])
    db.session.commit()

    _login_admin(client, teacher, secret)
    response = client.post("/admin/enforce-daily-limits")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] >= 1
    assert any(student.full_name in entry for entry in payload["tapped_out"])

    att_state = SeatAttendanceState.query.filter_by(seat_id=seat.id, class_id=class_scope.class_id, period="A").first()
    assert att_state is not None
    assert att_state.done_for_day_date is not None

    inactive_count = AttendanceSession.query.filter(
        AttendanceSession.student_id == student.id,
        AttendanceSession.period == "A",
        AttendanceSession.end_reason.ilike("Daily limit%"),
    ).count()
    assert inactive_count == 1


def test_student_detail_public_url_requires_nav_token(client):
    teacher, secret = _create_admin("teacher-public")
    student = _create_student("PublicDetail", teacher)
    _login_admin(client, teacher, secret)

    nav_url = _build_student_detail_public_url(client, teacher, student)
    ok = client.get(nav_url, follow_redirects=False)
    assert ok.status_code == 200

    public_path = nav_url.split("?", 1)[0]
    direct = client.get(public_path, follow_redirects=False)
    assert direct.status_code == 404


def test_student_detail_public_id_is_seat_scoped_for_shared_student(client):
    teacher_a, secret_a = _create_admin("teacher-seat-scope-a")
    teacher_b, _ = _create_admin("teacher-seat-scope-b")
    shared_student = _create_student("SharedSeatScope", teacher_a)
    db.session.add(StudentTeacher(user_id=shared_student_user.id, teacher_id=teacher_b.id))
    class_b = create_class_scope(
        teacher=teacher_b,
        teacher_user_id=teacher_b.user_id,
        join_code="SHAREDSEATB",
        student=shared_student,
        block="B",
        display_name="B",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()

    class_a = ClassEconomy.query.filter(
        ClassEconomy.user_id == teacher_a.id,
        ClassEconomy.class_id != class_b.class_id,
    ).first()
    seat_a = Seat.query.filter_by(user_id=shared_student_user.id, class_id=class_a.class_id).first()
    seat_b = Seat.query.filter_by(user_id=shared_student_user.id, class_id=class_b.class_id).first()
    assert seat_a is not None
    assert seat_b is not None
    assert seat_a.public_id != seat_b.public_id

    _login_admin(client, teacher_a, secret_a)
    own_detail_url = _build_student_detail_public_url(client, teacher_a, shared_student)
    assert f"/admin/students/{seat_a.public_id}?" in own_detail_url
    assert client.get(own_detail_url, follow_redirects=False).status_code == 200

    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
    forged_cross_class_nav = serializer.dumps({
        "student_id": int(shared_student.id),
        "seat_public_id": str(seat_b.public_id),
        "class_id": str(seat_b.class_id),
        "admin_id": int(teacher_a.id),
    })
    cross_class_response = client.get(
        f"/admin/students/{seat_b.public_id}?nav={forged_cross_class_nav}",
        follow_redirects=False,
    )
    assert cross_class_response.status_code == 404





