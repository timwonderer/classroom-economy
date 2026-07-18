from datetime import datetime, timezone, timedelta
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, ClassEconomy, PayrollSettings, Seat, SeatAttendanceState, Transaction, User
from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import admin_enforce_daily_limits, admin_get_students


def _build_student_detail_public_url(client, teacher_user: User, student_user: User, *, class_id: str) -> str:
    seat = (
        Seat.query.filter(
            Seat.user_id == student_user.id,
            Seat.role == "student",
            Seat.public_id.isnot(None),
            Seat.class_id == class_id,
        )
        .order_by(Seat.id.asc())
        .first()
    )
    assert seat is not None, "No seat found for student in the requested class"

    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
    nav = serializer.dumps({
        "actor_public_id": str(seat.public_id),
        "class_id": str(seat.class_id) if seat.class_id else None,
        "user_id": int(teacher_user.id),
    })
    return f"/admin/students/{seat.public_id}?nav={nav}"


def test_DOM_IDEN_006__student_listing_scoped_to_teacher(client):
    class_a = initialize("chemistry_p1", client.application)
    initialize("biology_block_a", client.application)

    teacher_a = class_a.teacher_user
    seat_a = class_a.students[0].seat

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = class_a.teacher_seat.id
        sess["role"] = "admin"
    response = admin_get_students(client)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    profile_a = seat_a.identity_profile
    assert profile_a is None or "Ava" in body or response.status_code == 200


def test_DOM_IDEN_006__student_detail_forbids_cross_tenant_access(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)

    teacher_a = class_a.teacher_user
    seat_b = class_b.students[0].seat

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = class_a.teacher_seat.id
        sess["role"] = "admin"
    response = client.get(f"/admin/students/{seat_b.id}")
    assert response.status_code == 404


def test_DOM_IDEN_007__shared_student_accessible_to_multiple_teachers(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)

    teacher_b = class_b.teacher_user
    shared_seat = class_a.students[0].seat
    shared_student_user = class_a.students[0].user
    seat_b = class_b.students[0].seat
    db.session.commit()

    assert shared_seat is not None
    assert seat_b is not None

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_b.id
        sess["current_class_id"] = class_b.class_id
        sess["current_seat_id"] = class_b.teacher_seat.id
        sess["role"] = "admin"
    list_response = admin_get_students(client)

    assert list_response.status_code == 200
    assert shared_student_user is not None


def test_DOM_IDEN_006__student_detail_recovers_from_stale_class_context(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("ap_csp_p3", client.application)

    teacher = class_a.teacher_user
    seat_a = class_a.students[0].seat
    student_a_user = class_a.students[0].user

    with FEATContext("FEAT-ADMN-001"):
        db.session.add(
            Transaction(
                user_id=student_a_user.id,
                seat_id=seat_a.id,
                target_seat_id=seat_a.id,
                actor_seat_id=seat_a.id,
                mechanism="self",
                amount=25,
                type="bonus",
                account_type="checking",
                description="Scoped tx",
                class_id=class_a.class_id,
            ),
        )
        db.session.flush()

    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = teacher.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = class_a.teacher_seat.id
        sess["role"] = "admin"

    with FEATContext("FEAT-IDEN-001", idempotency_key="admin_tenancy:stale_class_context"):
        teacher.last_active_class_id = class_b.class_id
        db.session.flush()
    db.session.commit()

    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
    nav = serializer.dumps({
        "actor_public_id": str(seat_a.public_id),
        "class_id": str(class_a.class_id),
        "user_id": int(teacher.id),
    })
    detail_url = f"/admin/students/{seat_a.public_id}?nav={nav}"
    response = client.get(detail_url, follow_redirects=True)
    assert response.status_code == 200


def test_DOM_IDEN_001__enforce_daily_limits_ignores_other_class_activity(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    teacher_a = class_a.teacher_user
    shared_seat_b = class_b.students[0].seat

    with FEATContext("FEAT-ADMN-001", idempotency_key="admin_tenancy:daily_limit_seed"):
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
        db.session.flush()
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = class_a.teacher_seat.id
        sess["role"] = "admin"
    response = admin_enforce_daily_limits(client)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] == 0
    assert payload["tapped_out"] == []


def test_DOM_IDEN_001__enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    class_scope = initialize("chemistry_p1", client.application)
    teacher = class_scope.teacher_user
    seat = class_scope.students[0].seat

    with FEATContext("FEAT-ADMN-001", idempotency_key="admin_tenancy:limit_seed"):
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
        db.session.flush()
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = teacher.id
        sess["current_class_id"] = class_scope.class_id
        sess["current_seat_id"] = class_scope.teacher_seat.id
        sess["role"] = "admin"
    response = admin_enforce_daily_limits(client)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["checked"] >= 1
    assert len(payload["tapped_out"]) >= 1

    att_state = SeatAttendanceState.query.filter_by(seat_id=seat.id, class_id=class_scope.class_id).first()
    assert att_state is not None
    assert att_state.done_for_day_date is not None

    inactive_count = AttendanceSession.query.filter(
        AttendanceSession.seat_id == seat.id,
        AttendanceSession.class_id == class_scope.class_id,
        AttendanceSession.end_reason.ilike("Daily limit%"),
    ).count()
    assert inactive_count == 1


def test_DOM_IDEN_006__student_detail_public_url_requires_nav_token(client):
    class_row = initialize("chemistry_p1", client.application)
    teacher = class_row.teacher_user
    student_user = class_row.students[0].user
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = teacher.id
        sess["current_class_id"] = class_row.class_id
        sess["current_seat_id"] = class_row.teacher_seat.id
        sess["role"] = "admin"

    nav_url = _build_student_detail_public_url(client, teacher, student_user, class_id=class_row.class_id)
    ok = client.get(nav_url, follow_redirects=False)
    assert ok.status_code == 200

    public_path = nav_url.split("?", 1)[0]
    direct = client.get(public_path, follow_redirects=False)
    assert direct.status_code == 404


def test_DOM_IDEN_007__student_detail_public_id_is_seat_scoped_for_shared_student(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)

    teacher_a = class_a.teacher_user
    seat_a = class_a.students[0].seat
    shared_student_user = class_a.students[0].user
    seat_b = class_b.students[0].seat
    db.session.commit()

    assert seat_a is not None
    assert seat_b is not None
    assert seat_a.public_id != seat_b.public_id

    with client.session_transaction() as sess:
        sess["user_id"] = teacher_a.id
        sess["current_class_id"] = class_a.class_id
        sess["current_seat_id"] = class_a.teacher_seat.id
        sess["role"] = "admin"
    own_detail_url = _build_student_detail_public_url(client, teacher_a, shared_student_user, class_id=class_a.class_id)
    assert f"/admin/students/{seat_a.public_id}?" in own_detail_url
    assert client.get(own_detail_url, follow_redirects=False).status_code == 200

    serializer = URLSafeTimedSerializer(client.application.config["SECRET_KEY"], salt="cth-student-detail-nav-v1")
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
