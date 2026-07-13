from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
import sqlalchemy as sa

from app.extensions import db
from app.models import (
    Admin,
    AttendanceSession,
    ClassEconomy,
    HallPassLog,
    HallPassSettings,
    Seat,
    SeatAttendanceState,
    AttendanceReasonCode,
)
from app.services.entitlement_service import consume_hall_pass, get_hall_pass_balance
from app.payroll import get_daily_limit_seconds
from app.utils.economy_policy import resolve_feature_class_for_class
from app.utils.join_code import get_display_join_code
from app.utils.time import ensure_utc, get_class_now, get_class_today_range, normalize_for_db, utc_now
from app.attendance import calculate_period_attendance_utc_range


HALL_PASS_FREE_REASONS = {"office", "summons", "done for the day"}


@dataclass
class HallPassMutationResult:
    message: str
    destination: str | None = None
    left_time_iso: str | None = None
    return_time_iso: str | None = None


@dataclass
class TapGuardResult:
    allowed: bool
    message: str | None = None
    status_code: int | None = None


@dataclass
class HallPassRequestGuardResult(TapGuardResult):
    user_id: int | None = None
    should_require_pass: bool = False


def _get_or_create_hall_pass_settings(*, class_id: str):
    """Fetch class-scoped hall pass settings, creating defaults when absent."""
    settings = HallPassSettings.query.filter_by(class_id=class_id).first()
    if settings:
        return settings

    settings = HallPassSettings(
        class_id=class_id,
        queue_enabled=True,
        queue_limit=10,
        pass_types=HallPassSettings.get_default_pass_types(),
    )
    db.session.add(settings)
    db.session.flush()
    return settings


def student_tap(
    *,
    seat_id: int,
    class_id: str,
    status: str,
    reason: str | None = None,
    reason_code: AttendanceReasonCode | None = None,
    timestamp_utc=None,
) -> AttendanceSession:
    """Create or close canonical attendance sessions and update live state."""
    event_time = timestamp_utc or utc_now()
    state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()

    if status == "active":
        session = AttendanceSession(
            seat_id=seat_id,
            class_id=class_id,
            started_at=event_time,
            start_reason=reason,
            created_at=event_time,
            updated_at=event_time,
        )
        db.session.add(session)
        db.session.flush()
        if not state:
            state = SeatAttendanceState(
                seat_id=seat_id,
                class_id=class_id,
            )
            db.session.add(state)
        state.is_active = True
        state.open_session_id = session.id
        state.last_event_at = event_time
        state.last_event_status = "active"
        state.last_reason = reason
        state.done_for_day_date = None
        state.updated_at = event_time
        db.session.flush()
        return session

    open_session = None
    if state and state.open_session_id:
        open_session = db.session.get(AttendanceSession, state.open_session_id)
    if not open_session:
        open_session = (
            AttendanceSession.query.filter_by(
                seat_id=seat_id,
                class_id=class_id,
                ended_at=None,
            )
            .order_by(AttendanceSession.started_at.desc(), AttendanceSession.id.desc())
            .first()
        )

    if open_session:
        start_time = ensure_utc(open_session.started_at)
        end_time = event_time if event_time >= start_time else start_time
        open_session.ended_at = end_time
        open_session.duration_seconds = int(max(0, (end_time - start_time).total_seconds()))
        open_session.end_reason = reason
        open_session.end_reason_code = reason_code
        open_session.updated_at = event_time
        session = open_session
    else:
        session = AttendanceSession(
            seat_id=seat_id,
            class_id=class_id,
            started_at=event_time,
            ended_at=event_time,
            duration_seconds=0,
            start_reason=reason,
            end_reason=reason,
            end_reason_code=reason_code,
            created_at=event_time,
            updated_at=event_time,
        )
        db.session.add(session)
        db.session.flush()

    if not state:
        state = SeatAttendanceState(
            seat_id=seat_id,
            class_id=class_id,
        )
        db.session.add(state)
    state.is_active = False
    state.open_session_id = None
    state.last_event_at = event_time
    state.last_event_status = "inactive"
    state.last_reason = reason
    state.updated_at = event_time
    db.session.flush()
    return session


def request_hall_pass(
    *,
    student,
    seat_id: int,
    class_id: str,
    reason: str,
    now_utc=None,
) -> HallPassLog:
    """Create a canonical hall-pass request row."""
    entry = HallPassLog(
        student_id=student.id,
        seat_id=seat_id,
        class_id=class_id,
        reason=reason,
        status="pending",
        request_time=now_utc or utc_now(),
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def get_or_create_attendance_state(
    *,
    seat_id: int,
    class_id: str,
    tap_enabled: bool = True,
) -> SeatAttendanceState:
    """Get or create canonical attendance state for one seat/class."""
    state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()
    if state:
        return state

    try:
        state = SeatAttendanceState(
            seat_id=seat_id,
            class_id=class_id,
            tap_enabled=tap_enabled,
        )
        db.session.add(state)
        db.session.flush()
        return state
    except IntegrityError:
        db.session.rollback()
        return SeatAttendanceState.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
        ).first()


def apply_standard_tap_mutations(
    *,
    seat_id: int,
    class_id: str,
    normalized_action: str,
    reason: str | None,
    now_utc=None,
    logger=None,
) -> None:
    """Apply canonical tap-event mutations for start/stop work actions."""
    now = now_utc or utc_now()
    status = "active" if normalized_action == "start_work" else "inactive"

    if normalized_action == "start_work":
        active_hall_pass = HallPassLog.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            status="left",
        ).order_by(HallPassLog.request_time.desc()).first()
        if active_hall_pass:
            active_hall_pass.status = "returned"
            active_hall_pass.return_time = now
            if logger:
                logger.info("Auto-returned hall pass %s for seat %s", active_hall_pass.id, seat_id)

    student_tap(
        seat_id=seat_id,
        class_id=class_id,
        status=status,
        reason=reason,
        timestamp_utc=now,
    )

    att_state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()

    today_local = get_class_now(class_id, reference_time_utc=now).date()
    if att_state and att_state.done_for_day_date and att_state.done_for_day_date != today_local:
        att_state.done_for_day_date = None
        if logger:
            logger.info("Cleared done_for_day_date for seat %s (new day)", seat_id)

    if normalized_action == "stop_work" and att_state:
        if reason and reason.lower() in ["done", "done for the day"]:
            att_state.done_for_day_date = today_local
            if logger:
                logger.info("Seat %s marked as done for the day", seat_id)
        elif att_state.done_for_day_date is not None:
            att_state.done_for_day_date = None
            if logger:
                logger.info(
                    "Cleared done_for_day_date for seat %s (reason: %s)",
                    seat_id,
                    reason,
                )

    db.session.flush()


def approve_hall_pass(*, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    now = now_utc or utc_now()
    if log_entry.status != "pending":
        raise ValueError("Pass is not pending.")

    should_deduct = (log_entry.reason or "").lower() not in HALL_PASS_FREE_REASONS
    if should_deduct:
        balance = get_hall_pass_balance(log_entry.seat_id, log_entry.class_id)
        if balance <= 0:
            raise ValueError("Student has no hall passes left.")

    log_entry.status = "approved"
    log_entry.decision_time = now

    if should_deduct:
        consume_hall_pass(
            log_entry.seat_id,
            log_entry.class_id,
            trigger_id=f"hall_pass_approve_{log_entry.id}",
        )

    db.session.flush()
    return HallPassMutationResult(message="Pass approved.")


def reject_hall_pass(*, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    if log_entry.status != "pending":
        raise ValueError("Pass is not pending.")
    log_entry.status = "rejected"
    log_entry.decision_time = now_utc or utc_now()
    db.session.flush()
    return HallPassMutationResult(message="Pass rejected.")


def leave_hall_pass(*, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    now = now_utc or utc_now()
    if log_entry.status != "approved":
        raise ValueError("Pass is not approved.")
    log_entry.status = "left"
    log_entry.left_time = now
    student_tap(
        seat_id=log_entry.seat_id,
        class_id=log_entry.class_id,
        status="inactive",
        reason=log_entry.reason,
        timestamp_utc=now,
    )
    db.session.flush()
    return HallPassMutationResult(message="Student has left the class.")


def return_hall_pass(*, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    now = now_utc or utc_now()
    if log_entry.status != "left":
        raise ValueError("Student is not out of class.")
    log_entry.status = "returned"
    log_entry.return_time = now
    student_tap(
        seat_id=log_entry.seat_id,
        class_id=log_entry.class_id,
        status="active",
        reason="Return from hall pass",
        timestamp_utc=now,
    )
    db.session.flush()
    return HallPassMutationResult(message="Student has returned.")


def cancel_hall_pass(*, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    if log_entry.status != "pending":
        raise ValueError("Only pending passes can be cancelled.")
    log_entry.status = "rejected"
    log_entry.decision_time = now_utc or utc_now()
    db.session.flush()
    return HallPassMutationResult(message="Hall pass request cancelled.")


def checkout_hall_pass(*, student, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    now = now_utc or utc_now()
    if log_entry.status != "approved":
        raise ValueError(f"Pass is not approved. Current status: {log_entry.status}")

    resolved_seat_id, resolved_class_id = log_entry.seat_id, log_entry.class_id
    if not student.id or not resolved_class_id or not resolved_seat_id:
        raise PermissionError("Missing class/seat context for hall pass checkout.")

    resolved_join_code = log_entry.join_code or get_display_join_code(resolved_class_id)

    log_entry.status = "left"
    log_entry.left_time = now
    student_tap(
        seat_id=resolved_seat_id,
        class_id=resolved_class_id,
        status="inactive",
        reason=log_entry.reason,
        timestamp_utc=now,
    )
    db.session.flush()
    return HallPassMutationResult(
        message=f"Checked out for {log_entry.reason}.",
        destination=log_entry.reason,
        left_time_iso=now.isoformat(),
    )


def checkin_hall_pass(*, student, log_entry: HallPassLog, now_utc=None) -> HallPassMutationResult:
    now = now_utc or utc_now()
    if log_entry.status != "left":
        raise ValueError(f"You are not currently checked out. Status: {log_entry.status}")

    resolved_seat_id, resolved_class_id = log_entry.seat_id, log_entry.class_id
    if not student.id or not resolved_class_id or not resolved_seat_id:
        raise PermissionError("Missing class/seat context for hall pass checkin.")

    resolved_join_code = log_entry.join_code or get_display_join_code(resolved_class_id)

    log_entry.status = "returned"
    log_entry.return_time = now
    student_tap(
        seat_id=resolved_seat_id,
        class_id=resolved_class_id,
        status="active",
        reason="Returned from hall pass",
        timestamp_utc=now,
    )
    db.session.flush()
    return HallPassMutationResult(
        message="Checked in successfully. Welcome back!",
        return_time_iso=now.isoformat(),
    )


def _check_simultaneous_pass_limit(*, log_entry: HallPassLog):
    economy = ClassEconomy.query.filter_by(class_id=log_entry.class_id).first()
    user_id = economy.user_id if economy else None
    if not user_id:
        return None

    settings = _get_or_create_hall_pass_settings(class_id=log_entry.class_id)
    if not settings:
        return None

    pass_types = settings.get_pass_types()
    pass_type_config = next((pt for pt in pass_types if pt["name"].lower() == log_entry.reason.lower()), None)
    if pass_type_config and not pass_type_config.get("enabled", True):
        return {
            "status": "error",
            "message": f"{log_entry.reason} pass type is currently disabled.",
        }, 403

    if pass_type_config and pass_type_config.get("simultaneous_limit") is not None:
        today_start_utc, _ = get_class_today_range(log_entry.class_id, reference_time_utc=utc_now())
        currently_out = HallPassLog.query.filter(
            HallPassLog.status == "left",
            HallPassLog.reason == log_entry.reason,
            HallPassLog.class_id == log_entry.class_id,
            HallPassLog.left_time >= today_start_utc,
            HallPassLog.id != log_entry.id,
        ).count()
        simultaneous_limit = pass_type_config["simultaneous_limit"]
        if currently_out >= simultaneous_limit:
            return {
                "status": "error",
                "message": (
                    f"{log_entry.reason} limit reached. {currently_out}/{simultaneous_limit} students are "
                    "currently out. Please wait for someone to return."
                ),
            }, 403
    return None


def check_start_work_daily_limit(
    *,
    seat_id: int,
    class_id: str,
    now_utc=None,
    logger=None,
) -> TapGuardResult:
    """Read-only daily-limit guard for tap start_work requests."""
    now = now_utc or utc_now()
    from app.models import ClassEconomy
    class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
    section = class_row.section if class_row else None
    daily_limit = get_daily_limit_seconds(section, class_id=class_id) if section else None
    if not daily_limit:
        return TapGuardResult(allowed=True)

    start_of_day_utc, end_of_day_utc = get_class_today_range(class_id, reference_time_utc=now)
    today_attendance = calculate_period_attendance_utc_range(
        seat_id,
        class_id,
        start_of_day_utc,
        end_of_day_utc,
    )
    if today_attendance < daily_limit:
        return TapGuardResult(allowed=True)

    hours_limit = daily_limit / 3600.0
    if logger:
        logger.warning(
            "Seat %s attempted to tap in but reached daily limit of %.1f hours",
            seat_id,
            hours_limit,
        )
    return TapGuardResult(
        allowed=False,
        message=f"Daily limit of {hours_limit:.1f} hours reached. Please try again tomorrow.",
        status_code=400,
    )


def check_hall_pass_request_policy(
    *,
    student,
    class_id: str,
    reason: str,
    now_utc=None,
) -> HallPassRequestGuardResult:
    """Read-only policy guards for hall-pass request creation on stop_work."""
    now = now_utc or utc_now()
    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    if not economy:
        return HallPassRequestGuardResult(
            allowed=False,
            message="Unable to resolve class context.",
            status_code=400,
        )
    user_id = economy.user_id

    feature_scope = resolve_feature_class_for_class(class_id, "hall_pass")
    if feature_scope and not feature_scope["enabled"]:
        return HallPassRequestGuardResult(
            allowed=False,
            message="Hall pass is currently disabled for this class.",
            status_code=403,
            user_id=user_id,
        )

    settings = _get_or_create_hall_pass_settings(class_id=class_id)
    if not settings:
        return HallPassRequestGuardResult(
            allowed=False,
            message="Hall pass settings are not available for this class.",
            status_code=400,
            user_id=user_id,
        )

    pass_types = settings.get_pass_types()
    pass_type_config = next((pt for pt in pass_types if pt["name"].lower() == reason.lower()), None)

    if not settings.queue_enabled:
        unlimited_queue = (
            pass_type_config
            and pass_type_config.get("queue_limit") is None
            and pass_type_config.get("simultaneous_limit") is None
        )
        if not unlimited_queue:
            return HallPassRequestGuardResult(
                allowed=False,
                message="Queue system is currently disabled.",
                status_code=403,
                user_id=user_id,
            )

    if pass_type_config and pass_type_config.get("queue_limit") is not None:
        today_start_utc, _ = get_class_today_range(class_id, reference_time_utc=now)
        today_start_db = normalize_for_db(today_start_utc)
        queue_count = HallPassLog.query.filter(
            HallPassLog.status == "approved",
            HallPassLog.reason == reason,
            HallPassLog.class_id == class_id,
            HallPassLog.decision_time >= today_start_db,
        ).count()
        out_count = HallPassLog.query.filter(
            HallPassLog.status == "left",
            HallPassLog.reason == reason,
            HallPassLog.class_id == class_id,
            HallPassLog.left_time >= today_start_db,
        ).count()
        total_in_queue = queue_count + out_count
        queue_limit = pass_type_config["queue_limit"]
        if total_in_queue >= queue_limit:
            return HallPassRequestGuardResult(
                allowed=False,
                message=f"{reason} queue is full ({total_in_queue}/{queue_limit}). Please wait for someone to return.",
                status_code=403,
                user_id=user_id,
            )

    should_require_pass = reason.lower() not in HALL_PASS_FREE_REASONS
    return HallPassRequestGuardResult(
        allowed=True,
        user_id=user_id,
        should_require_pass=should_require_pass,
    )


def enforce_daily_limits(*, seat_id: int, class_id: str, commit: bool = True, logger=None):
    """Canonical daily-limit enforcement for one seat/class."""
    now = utc_now()
    log = logger

    from app.models import ClassEconomy
    seat = db.session.get(Seat, seat_id)
    if not seat or not seat.class_id:
        return

    class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
    section = class_row.section if class_row else None
    start_of_day_utc, end_of_day_utc = get_class_today_range(class_id, reference_time_utc=now)
    today_local = get_class_now(class_id, reference_time_utc=now).date()

    state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()
    if not state or not state.is_active:
        if commit:
            db.session.flush()
        return

    daily_limit = get_daily_limit_seconds(section, class_id=class_id) if section else None
    if not daily_limit:
        if commit:
            db.session.flush()
        return

    today_attendance = calculate_period_attendance_utc_range(
        seat_id,
        class_id,
        start_of_day_utc,
        end_of_day_utc,
    )

    if today_attendance < daily_limit:
        if commit:
            db.session.flush()
        return

    hours_limit = daily_limit / 3600.0

    existing_limit_tapout = AttendanceSession.query.filter(
        AttendanceSession.seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.ended_at >= start_of_day_utc,
        AttendanceSession.ended_at < end_of_day_utc,
        AttendanceSession.end_reason_code == AttendanceReasonCode.DAILY_LIMIT,
    ).first()
    if existing_limit_tapout:
        if log:
            log.debug(
                "Skipping duplicate auto-tap-out for seat %s - already exists at %s",
                seat_id,
                existing_limit_tapout.ended_at,
            )
        if commit:
            db.session.flush()
        return

    if log:
        log.info(
            "Auto-tapping out seat %s - daily limit of %.1f hours reached (total: %.2fh)",
            seat_id,
            hours_limit,
            today_attendance / 3600.0,
        )

    overage_seconds = today_attendance - daily_limit
    tapout_timestamp = now - timedelta(seconds=overage_seconds)

    student_tap(
        seat_id=seat_id,
        class_id=class_id,
        status="inactive",
        reason=f"Daily limit ({hours_limit:.1f}h) reached",
        timestamp_utc=tapout_timestamp,
        reason_code=AttendanceReasonCode.DAILY_LIMIT,
    )

    state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()
    if not state:
        state = SeatAttendanceState(
            seat_id=seat_id,
            class_id=class_id,
            tap_enabled=True,
        )
        db.session.add(state)
    state.done_for_day_date = today_local

    if commit:
        db.session.flush()


def soft_delete_session(*, session: AttendanceSession, admin_seat_id: int | None, deleted_at=None) -> None:
    """Soft-delete one attendance session with audit fields."""
    session.is_deleted = True
    session.deleted_at = deleted_at or utc_now()
    session.deleted_by_seat_id = admin_seat_id
    db.session.flush()




def set_attendance_state_tap_enabled(
    *,
    seat_id: int,
    class_id: str,
    tap_enabled: bool,
) -> SeatAttendanceState:
    """Set tap_enabled for a canonical seat/class row."""
    state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
    ).first()
    if state:
        state.tap_enabled = tap_enabled
        db.session.flush()
        return state

    state = SeatAttendanceState(
        seat_id=seat_id,
        class_id=class_id,
        tap_enabled=tap_enabled,
    )
    db.session.add(state)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise PermissionError("Seat not found or access denied.") from exc
    return state


def admin_tap_out(
    *,
    seat_id: int,
    class_id: str,
    reason: str | None = None,
    now_utc=None,
) -> AttendanceSession:
    return student_tap(
        seat_id=seat_id,
        class_id=class_id,
        status="inactive",
        reason=reason,
        timestamp_utc=now_utc or utc_now(),
    )


def admin_tap_in(
    *,
    seat_id: int,
    class_id: str,
    reason: str | None = None,
    now_utc=None,
) -> AttendanceSession:
    return student_tap(
        seat_id=seat_id,
        class_id=class_id,
        status="active",
        reason=reason,
        timestamp_utc=now_utc or utc_now(),
    )


def update_hall_pass_queue_settings(
    *,
    user_id: int,
    class_id: str,
    queue_enabled=None,
    queue_limit=None,
    updated_at=None,
) -> HallPassSettings:
    """Update class-scoped queue settings for hall-pass management."""
    settings = _get_or_create_hall_pass_settings(class_id=class_id)
    if not settings:
        raise ValueError("Class context is required")

    if queue_enabled is not None:
        settings.queue_enabled = bool(queue_enabled)

    if queue_limit is not None:
        try:
            parsed_limit = int(queue_limit)
        except (TypeError, ValueError):
            raise ValueError("Queue limit must be between 1 and 50")
        if parsed_limit < 1 or parsed_limit > 50:
            raise ValueError("Queue limit must be between 1 and 50")
        settings.queue_limit = parsed_limit

    settings.updated_at = ensure_utc(updated_at or utc_now())
    db.session.flush()
    return settings


def save_hall_pass_setup_config(
    *,
    user_id: int,
    class_id: str,
    hall_pass_enabled: bool,
    pass_types: list[dict],
    updated_at=None,
) -> HallPassSettings:
    """Persist class-scoped hall-pass configuration payload."""
    settings = _get_or_create_hall_pass_settings(class_id=class_id)
    if not settings:
        raise ValueError("Class scope not found")

    settings.queue_enabled = hall_pass_enabled
    settings.pass_types = pass_types
    settings.updated_at = ensure_utc(updated_at or utc_now())
    db.session.flush()
    return settings


def rotate_teacher_hall_pass_verify_token(*, user_id: int) -> str:
    """Rotate and persist a teacher hall-pass verification token on canonical User."""
    from app.models import User
    teacher_user = db.session.get(User, user_id)
    if not teacher_user:
        raise LookupError("User not found.")

    teacher_user.hall_pass_verify_token = User.generate_verify_token()
    db.session.flush()
    return teacher_user.hall_pass_verify_token
