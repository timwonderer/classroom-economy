"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
import secrets
from app.feats.base import FEATContextError, requires_feat_context
from app.services.insurance_policy_service import delete_due_policy_lineages
# TODO (Phase 4): insurance_billing deleted; move to Obligations domain
# from app.utils.insurance_billing import get_insurance_billing_snapshot


@requires_feat_context("FEAT-PROD-001")
def enforce_daily_limits_job():
    """
    Scheduled job that checks active seats and records an inactive PROD event
    when the class daily limit has been reached.

    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    # Compose the Productivity domain command, not the FEAT-PROD-001 entry —
    # this job already owns the envelope and exactly one FEAT executes per
    # invocation (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).
    from app.feats.prod import _record_attendance_session_impl
    from app.extensions import db
    from app.models import AttendanceReasonCode, AttendanceSession, ClassEconomy, Seat
    from app.payroll import get_daily_limit_seconds
    from app.services.context_resolver import CanonicalContext
    from app.services.identity_service import resolve_teacher_seat_for_class
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

            actor_seat_id = resolve_teacher_seat_for_class(class_id).id
            ctx = CanonicalContext(
                user_id=class_row.teacher_user_id,
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

                        _record_attendance_session_impl(
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
                except FEATContextError:
                    # A constitutional violation is never per-seat noise. Swallowing
                    # it here is how this job reported success while closing zero
                    # sessions for eight weeks; let it abort the run and surface.
                    raise
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


@requires_feat_context("FEAT-OPS-001")
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

def run_rent_reconciliation_job():
    """Materialize the recurring rent lifecycle for every rent-enabled class.

    Canonical single mechanism (FEAT-OBL-002): for each class this creates the
    initial cycle + assessments on first run, advances successor cycles once a
    cycle's ``next_assessment_at`` has been reached, and expires the prior
    cycle's PERK hall passes at the rent boundary. The whole thing is idempotent,
    so re-running produces no duplicate cycles, assessments, or expiry events.

    Each class is reconciled under its OWN top-level FEAT transaction so a
    failure in one class cannot roll back or block another. This function is
    therefore a plain loop — it must NOT itself hold a FEAT context, which would
    force every class into a single shared correlation/transaction.
    """
    from app.extensions import db
    from app.models import ClassEconomy
    from app.services.class_configuration_query_service import is_feature_enabled
    from app.feats.reconcile_rent_feat import execute_reconcile_rent

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled rent reconciliation job")

    reconciled = 0
    skipped = 0
    failed = 0
    try:
        class_ids = [row.class_id for row in ClassEconomy.query.order_by(ClassEconomy.class_id.asc()).all()]
    except Exception:
        db.session.rollback()
        logger.exception("Rent reconciliation job could not enumerate classes")
        return

    for class_id in class_ids:
        # Class-level rent gate short-circuit (execute_reconcile_rent also guards,
        # but skipping here avoids opening a FEAT transaction for disabled classes).
        try:
            if not is_feature_enabled(class_id, "rent"):
                skipped += 1
                continue
            result = execute_reconcile_rent(class_id)
            reconciled += 1
            if result.cycles_created or result.perks_expired:
                logger.info(
                    "Rent reconciliation for class %s: reason=%s cycles=%s assessments=%s perks_expired=%s",
                    class_id,
                    result.reason,
                    result.cycles_created,
                    result.assessments_created,
                    result.perks_expired,
                )
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception("Rent reconciliation failed for class %s", class_id)
            continue

    logger.info(
        "Rent reconciliation job completed. Reconciled %s class(es), skipped %s, failed %s",
        reconciled,
        skipped,
        failed,
    )


def run_automatic_payroll_job():
    """Automatic payroll: fire the canonical completion FEAT for every due class.

    Automatic payroll is merely a second *initiation mechanism* for the same
    economic-cycle completion as manual payroll (DOM-PROD-001 §XV). This job owns
    exactly one question — "is this class due for automatic payroll now?" — and
    then becomes just another caller of ``complete_payroll_cycle``. It contains no
    payroll, interpretation, or activation logic of its own.

    A class is due when its active ``PayrollSettings`` carries a
    ``next_payroll_date`` at or before now. The **scheduled occurrence** (that
    ``next_payroll_date``) is the deterministic command identity: every retry of
    the same occurrence derives the same idempotency key, while the next intended
    occurrence — after ``next_payroll_date`` advances — derives a different one. So
    the ``payroll_cycle_completion`` anchor makes scheduler retries idempotent
    without any bespoke job-run substrate. Each class runs under its OWN top-level
    FEAT transaction (a plain loop, no shared FEAT context), so one class's failure
    cannot roll back or block another; the ``next_payroll_date`` advance commits
    atomically with the cycle so a failed run stays due under the same key.
    """
    from datetime import timedelta

    from app.extensions import db
    from app.feats.base import FEATContext
    from app.feats.complete_payroll_cycle import complete_payroll_cycle
    from app.models import ClassEconomy, PayrollSettings
    from app.services.class_configuration_query_service import is_feature_enabled
    from app.services.context_resolver import CanonicalContext
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.services.payroll.cycle_completion import get_completed_cycle_window
    from app.utils.canonical_temporal_resolver import (
        CLASS_LEVEL_EVALUATION,
        canonical_temporal_resolver,
        ensure_utc,
        utc_now,
    )

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled automatic-payroll job")

    now = utc_now()
    try:
        due_settings = (
            PayrollSettings.query
            .filter(
                PayrollSettings.availability_state == 'IN_USE',
                PayrollSettings.next_payroll_date.isnot(None),
                PayrollSettings.next_payroll_date <= now,
            )
            .order_by(PayrollSettings.class_id.asc())
            .all()
        )
    except Exception:
        db.session.rollback()
        logger.exception("Automatic-payroll job could not enumerate due classes")
        return

    ran = 0
    skipped = 0
    failed = 0
    for settings in due_settings:
        class_id = settings.class_id
        scheduled_occurrence = ensure_utc(settings.next_payroll_date)
        try:
            if not is_feature_enabled(class_id, "payroll"):
                skipped += 1
                continue
            class_row = db.session.get(ClassEconomy, class_id)
            if class_row is None or not class_row.teacher_user_id:
                skipped += 1
                continue

            ctx = CanonicalContext(
                user_id=class_row.teacher_user_id,
                class_id=class_id,
                seat_id=resolve_teacher_seat_for_class(class_id).id,
                actor_role="teacher",
            )
            boundary_utc = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=ctx,
                primitive="current_time",
            ).canonical_now_utc
            cycle_started_at, cycle_completed_at = get_completed_cycle_window(
                class_id, boundary_utc=boundary_utc
            )

            idempotency_key = f"auto-payroll:{class_id}:{scheduled_occurrence.isoformat()}"
            frequency_days = settings.payroll_frequency_days or 14
            with FEATContext("FEAT-PROD-004", idempotency_key=idempotency_key):
                complete_payroll_cycle(
                    ctx=ctx,
                    idempotency_key=idempotency_key,
                    cycle_started_at=cycle_started_at,
                    cycle_completed_at=cycle_completed_at,
                )
                # Scheduling bookkeeping (the scheduler's own concern), committed
                # atomically with the cycle so a failure leaves the class due.
                settings.next_payroll_date = scheduled_occurrence + timedelta(days=frequency_days)
            ran += 1
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception("Automatic payroll failed for class %s", class_id)
            continue

    logger.info(
        "Automatic-payroll job completed. Ran %s class(es), skipped %s, failed %s",
        ran, skipped, failed,
    )


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


def run_insurance_expiry_job():
    """Daily insurance boundary expiry: EXPIRE coverage whose cycle boundary passed.

    The canonical terminal disposition for purchased insurance is EXPIRED at the
    coverage boundary — never REVOKED or refunded (FEAT-STOR-002 §IX.C, DOM-STORE-001
    §1). Coverage stops renewing when its recurring premium lineage is terminated
    (a terminal ``bill_cycles`` row with ``next_assessment_at IS NULL`` — via
    FEAT-OBL-005 cancellation, teacher offering-cancel, or nonpayment non-renewal;
    DOM-OBL-001 §160/§241). This job is the Store-owned boundary trigger: it reads
    the bill-cycle table directly for terminal insurance lineages whose
    ``cycle_boundary_at`` has been reached and writes EXPIRED for the matching
    coverage through the FEAT-STOR-002 domain command.

    The work-list is the table itself — terminal rows past boundary — so there is no
    per-entitlement enumeration and no lag: a lineage becomes due the day its
    boundary arrives. Each expiry runs under its OWN top-level FEAT-STOR-002 context
    (isolated failure), and ``expire_entitlement`` is idempotent (an already-EXPIRED
    lineage is a no-op), so re-runs are safe.
    """
    from app.extensions import db
    from app.feats.base import FEATContext
    from app.models import BillCycle, ObligationAssessment
    from app.services import entitlement_service
    from app.services.entitlement_read_service import get_active_insurance_grant
    from app.services.identity_service import resolve_teacher_seat_for_class
    from app.utils.canonical_temporal_resolver import ensure_utc, utc_now

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled insurance boundary-expiry job")

    now = utc_now()
    try:
        terminal_cycles = (
            BillCycle.query
            .filter(
                BillCycle.next_assessment_at.is_(None),   # terminal — recurrence stopped
                BillCycle.cycle_boundary_at <= now,       # coverage boundary reached
            )
            .order_by(BillCycle.class_id.asc(), BillCycle.id.asc())
            .all()
        )
    except Exception:
        db.session.rollback()
        logger.exception("Insurance expiry job could not enumerate terminal cycles")
        return

    expired = 0
    skipped = 0
    failed = 0
    for cycle in terminal_cycles:
        try:
            # Resolve the seat/policy binding, which lives on the INSURANCE_PREMIUM
            # assessment the cycle drives (bill cycles are seat-blind). A cycle with
            # no insurance assessment is some other lineage (e.g. rent) — skip.
            assessment = (
                ObligationAssessment.query
                .filter_by(
                    internal_ref=cycle.internal_ref,
                    obligation_type="INSURANCE_PREMIUM",
                )
                .first()
            )
            if assessment is None:
                skipped += 1
                continue

            grant = get_active_insurance_grant(
                assessment.seat_id, assessment.class_id, assessment.policy_uuid
            )
            if grant is None:
                # Already expired (or no active coverage for this lineage).
                skipped += 1
                continue

            boundary = ensure_utc(cycle.cycle_boundary_at)
            idempotency_key = (
                f"insurance-expiry:{grant.entitlement_id}:{boundary.isoformat()}"
            )
            with FEATContext("FEAT-STOR-002", idempotency_key=idempotency_key):
                entitlement_service.expire_entitlement(
                    entitlement_id=grant.entitlement_id,
                    class_id=assessment.class_id,
                    target_seat_id=assessment.seat_id,
                    actor_seat_id=resolve_teacher_seat_for_class(assessment.class_id).id,
                    product_id=grant.product_id,
                    entitlement_type="INSURANCE",
                    acquisition_type=grant.acquisition_type,
                    correlation_id=idempotency_key,
                    payload={
                        "source": "run_insurance_expiry_job",
                        "policy_uuid": assessment.policy_uuid,
                    },
                )
            expired += 1
        except Exception:
            failed += 1
            db.session.rollback()
            logger.exception(
                "Insurance expiry failed for lineage %s", cycle.internal_ref
            )
            continue

    logger.info(
        "Insurance boundary-expiry job completed. Expired %s, skipped %s, failed %s",
        expired, skipped, failed,
    )


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

    def run_audit_invariant_check():
        with app.app_context():
            run_audit_invariant_check_job()

    # Wrapper that runs the rent reconciliation job with Flask app context
    def run_rent_reconciliation():
        with app.app_context():
            run_rent_reconciliation_job()

    # Wrapper that runs the automatic-payroll job with Flask app context
    def run_automatic_payroll():
        with app.app_context():
            run_automatic_payroll_job()

    # Wrapper that runs the insurance boundary-expiry job with Flask app context
    def run_insurance_expiry():
        with app.app_context():
            run_insurance_expiry_job()

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

        # Rent lifecycle reconciliation — runs hourly so cycle boundaries and
        # rent-boundary PERK expiry are materialized promptly across timezones,
        # even when no student visits the rent page. Idempotent per class.
        scheduler.add_job(
            func=run_rent_reconciliation,
            trigger='interval',
            hours=1,
            id='rent_reconciliation',
            name='Rent lifecycle reconciliation',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        # Automatic payroll — hourly. Fires the canonical completion FEAT only for
        # classes whose next_payroll_date is due; idempotent per scheduled
        # occurrence, so an hourly cadence never double-runs a cycle.
        scheduler.add_job(
            func=run_automatic_payroll,
            trigger='interval',
            hours=1,
            id='automatic_payroll',
            name='Automatic payroll (due classes)',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        # Insurance boundary expiry — daily at 4 AM UTC. Reads the bill-cycle table
        # for terminal insurance lineages whose coverage boundary has passed and
        # writes EXPIRED via FEAT-STOR-002. Idempotent per entitlement/boundary, so
        # a daily cadence never double-expires.
        scheduler.add_job(
            func=run_insurance_expiry,
            trigger='cron',
            hour=4,
            minute=0,
            id='insurance_expiry',
            name='Insurance boundary expiry',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        scheduler.start()
        logger.info(
            "Scheduled tasks initialized: daily-limit enforcement (hourly), "
            "database maintenance (2 AM UTC), "
            "audit invariant check (3 AM UTC), "
            "rent reconciliation (hourly), "
            "automatic payroll (hourly)"
        )
    else:
        logger.info("Scheduler already running")
