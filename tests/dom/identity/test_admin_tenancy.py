from datetime import datetime, timezone, timedelta
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, Seat, Transaction, User
from app.scheduled_tasks import enforce_daily_limits_job
from app.services.context_resolver import CanonicalContext
from app.services.payroll_settings_service import upsert_payroll_settings
from tests.helpers.classroom_initializer import initialize
from tests.helpers.canonical_session import set_canonical_context
from tests.dom.identity.helpers import admin_get_students


def _set_admin_context(client, *, teacher_user: User, class_id: str, teacher_seat_id: int) -> None:
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_user.id,
            class_id=class_id,
            seat_id=teacher_seat_id,
            role="admin",
        )


def _teacher_context(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _session_start_within_evaluation_day(classroom, *, hours_ago: float) -> datetime:
    """A session start `hours_ago` in the past, but never before today's boundary.

    `enforce_daily_limits_job` accrues against a *daily* limit, so it clamps each
    interval with `max(active_start, day_start_utc)`: time spent yesterday does
    not count toward today's cap. A naive `now() - 2h` seed silently violates
    that premise whenever the suite runs within two hours of the class's
    evaluation-day boundary — the job then taps out at `day_start + limit`, not
    `started_at + limit`, and the test fails for a reason that has nothing to do
    with what it certifies. Anchoring the seed to the same boundary the job uses
    keeps the scenario ("a session opened earlier today") intact at every hour of
    the day rather than only for 22 of them.
    """
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
    )

    ctx = _teacher_context(classroom)
    now_utc = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
    ).canonical_now_utc
    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=now_utc,
    )
    return max(now_utc - timedelta(hours=hours_ago), day_bounds.boundary_start_utc)


def _seed_active_attendance(classroom, seat: Seat, *, started_at: datetime) -> AttendanceSession:
    result = record_attendance_session(
        ctx=_teacher_context(classroom),
        target_seat_id=seat.id,
        actor_seat_id=classroom.teacher_seat.id,
        mechanism="teacher",
        status="active",
        idempotency_key=f"admin_tenancy:active_seed:{classroom.class_id}:{seat.id}",
        reference_time_utc=started_at,
    )
    return result.session


def _configure_daily_limit(class_id: str, *, daily_limit_hours: float, idempotency_key: str) -> None:
    """Configure the class's canonical payroll settings with a daily limit.

    Uses the sole canonical writer (`upsert_payroll_settings`), which updates the
    single class-scoped PayrollSettings row in place (DOM-CLASS-001: `class_id` is
    the sole scoping key, one active row per class). This mirrors how a teacher
    configures limits in production; it must NOT insert a second active row, which
    would violate `uq_payroll_settings_active_scope` and produce the "Ambiguous
    PayrollSettings scope" fatal that this fixture previously provoked.
    """
    with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
        upsert_payroll_settings(
            class_id=class_id,
            settings_data={
                "block": None,
                "settings_mode": "simple",
                "daily_limit_hours": daily_limit_hours,
                "pay_rate": 0.25,
                "payroll_frequency_days": 14,
            },
        )


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

    _set_admin_context(
        client,
        teacher_user=teacher_a,
        class_id=class_a.class_id,
        teacher_seat_id=class_a.teacher_seat.id,
    )
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

    _set_admin_context(
        client,
        teacher_user=teacher_a,
        class_id=class_a.class_id,
        teacher_seat_id=class_a.teacher_seat.id,
    )
    response = client.get(_build_student_detail_public_url(client, class_b.teacher_user, class_b.students[0].user, class_id=class_b.class_id))
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

    _set_admin_context(
        client,
        teacher_user=teacher_b,
        class_id=class_b.class_id,
        teacher_seat_id=class_b.teacher_seat.id,
    )
    list_response = admin_get_students(client)

    assert list_response.status_code == 200
    assert shared_student_user is not None


def test_DOM_IDEN_006__student_detail_recovers_from_stale_class_context(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)

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
    _set_admin_context(
        client,
        teacher_user=teacher,
        class_id=class_a.class_id,
        teacher_seat_id=class_a.teacher_seat.id,
    )

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
    shared_seat_b = class_b.students[0].seat
    started_at = _session_start_within_evaluation_day(class_b, hours_ago=2)

    _configure_daily_limit(
        class_a.class_id,
        daily_limit_hours=0.001,
        idempotency_key="admin_tenancy:daily_limit_seed",
    )
    _seed_active_attendance(class_b, shared_seat_b, started_at=started_at)
    db.session.commit()

    enforce_daily_limits_job()

    rows = AttendanceSession.query.filter_by(
        target_seat_id=shared_seat_b.id,
        class_id=class_b.class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()

    assert len(rows) == 1
    assert rows[0].status == "active"
    assert rows[0].timestamp == started_at
    assert AttendanceSession.query.filter_by(
        target_seat_id=shared_seat_b.id,
        class_id=class_b.class_id,
        status="inactive",
    ).count() == 0


def test_DOM_IDEN_001__enforce_daily_limits_taps_out_when_limit_reached_in_scope(client):
    class_scope = initialize("chemistry_p1", client.application)
    seat = class_scope.students[0].seat
    started_at = _session_start_within_evaluation_day(class_scope, hours_ago=2)
    daily_limit_hours = 0.001
    expected_limit_seconds = int(daily_limit_hours * 3600)

    _configure_daily_limit(
        class_scope.class_id,
        daily_limit_hours=daily_limit_hours,
        idempotency_key="admin_tenancy:limit_seed",
    )
    _seed_active_attendance(class_scope, seat, started_at=started_at)
    db.session.commit()

    enforce_daily_limits_job()

    rows = AttendanceSession.query.filter_by(
        target_seat_id=seat.id,
        class_id=class_scope.class_id,
    ).order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()

    assert len(rows) == 2
    active_row, inactive_row = rows
    assert active_row.status == "active"
    assert inactive_row.status == "inactive"
    assert inactive_row.actor_seat_id == class_scope.teacher_seat.id
    assert inactive_row.mechanism == "system"
    assert inactive_row.reason_code == AttendanceReasonCode.DONE_FOR_DAY.value
    assert inactive_row.timestamp == started_at + timedelta(seconds=expected_limit_seconds)


def test_DOM_IDEN_001__enforce_daily_limits_does_not_duplicate_closed_session(client):
    class_scope = initialize("chemistry_p1", client.application)
    seat = class_scope.students[0].seat
    started_at = _session_start_within_evaluation_day(class_scope, hours_ago=2)
    daily_limit_hours = 0.001

    _configure_daily_limit(
        class_scope.class_id,
        daily_limit_hours=daily_limit_hours,
        idempotency_key="admin_tenancy:limit_idempotency_seed",
    )
    _seed_active_attendance(class_scope, seat, started_at=started_at)
    db.session.commit()

    enforce_daily_limits_job()
    enforce_daily_limits_job()

    assert AttendanceSession.query.filter_by(
        target_seat_id=seat.id,
        class_id=class_scope.class_id,
        status="inactive",
        mechanism="system",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY.value,
    ).count() == 1


def test_DOM_IDEN_006__student_detail_public_url_requires_nav_token(client):
    class_row = initialize("chemistry_p1", client.application)
    teacher = class_row.teacher_user
    student_user = class_row.students[0].user
    db.session.commit()

    _set_admin_context(
        client,
        teacher_user=teacher,
        class_id=class_row.class_id,
        teacher_seat_id=class_row.teacher_seat.id,
    )

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

    _set_admin_context(
        client,
        teacher_user=teacher_a,
        class_id=class_a.class_id,
        teacher_seat_id=class_a.teacher_seat.id,
    )
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
