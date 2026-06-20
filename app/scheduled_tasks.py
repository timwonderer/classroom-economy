"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
from datetime import datetime, timezone, timedelta
from app.utils.time import get_class_cycle_start_utc, utc_now
from app.feats.base import feat_shell


@feat_shell("FEAT-ATTN-001")
def enforce_daily_limits_job():
    """
    Scheduled job that checks all active students and auto-taps them out if they've exceeded their daily limit.
    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    # Import here to avoid circular imports
    from app.models import AttendanceSession, SeatAttendanceState, Student, AttendanceReasonCode
    from app.feats.attendance import enforce_daily_limits as feat_enforce_daily_limits
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled auto tap-out enforcement job")

    try:
        # Load all students into memory first to avoid named cursor issues
        # yield_per() creates a server-side cursor that gets invalidated by commit()
        students = Student.query.all()
        checked_count = 0
        tapped_out_count = 0

        for student in students:
            try:
                # Isolate each student in a savepoint so one failure doesn't
                # discard successful mutations for prior students.
                with db.session.begin_nested():
                    # Get the student's current active sessions
                    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
                    has_active_session = False

                    for period in student_blocks:
                        state = (
                            SeatAttendanceState.query
                            .filter_by(student_id=student.id, period=period)
                            .order_by(SeatAttendanceState.updated_at.desc())
                            .first()
                        )

                        # If student is active, check their limit
                        if state and state.is_active:
                            has_active_session = True
                            break

                    if has_active_session:
                        checked_count += 1
                        # Compare canonical daily-limit session closures before/after.
                        before_daily_limit_count = (
                            AttendanceSession.query
                            .filter(
                                AttendanceSession.student_id == student.id,
                                AttendanceSession.end_reason_code == AttendanceReasonCode.DAILY_LIMIT,
                                AttendanceSession.ended_at.is_not(None),
                            )
                            .count()
                        )

                        feat_enforce_daily_limits(student=student, commit=False, logger=logger)

                        after_daily_limit_count = (
                            AttendanceSession.query
                            .filter(
                                AttendanceSession.student_id == student.id,
                                AttendanceSession.end_reason_code == AttendanceReasonCode.DAILY_LIMIT,
                                AttendanceSession.ended_at.is_not(None),
                            )
                            .count()
                        )

                        newly_closed = max(0, after_daily_limit_count - before_daily_limit_count)
                        if newly_closed:
                            tapped_out_count += newly_closed
                            logger.info(
                                "Auto-tapped out student %s (%s) in %s class sessions",
                                student.id,
                                student.full_name,
                                newly_closed,
                            )
            except Exception as e:
                logger.error(f"Error checking student {student.id}: {e}", exc_info=True)
                continue
        logger.info(f"Auto tap-out job completed. Checked {checked_count} active students, tapped out {tapped_out_count}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Auto tap-out job failed: {e}", exc_info=True)


@feat_shell("FEAT-OPS-001")
def database_maintenance_job():
    """
    Scheduled job that performs nightly database maintenance tasks.
    Runs at 2 AM UTC to clean up orphaned entries and maintain data integrity.
    """
    # Import here to avoid circular imports
    from sqlalchemy import and_, or_, tuple_
    from app.models import Seat, StoreItemBlock, StoreItem
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly database maintenance job")

    total_cleaned = 0

    try:
        # Task 1: Clean up orphaned StoreItemBlock entries.
        # StoreItemBlock entries are class-scoped (store_item_id, class_id, block).
        # They are orphaned when:
        #   a) The parent StoreItem no longer exists (FK cascade should handle; explicit check as safety net).
        #   b) The class_id is set but no Seat with that block identifier exists in that class
        #      (the block period was retired while the class still exists).
        logger.info("Checking for orphaned StoreItemBlock entries...")

        # Subquery: active (class_id, block) pairs that exist in canonical Seat records
        active_class_blocks_subq = (
            db.session.query(
                Seat.class_id.label("class_id"),
                Seat.block.label("block"),
            )
            .filter(Seat.block.isnot(None), Seat.class_id.isnot(None))
            .distinct()
            .subquery()
        )

        orphaned_entries_subq = (
            db.session.query(
                StoreItemBlock.store_item_id.label("store_item_id"),
                StoreItemBlock.block.label("block"),
            )
            .outerjoin(StoreItem, StoreItem.id == StoreItemBlock.store_item_id)
            .outerjoin(
                active_class_blocks_subq,
                and_(
                    active_class_blocks_subq.c.class_id == StoreItemBlock.class_id,
                    active_class_blocks_subq.c.block == StoreItemBlock.block,
                ),
            )
            .filter(
                or_(
                    StoreItem.id.is_(None),
                    and_(
                        StoreItemBlock.class_id.isnot(None),
                        active_class_blocks_subq.c.class_id.is_(None),
                    ),
                )
            )
            .distinct()
            .subquery()
        )

        orphaned_count = db.session.query(orphaned_entries_subq).count()
        if orphaned_count:
            logger.info("Found %s orphaned StoreItemBlock entries", orphaned_count)
            total_cleaned = (
                StoreItemBlock.query
                .filter(
                    tuple_(StoreItemBlock.store_item_id, StoreItemBlock.block).in_(
                        db.session.query(
                            orphaned_entries_subq.c.store_item_id,
                            orphaned_entries_subq.c.block,
                        )
                    )
                )
                .delete(synchronize_session=False)
            )
            db.session.flush()  # FEAT-AUTHORIZED-SHELL
            logger.info("Cleaned up %s orphaned StoreItemBlock entries", total_cleaned)
        else:
            logger.info("No orphaned StoreItemBlock entries found")

        logger.info(
            "Skipping legacy join_code backfill in nightly maintenance; "
            "records are expected to already be join_code-scoped."
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
    from app.models import RentSettings, RentPayment, Seat
    from app.feats.rent_cycle_feat import execute_scheduled_rent_charge
    from app.services.obligations_service import activate_next_rent_policy_version

    execution_time = execution_time or utc_now()

    settings = (
        RentSettings.query
        .filter_by(class_id=class_id, is_enabled=True)
        .order_by(RentSettings.updated_at.desc())
        .first()
    )
    if not settings:
        return {"status": "skipped", "reason": "rent_disabled_or_missing", "class_id": class_id}

    # Cycle boundary: promote next_version → active_version if queued
    activate_next_rent_policy_version(class_id)

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
    cycle_start = get_class_cycle_start_utc(
        class_id,
        execution_time,
        cycle_length_days=cycle_length_days,
        effective_start_utc=rent_effective_at,
    )

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
        existing = RentPayment.query.filter_by(
            class_id=class_id,
            seat_id=seat.id,
            cycle_idempotency_key=idem_key,
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

    execution_time = execution_time or utc_now()
    class_ids = [
        class_id for (class_id,) in
        RentSettings.query.filter(
            RentSettings.is_enabled.is_(True),
            RentSettings.class_id.is_not(None),
        ).with_entities(RentSettings.class_id).distinct().all()
    ]

    outcomes = []
    for class_id in class_ids:
        outcomes.append(run_rent_cycle_for_class(class_id, execution_time))
    return outcomes


def run_audit_invariant_check_job():
    """Nightly audit chain integrity verification.

    Walks all active class chains and the system chain, recomputing HMAC
    signatures and verifying hash continuity. Writes the aggregate result to
    IntegrityStatus, which is exposed by /health/deep.
    """
    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting nightly audit invariant check")
    try:
        from app.utils.audit_verifier import run_full_invariant_check, update_integrity_status
        results = run_full_invariant_check()
        update_integrity_status(results)

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

    def run_audit_invariant_check():
        with app.app_context():
            run_audit_invariant_check_job()

    if not scheduler.running:
        # Add the auto tap-out enforcement job to run every hour
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
            "Scheduled tasks initialized: auto tap-out (hourly), "
            "database maintenance (2 AM UTC), rent cycles (hourly), "
            "audit invariant check (3 AM UTC)"
        )
    else:
        logger.info("Scheduler already running")
