"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
import secrets
from app.feats.base import feat_shell
from app.services.insurance_policy_service import delete_due_policy_lineages
# TODO (Phase 4): insurance_billing deleted; move to Obligations domain
# from app.utils.insurance_billing import get_insurance_billing_snapshot


@feat_shell("FEAT-PROD-001")
def enforce_daily_limits_job():
    """
    Scheduled job that checks active seats and records an inactive PROD event
    when the class daily limit has been reached.

    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    from app.feats.prod import record_attendance_session
    from app.extensions import db
    from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, Seat
    from app.payroll import get_daily_limit_seconds
    from app.services.context_resolver import CanonicalContext
    from app.services.ledger_service import resolve_class_authority_seat_id
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
    )

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled daily-limit enforcement job")

    try:
        events = (
            AttendanceSession.query
            .order_by(
                AttendanceSession.class_id.asc(),
                AttendanceSession.target_seat_id.asc(),
                AttendanceSession.timestamp.asc(),
                AttendanceSession.id.asc(),
            )
            .all()
        )
        rows_by_class_id = {}
        rows_by_scope = {}
        for event in events:
            rows_by_class_id.setdefault(event.class_id, []).append(event)
            rows_by_scope.setdefault((event.class_id, event.target_seat_id), []).append(event)

        checked_count = 0
        closed_count = 0

        def _active_intervals_for_day(rows, *, day_start_utc, now_utc):
            intervals = []
            active_start = None
            for row in rows:
                if row.timestamp > now_utc:
                    break
                if row.status == "active":
                    active_start = row.timestamp
                    continue
                if row.status == "inactive" and active_start is not None:
                    interval_start = max(active_start, day_start_utc)
                    interval_end = min(row.timestamp, now_utc)
                    if interval_end >= interval_start:
                        intervals.append((interval_start, interval_end))
                    active_start = None
            if active_start is not None:
                interval_start = max(active_start, day_start_utc)
                if now_utc >= interval_start:
                    intervals.append((interval_start, now_utc))
            return intervals

        for class_id, class_events in rows_by_class_id.items():
            class_row = ClassEconomy.query.filter_by(class_id=class_id).first()
            if class_row is None:
                continue

            daily_limit = (
                get_daily_limit_seconds(class_row.section, class_id=class_id)
                if class_row.section else None
            )
            if not daily_limit:
                continue

            actor_seat_id = resolve_class_authority_seat_id(class_id)
            ctx = CanonicalContext(
                user_id=class_row.user_id,
                class_id=class_id,
                seat_id=actor_seat_id,
                actor_role="teacher",
            )
            now_evaluation = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            )
            now_utc = now_evaluation.canonical_now_utc
            day_bounds = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="evaluation_day_boundaries",
                reference_time_utc=now_utc,
            )

            active_latest_events = {}
            for event in class_events:
                active_latest_events[event.target_seat_id] = event

            for seat_id, latest_event in active_latest_events.items():
                if latest_event.status != "active":
                    continue
                try:
                    with db.session.begin_nested():
                        checked_count += 1

                        seat = Seat.query.filter_by(
                            id=seat_id,
                            class_id=class_id,
                            role="student",
                        ).first()
                        if seat is None:
                            continue

                        intervals = _active_intervals_for_day(
                            rows_by_scope[(class_id, seat_id)],
                            day_start_utc=day_bounds.boundary_start_utc,
                            now_utc=now_utc,
                        )
                        if not intervals:
                            continue

                        total_evaluation = canonical_temporal_resolver(
                            CLASS_LEVEL_EVALUATION,
                            canonical_execution_context=ctx,
                            primitive="elapsed_duration",
                            reference_time_utc=now_utc,
                            intervals=intervals,
                        )
                        if total_evaluation.elapsed_seconds < daily_limit:
                            continue

                        accumulated_before_active = 0
                        active_start, _active_end = intervals[-1]
                        if len(intervals) > 1:
                            prior_evaluation = canonical_temporal_resolver(
                                CLASS_LEVEL_EVALUATION,
                                canonical_execution_context=ctx,
                                primitive="elapsed_duration",
                                reference_time_utc=now_utc,
                                intervals=intervals[:-1],
                            )
                            accumulated_before_active = prior_evaluation.elapsed_seconds

                        remaining_seconds = int(daily_limit) - int(accumulated_before_active)
                        close_at_utc = active_start
                        if remaining_seconds > 0:
                            close_evaluation = canonical_temporal_resolver(
                                CLASS_LEVEL_EVALUATION,
                                canonical_execution_context=ctx,
                                primitive="shift_timestamp",
                                reference_time_utc=now_utc,
                                timestamp=active_start,
                                elapsed_seconds=remaining_seconds,
                            )
                            close_at_utc = close_evaluation.shifted_timestamp_utc

                        reached_at_or_before_now = canonical_temporal_resolver(
                            CLASS_LEVEL_EVALUATION,
                            canonical_execution_context=ctx,
                            primitive="later_than",
                            reference_time_utc=now_utc,
                            candidate=now_utc,
                            reference=close_at_utc,
                        )
                        if not reached_at_or_before_now.is_later and now_utc != close_at_utc:
                            continue

                        record_attendance_session(
                            ctx=ctx,
                            target_seat_id=seat_id,
                            actor_seat_id=actor_seat_id,
                            mechanism="system",
                            status="inactive",
                            reason=f"Daily limit reached ({daily_limit / 3600:.1f}h)",
                            reason_code=AttendanceReasonCode.DONE_FOR_DAY,
                            idempotency_key=f"daily_limit:{class_id}:{seat_id}:{secrets.token_hex(12)}",
                            reference_time_utc=close_at_utc,
                        )

                        closed_count += 1
                        logger.info(
                            "Closed daily-limit attendance session for seat %s in class %s at %s",
                            seat_id,
                            class_id,
                            close_at_utc,
                        )
                except Exception as e:
                    logger.error(
                        "Error checking daily limit for seat %s in class %s: %s",
                        seat_id,
                        class_id,
                        e,
                        exc_info=True,
                    )
                    continue
        logger.info(
            "Daily-limit enforcement job completed. Checked %s active seats, closed %s sessions",
            checked_count,
            closed_count,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Daily-limit enforcement job failed: {e}", exc_info=True)


@feat_shell("FEAT-OPS-001")
def database_maintenance_job():
    """
    Scheduled job that performs nightly database maintenance tasks.
    Runs at 2 AM UTC to clean up orphaned entries and maintain data integrity.
    """
    # Import here to avoid circular imports
    from app.models import StoreItem
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly database maintenance job")

    total_cleaned = 0

    try:
        # Task 1: StoreItemBlock orphan cleanup REMOVED.
        # store_item_blocks table dropped (migration 7c3d4e5f6a7b) — unauthorized per DOM-STORE-001.
        # Canonical replacement: store_item_visibility (seat_id scoped, no block/period key).
        # TODO: Implement store_item_visibility orphan cleanup if needed.
        logger.info("StoreItemBlock cleanup skipped — table dropped (migration 7c3d4e5f6a7b)")

        logger.info(
            "Skipping legacy join_code backfill in nightly maintenance; "
            "records are expected to already be class-scoped."
        )
        logger.info(f"Database maintenance completed. Total orphaned entries cleaned: {total_cleaned}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database maintenance job failed: {e}", exc_info=True)


def _derive_cycle_length_days(settings) -> int:
    """Resolve cycle length in days from rent settings."""
    configured = int(getattr(settings, "cycle_length_days", 0) or 0)
    if configured > 0:
        return configured

    frequency = (getattr(settings, "frequency_type", "monthly") or "monthly").lower()
    if frequency == "daily":
        return 1
    if frequency == "weekly":
        return 7
    if frequency == "custom":
        unit = (getattr(settings, "custom_frequency_unit", "days") or "days").lower()
        value = int(getattr(settings, "custom_frequency_value", 1) or 1)
        if unit.startswith("week"):
            return max(1, value * 7)
        if unit.startswith("month"):
            return max(1, value * 30)
        return max(1, value)
    return 30


@feat_shell("FEAT-OBL-002")
def run_rent_cycle_for_class(class_id: str, execution_time):
    """
    Execute one rent cycle for one class.

    Actor model: seat_id + class_id only.
    """
    from app.extensions import db
    from app.models import RentSettings, Seat, ObligationAssessment
    from app.feats.rent_cycle_feat import execute_scheduled_rent_charge
    from datetime import timedelta
    from app.utils.canonical_temporal_resolver import utc_now

    execution_time = execution_time or utc_now()

    settings = (
        RentSettings.query
        .filter_by(class_id=class_id)
        .order_by(RentSettings.updated_at.desc())
        .first()
    )
    if not settings:
        return {"status": "skipped", "reason": "rent_disabled_or_missing", "class_id": class_id}

    cycle_length_days = _derive_cycle_length_days(settings)
    settings.cycle_length_days = cycle_length_days

    rent_configured_at = settings.rent_configured_at or settings.updated_at or utc_now()
    if not settings.rent_effective_at:
        settings.rent_effective_at = rent_configured_at + timedelta(days=cycle_length_days)
        db.session.flush()

    rent_effective_at = settings.rent_effective_at
    if execution_time < rent_effective_at:
        return {"status": "skipped", "reason": "before_effective_at", "class_id": class_id}

    # Freeze deterministic class-local cycle boundary for the full execution.
    # Use class-local date arithmetic (not UTC seconds) so DST transitions
    # don't shift cycle boundaries.
    from datetime import datetime as _dt, timezone as _tz
    from app.utils.canonical_temporal_resolver import _get_class_timezone
    class_tz = _get_class_timezone(class_id)
    effective_local = rent_effective_at.astimezone(class_tz)
    exec_local = execution_time.astimezone(class_tz)
    elapsed_days = (exec_local.date() - effective_local.date()).days
    cycles_completed = elapsed_days // cycle_length_days
    cycle_start_date = effective_local.date() + timedelta(days=cycles_completed * cycle_length_days)
    cycle_start = class_tz.localize(
        _dt.combine(cycle_start_date, effective_local.time())
    ).astimezone(_tz.utc)

    claimed_seats = Seat.query.filter(
        Seat.class_id == class_id,
        Seat.claimed_at.is_not(None),
    ).all()

    charged = 0
    exempted = 0
    skipped_existing = 0

    for seat in claimed_seats:
        if (
            seat.claimed_at
            and seat.claimed_at >= rent_configured_at
            and not seat.has_received_rent_exemption
        ):
            seat.has_received_rent_exemption = True
            exempted += 1
            continue

        idem_key = f"rent_cycle:{class_id}:{seat.id}:{cycle_start.isoformat()}"
        existing = ObligationAssessment.query.filter_by(
            class_id=class_id,
            seat_id=seat.id,
            cycle_idempotency_key=idem_key,
            obligation_type="RENT",
        ).first()
        if existing:
            skipped_existing += 1
            continue

        execute_scheduled_rent_charge(
            seat=seat,
            settings=settings,
            class_id=class_id,
            execution_time=cycle_start,
            idempotency_key=idem_key,
        )
        charged += 1

    db.session.flush()  # FEAT-AUTHORIZED-SHELL
    return {
        "status": "ok",
        "class_id": class_id,
        "charged": charged,
        "exempted": exempted,
        "skipped_existing": skipped_existing,
    }


def run_rent_cycle_scheduler(execution_time=None):
    """
    Iterate all rent-enabled classes and execute one rent cycle per class.
    """
    from app.models import RentSettings
    # TODO(SPEC-TIME-001): Legacy OBL scheduler exception.
    # Switch this to canonical_temporal_resolver during OBL rewiring instead of widening
    # the current PROD slice.
    from app.utils.canonical_temporal_resolver import utc_now

    execution_time = execution_time or utc_now()
    class_ids = [
        class_id for (class_id,) in
        RentSettings.query.filter(
            
            RentSettings.class_id.is_not(None),
        ).with_entities(RentSettings.class_id).distinct().all()
    ]

    outcomes = []
    for class_id in class_ids:
        outcomes.append(run_rent_cycle_for_class(class_id, execution_time))
    return outcomes


def _get_active_insurance_policy_version(class_id: str):
    from app.models import PolicyVersion

    return (
        PolicyVersion.query.filter_by(class_id=class_id, domain="insurance", is_active=True)
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .first()
    )


@feat_shell("FEAT-OBL-003")
def run_insurance_cycle_for_class(class_id: str, execution_time):
    """Execute one insurance cycle for one class, evaluated per seat."""
    from app.extensions import db
    from app.models import ObligationAssessment, Seat
    from app.feats.insurance_cycle_feat import execute_scheduled_insurance_charge
    # TODO(SPEC-TIME-001): Legacy insurance/OBL scheduler exception.
    # Switch this to canonical_temporal_resolver when that domain slice is rewired.
    from app.utils.canonical_temporal_resolver import utc_now

    execution_time = execution_time or utc_now()
    policy_version = _get_active_insurance_policy_version(class_id)
    if not policy_version:
        return {"status": "skipped", "reason": "insurance_disabled_or_missing", "class_id": class_id}

    try:
        snapshot = get_insurance_billing_snapshot(policy_version)
    except NameError:
        return {
            "status": "skipped",
            "reason": "insurance_billing_helper_unavailable",
            "class_id": class_id,
        }
    seats = Seat.query.filter(
        Seat.class_id == class_id,
        Seat.role == "student",
        Seat.claimed_at.is_not(None),
    ).all()

    charged = 0
    skipped_existing = 0

    for seat in seats:
        idem_key = f"insurance_cycle:{class_id}:{seat.id}:{execution_time.isoformat()}"
        existing = ObligationAssessment.query.filter_by(
            class_id=class_id,
            seat_id=seat.id,
            cycle_idempotency_key=idem_key,
            obligation_type="INSURANCE_PREMIUM",
        ).first()
        if existing:
            skipped_existing += 1
            continue

        execute_scheduled_insurance_charge(
            seat=seat,
            policy_version=policy_version,
            class_id=class_id,
            execution_time=execution_time,
            idempotency_key=idem_key,
        )
        charged += 1

    db.session.flush()
    return {
        "status": "ok",
        "class_id": class_id,
        "charged": charged,
        "skipped_existing": skipped_existing,
        "cycle_length_days": snapshot["cycle_length_days"],
    }


def run_insurance_cycle_scheduler(execution_time=None):
    """Iterate all insurance-enabled classes and execute one insurance cycle per class."""
    from app.models import PolicyVersion
    # TODO(SPEC-TIME-001): Legacy insurance/OBL scheduler exception.
    # Switch this to canonical_temporal_resolver when that domain slice is rewired.
    from app.utils.canonical_temporal_resolver import utc_now

    execution_time = execution_time or utc_now()
    class_ids = [
        class_id for (class_id,) in
        PolicyVersion.query.filter_by(domain="insurance", is_active=True)
        .with_entities(PolicyVersion.class_id)
        .distinct()
        .all()
    ]

    outcomes = []
    for class_id in class_ids:
        outcomes.append(run_insurance_cycle_for_class(class_id, execution_time))
    delete_due_policy_lineages(execution_time=execution_time)
    return outcomes


def run_audit_invariant_check_job():
    """Nightly audit chain integrity verification.

    Walks all active class chains and the system chain, recomputing HMAC
    signatures and verifying hash continuity. Writes the aggregate result to
    the deep health endpoint.
    """
    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly audit invariant check")
    try:
        from app.utils.audit_verifier import run_full_invariant_check, record_integrity_verification
        results = run_full_invariant_check()
        record_integrity_verification(results)

        passing = all(r.state == "VERIFIED" for r in results)
        if passing:
            logger.info(
                "Audit invariant check passed: %d chain(s) verified", len(results)
            )
        else:
            failed = [r for r in results if r.state != "VERIFIED"]
            logger.error(
                "Audit invariant check FAILED: %d/%d chain(s) invalid — %s",
                len(failed),
                len(results),
                [{"scope": r.chain_scope, "type": r.failure_type} for r in failed],
            )
    except Exception:
        logger.exception("Audit invariant check job encountered an unhandled error")


def init_scheduled_tasks(app):
    """
    Initialize and start scheduled tasks.

    Args:
        app: Flask application instance
    """
    from app.extensions import scheduler

    logger = logging.getLogger('scheduled_tasks')

    # Wrapper function that runs the enforce_daily_limits_job with Flask app context
    def run_enforce_daily_limits():
        with app.app_context():
            enforce_daily_limits_job()

    # Wrapper function that runs the database_maintenance_job with Flask app context
    def run_database_maintenance():
        with app.app_context():
            database_maintenance_job()

    def run_scheduled_rent_cycles():
        with app.app_context():
            run_rent_cycle_scheduler()

    def run_scheduled_insurance_cycles():
        with app.app_context():
            run_insurance_cycle_scheduler()

    def run_audit_invariant_check():
        with app.app_context():
            run_audit_invariant_check_job()

    if not scheduler.running:
        # Add the daily-limit enforcement job to run every hour
        scheduler.add_job(
            func=run_enforce_daily_limits,
            trigger='interval',
            hours=1,
            id='enforce_daily_limits',
            name='Enforce daily attendance limits',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        # Add the database maintenance job to run nightly at 2 AM UTC
        scheduler.add_job(
            func=run_database_maintenance,
            trigger='cron',
            hour=2,
            minute=0,
            id='database_maintenance',
            name='Nightly database maintenance',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        scheduler.add_job(
            func=run_scheduled_rent_cycles,
            trigger='cron',
            hour='*',
            minute=5,
            id='run_rent_cycles',
            name='Run class-scoped rent cycles',
            replace_existing=True,
            max_instances=1
        )

        scheduler.add_job(
            func=run_scheduled_insurance_cycles,
            trigger='cron',
            hour='*',
            minute=10,
            id='run_insurance_cycles',
            name='Run seat-scoped insurance cycles',
            replace_existing=True,
            max_instances=1
        )

        # Nightly audit chain integrity check — runs at 3 AM UTC (after maintenance)
        scheduler.add_job(
            func=run_audit_invariant_check,
            trigger='cron',
            hour=3,
            minute=0,
            id='audit_invariant_check',
            name='Nightly audit chain integrity verification',
            replace_existing=True,
            max_instances=1
        )

        scheduler.start()
        logger.info(
            "Scheduled tasks initialized: daily-limit enforcement (hourly), "
            "database maintenance (2 AM UTC), rent cycles (hourly), "
            "insurance cycles (hourly), "
            "audit invariant check (3 AM UTC)"
        )
    else:
        logger.info("Scheduler already running")
