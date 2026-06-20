from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.utils.time import (
    utc_now,
    ensure_utc,
    normalize_for_db,
    class_date,
    get_class_now,
    get_class_today_range,
    local_date_range_utc,
)
import sqlalchemy as sa
from flask import current_app
from app.extensions import db
import pytz
from app.services.attendance_service import (
    calculate_unpaid_attendance_seconds as _calculate_unpaid_attendance_seconds,
    get_all_block_statuses as _get_all_block_statuses,
)
from app.services.ledger_service import get_last_payroll_time as _get_last_payroll_time
from app.models import AttendanceSession
from app.feats.base import feat_shell

def get_last_payroll_time(*, seat_id: int, class_id: str):
    """Return the latest payroll/manual payment anchor for one canonical seat/class scope."""
    if not seat_id or not class_id:
        raise ValueError("get_last_payroll_time requires seat_id and class_id.")
    return _get_last_payroll_time(seat_id=seat_id, class_id=class_id)



def calculate_unpaid_attendance_seconds(seat_id, class_id, period, last_payroll_time):
    """Calculate unpaid attendance seconds for one canonical seat/class/period scope."""
    if not seat_id or not class_id:
        raise ValueError("calculate_unpaid_attendance_seconds requires seat_id and class_id.")
    return _calculate_unpaid_attendance_seconds(
        seat_id,
        class_id,
        period,
        last_payroll_time,
    )


def calculate_period_attendance(seat_id, class_id, period, date):
    """
    Calculates total attendance seconds for a student in a specific period
    on a specific date. Used for daily attendance reporting.
    NOTE: This uses UTC day boundaries.
    For class-timezone daily limits, use calculate_period_attendance_utc_range instead.
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_period_attendance requires seat_id and class_id.")

    # Build UTC range for the specified date
    start_utc = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    sessions = AttendanceSession.query.filter(
        AttendanceSession.seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.period == period,
        AttendanceSession.started_at < end_db,
        sa.or_(AttendanceSession.ended_at.is_(None), AttendanceSession.ended_at > start_db),
    ).all()

    total_seconds = 0
    now_utc = utc_now()
    for session in sessions:
        start_time = max(ensure_utc(session.started_at), start_utc)
        end_time = ensure_utc(session.ended_at) if session.ended_at else now_utc
        end_time = min(end_time, end_utc)
        if end_time > start_time:
            total_seconds += (end_time - start_time).total_seconds()
    return int(total_seconds)


def calculate_period_attendance_utc_range(seat_id, class_id, period, start_utc, end_utc):
    """
    Calculates total attendance seconds for a student in a specific period
    within a UTC datetime range. Use this for timezone-aware daily limits.

    Args:
        seat_id: The seat's ID
        class_id: The class's ID
        period: The block/period identifier
        start_utc: Start of period (UTC datetime, inclusive)
        end_utc: End of period (UTC datetime, exclusive)

    Returns:
        int: Total seconds of attendance in the range
    """
    if not seat_id or not class_id:
        raise ValueError("calculate_period_attendance_utc_range requires seat_id and class_id.")

    start_db = normalize_for_db(start_utc)
    end_db = normalize_for_db(end_utc)

    sessions = AttendanceSession.query.filter(
        AttendanceSession.seat_id == seat_id,
        AttendanceSession.class_id == class_id,
        AttendanceSession.period == period,
        AttendanceSession.started_at < end_db,
        sa.or_(AttendanceSession.ended_at.is_(None), AttendanceSession.ended_at > start_db),
    ).all()

    total_seconds = 0
    now_utc = utc_now()
    for session in sessions:
        start_time = max(ensure_utc(session.started_at), start_utc)
        end_time = ensure_utc(session.ended_at) if session.ended_at else now_utc
        end_time = min(end_time, end_utc)
        if end_time > start_time:
            total_seconds += (end_time - start_time).total_seconds()
    return int(total_seconds)


def get_session_status(seat_id, class_id, period):
    """
    Gets the current session status for a student in a specific period.
    Returns a tuple of (is_active, done, duration).
    """
    from app.models import SeatAttendanceState, StudentBlock

    if not seat_id or not class_id:
        raise ValueError("get_session_status requires seat_id and class_id.")
    latest_state = SeatAttendanceState.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
    ).order_by(SeatAttendanceState.updated_at.desc()).first()
    is_active = latest_state.is_active if latest_state else False

    today_local = get_class_now(class_id).date()
    done = False
    if latest_state and latest_state.done_for_day_date == today_local:
        done = True
    else:
        block_query = StudentBlock.query.filter(
            StudentBlock.seat_id == seat_id,
            StudentBlock.class_id == class_id,
            StudentBlock.period == period,
            StudentBlock.done_for_day_date.isnot(None),
        )
        done = block_query.filter(StudentBlock.done_for_day_date == today_local).first() is not None

    # Calculate unpaid duration
    last_payroll_time = get_last_payroll_time(seat_id=seat_id, class_id=class_id)
    duration = calculate_unpaid_attendance_seconds(seat_id, class_id, period, last_payroll_time)

    return is_active, done, duration


def get_all_block_statuses(student, *, class_id: str):
    """Return block statuses within one canonical class scope."""
    if not class_id:
        raise ValueError("get_all_block_statuses requires class_id.")
    return _get_all_block_statuses(student, class_id=class_id)

# -------------------------------------------------------------------
# BATCH OPTIMIZATION HELPERS
# -------------------------------------------------------------------

def get_batch_attendance_events(seat_ids, min_anchor, allowed_class_ids):
    """
    Fetch attendance transitions from canonical attendance sessions.
    Returns a dict: (seat_id, period_upper, class_id) -> list of event-like rows
    with ``status`` and ``timestamp`` fields.

    SECURITY: ``allowed_class_ids`` is required to restrict results to explicit
    tenant-owned class scopes.
    """
    if not seat_ids:
        return {}
    if not allowed_class_ids:
        return {}

    min_anchor_utc = ensure_utc(min_anchor) if min_anchor else None
    query = AttendanceSession.query.filter(
        AttendanceSession.seat_id.in_(seat_ids),
        AttendanceSession.class_id.in_(allowed_class_ids),
    )

    if min_anchor_utc:
        query = query.filter(
            sa.or_(
                AttendanceSession.started_at > min_anchor_utc,
                AttendanceSession.ended_at.is_(None),
                AttendanceSession.ended_at > min_anchor_utc,
            )
        )

    sessions = query.order_by(AttendanceSession.started_at.asc(), AttendanceSession.id.asc()).all()

    grouped = {}
    for session in sessions:
        start_time = ensure_utc(session.started_at)
        end_time = ensure_utc(session.ended_at) if session.ended_at else None

        if min_anchor_utc:
            if end_time is not None and end_time <= min_anchor_utc:
                continue
            active_at = max(start_time, min_anchor_utc)
        else:
            active_at = start_time

        key = (session.seat_id, (session.period or "").upper(), session.class_id)
        grouped.setdefault(key, []).append(
            SimpleNamespace(
                student_id=session.student_id,
                seat_id=session.seat_id,
                period=session.period,
                class_id=session.class_id,
                status="active",
                timestamp=active_at,
            )
        )

        if end_time and (not min_anchor_utc or end_time > min_anchor_utc):
            grouped[key].append(
                SimpleNamespace(
                    student_id=session.student_id,
                    seat_id=session.seat_id,
                    period=session.period,
                    class_id=session.class_id,
                    status="inactive",
                    timestamp=end_time,
                )
            )

    for events in grouped.values():
        events.sort(key=lambda event: (ensure_utc(event.timestamp), 0 if event.status == "active" else 1))

    return grouped

def calculate_seconds_in_memory(events, anchor):
    """
    Calculate unpaid seconds from a sorted list of events, strictly after anchor.
    """
    total_seconds = 0
    in_time = None

    anchor = ensure_utc(anchor)

    for event in events:
        event_time = ensure_utc(event.timestamp)

        # Skip events before specific anchor
        if anchor and event_time <= anchor:
            # If active, it effectively sets in_time for subsequent period
            if event.status == 'active':
                in_time = event_time
            else:
                in_time = None
            continue

        # If we crossed the anchor boundary and in_time was set from a pre-anchor event
        if in_time and in_time < anchor:
            in_time = anchor

        if event.status == 'active':
            if in_time is None:
                in_time = event_time
        elif event.status == 'inactive' and in_time:
            total_seconds += (event_time - in_time).total_seconds()
            in_time = None

    # If still active at "now"
    if in_time:
        if anchor and in_time < anchor:
            in_time = anchor

        now = utc_now()
        total_seconds += (now - in_time).total_seconds()

    return int(total_seconds)

@feat_shell("FEAT-ATTN-001")
def batch_auto_tapout_students(admin_id):
    """
    Optimized version of auto-tapout that processes all students for an admin in batch.
    Returns the count of students tapped out.
    """
    from app.models import Student, AttendanceReasonCode, StudentBlock, PayrollSettings, Seat, ClassEconomy, IdentityProfile
    from app.extensions import db

    # 1. Get all students for this admin via canonical class seats
    student_ids = [
        row[0] for row in db.session.query(Student.id)
        .join(IdentityProfile, IdentityProfile.id == Student.identity_id)
        .join(Seat, Seat.id == IdentityProfile.seat_id)
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(ClassEconomy.teacher_id == admin_id)
        .distinct()
        .all()
    ]

    if not student_ids:
        return 0

    # 1b. SECURITY: Fetch only class scopes owned by this admin.
    admin_class_rows = db.session.query(ClassEconomy.class_id, ClassEconomy.join_code).filter(
        ClassEconomy.teacher_id == admin_id,
        ClassEconomy.class_id.isnot(None),
    ).distinct().all()
    admin_class_ids = [row.class_id for row in admin_class_rows if row.class_id]
    join_code_by_class_id = {row.class_id: row.join_code for row in admin_class_rows if row.class_id}

    if not admin_class_ids:
        return 0

    now_utc = utc_now()
    class_day_start_by_class_id = {}
    class_today_by_class_id = {}
    for class_id in admin_class_ids:
        day_start_utc, _ = get_class_today_range(class_id, reference_time_utc=now_utc)
        class_day_start_by_class_id[class_id] = day_start_utc
        class_today_by_class_id[class_id] = get_class_now(class_id, reference_time_utc=now_utc).date()

    if class_day_start_by_class_id:
        start_of_day_utc = min(class_day_start_by_class_id.values())
    else:
        start_of_day_utc, _ = local_date_range_utc(
            class_date(timezone_name="America/Los_Angeles", timestamp_utc=now_utc),
            timezone_name="America/Los_Angeles",
        )
    default_today_local = class_date(timestamp_utc=now_utc)

    claimed_seats = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(Seat.class_id.in_(admin_class_ids), Student.id.in_(student_ids), Seat.claimed_at.isnot(None))
        .all()
    )
    if not claimed_seats:
        return 0
    seat_ids = [seat.id for seat in claimed_seats]

    # 3. Batch fetch events for today, scoped to this admin's class_ids only.
    # events_map: (seat_id, period, class_id) -> list[event-like]
    events_map = get_batch_attendance_events(seat_ids, start_of_day_utc, allowed_class_ids=admin_class_ids)

    # Lookup by canonical actor scope for fast iteration
    seats_by_student_period = {}
    for seat in claimed_seats:
        blk = (seat.block or "").strip().upper()
        if not blk:
            continue
        seats_by_student_period.setdefault(seat.student_id, {}).setdefault(blk, []).append(seat)

    # 4. Batch fetch PayrollSettings
    payroll_settings = PayrollSettings.query.filter(
        PayrollSettings.class_id.in_(admin_class_ids),
        PayrollSettings.is_active == True
    ).all()
    limits_map = {}

    def get_limit(setting):
        if not setting: return None
        if setting.settings_mode == 'simple' and setting.daily_limit_hours:
            return int(setting.daily_limit_hours * 3600)
        elif setting.settings_mode == 'advanced' and setting.max_time_per_day:
            multiplier = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}.get(setting.max_time_per_day_unit, 3600)
            return int(setting.max_time_per_day * multiplier)
        return None

    global_setting = next((s for s in payroll_settings if s.block is None), None)
    global_limit = get_limit(global_setting)

    for s in payroll_settings:
        if s.block:
            limit = get_limit(s)
            if limit is not None:
                limits_map[s.block.upper()] = limit

    # 5. Batch fetch Students to get their blocks
    students = Student.query.filter(Student.id.in_(student_ids)).all()

    # 6. Iterate and check
    tapped_out_count = 0

    for student in students:
        student_blocks = [b.strip().upper() for b in (student.block or "").split(',') if b.strip()]

        for period in student_blocks:
            seat_rows = seats_by_student_period.get(student.id, {}).get(period, [])
            for seat_row in seat_rows:
                class_id = seat_row.class_id
                resolved_seat_id = seat_row.id
                events = events_map.get((resolved_seat_id, period, class_id), [])
                if not events:
                    continue

                last_event = events[-1]
                if last_event.status != 'active':
                    continue

                # Calculate duration today
                duration = calculate_seconds_in_memory(events, start_of_day_utc)

                # Get limit
                limit = limits_map.get(period, global_limit)

                if limit and duration >= limit:
                    # Limit reached. Tap out.
                    hours_limit = limit / 3600.0
                    overage = duration - limit
                    # Timestamp backdated to when limit was reached
                    tapout_ts = now_utc - timedelta(seconds=max(0, overage))
                    if tapout_ts > now_utc: tapout_ts = now_utc

                    if not class_id or not resolved_seat_id:
                        continue
                    join_code = join_code_by_class_id.get(class_id)
                    student_tap(
                        student_id=student.id,
                        seat_id=resolved_seat_id,
                        class_id=class_id,
                        join_code=join_code,
                        period=period,
                        status="inactive",
                        reason=f"Daily limit ({hours_limit:.1f}h) reached",
                        reason_code=AttendanceReasonCode.DAILY_LIMIT,
                        timestamp_utc=tapout_ts,
                    )
                    tapped_out_count += 1

                    # Lock student
                    sb = StudentBlock.query.filter_by(
                        seat_id=resolved_seat_id,
                        class_id=class_id,
                        period=period,
                    ).first()
                    if not sb:
                        sb = StudentBlock(
                            seat_id=resolved_seat_id,
                            class_id=class_id,
                            student_id=student.id,
                            period=period,
                            tap_enabled=True,
                            join_code=join_code
                        )
                        db.session.add(sb)
                    sb.done_for_day_date = class_today_by_class_id.get(class_id, default_today_local)

    if tapped_out_count > 0:
        try:
            db.session.flush()  # FEAT-AUTHORIZED-SHELL
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing batch auto-tapout: {e}", exc_info=True)
            return 0

    return tapped_out_count
