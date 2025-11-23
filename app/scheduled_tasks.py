"""
Scheduled background tasks for Classroom Token Hub.

Contains periodic tasks that run in the background to maintain system state.
"""

import logging
from datetime import datetime, timezone


def enforce_daily_limits_job():
    """
    Scheduled job that checks all active students and auto-taps them out if they've exceeded their daily limit.
    Runs hourly to ensure limits are enforced even if students close their browser.
    """
    # Import here to avoid circular imports
    from app.models import Student, TapEvent
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    from app.extensions import db

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting scheduled auto tap-out enforcement job")

    try:
        with db.session.begin_nested():
            students = Student.query.all()
            checked_count = 0
            tapped_out_count = 0

            for student in students:
                try:
                    # Get the student's current active sessions
                    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
                    has_active_session = False

                    for period in student_blocks:
                        latest_event = (
                            TapEvent.query
                            .filter_by(student_id=student.id, period=period)
                            .order_by(TapEvent.timestamp.desc())
                            .first()
                        )

                        # If student is active, check their limit
                        if latest_event and latest_event.status == "active":
                            has_active_session = True
                            break

                    if has_active_session:
                        checked_count += 1
                        # Get the latest event ID before running check
                        latest_before = TapEvent.query.filter_by(
                            student_id=student.id
                        ).order_by(TapEvent.timestamp.desc()).first()

                        check_and_auto_tapout_if_limit_reached(student)

                        # Check if a new tap-out event was created
                        latest_after = TapEvent.query.filter_by(
                            student_id=student.id
                        ).order_by(TapEvent.timestamp.desc()).first()

                        if latest_after and latest_after.id != latest_before.id:
                            if latest_after.status == "inactive":
                                tapped_out_count += 1
                                logger.info(f"Auto-tapped out student {student.id} ({student.full_name})")

                except Exception as e:
                    logger.error(f"Error checking student {student.id}: {e}", exc_info=True)
                    continue

            db.session.commit()
            logger.info(f"Auto tap-out job completed. Checked {checked_count} active students, tapped out {tapped_out_count}")

    except Exception as e:
        logger.error(f"Auto tap-out job failed: {e}", exc_info=True)
        db.session.rollback()


def cleanup_expired_demo_sessions_job():
    """
    Scheduled job that cleans up expired demo student sessions.
    Runs every 5 minutes to remove demo sessions that have exceeded the 10-minute timeout.
    """
    # Import here to avoid circular imports
    from app.models import DemoStudent
    from app.extensions import db
    from app.utils.demo_sessions import cleanup_demo_student_data

    logger = logging.getLogger('scheduled_tasks')
    logger.info("Starting demo session cleanup job")

    try:
        now = datetime.now(timezone.utc)

        # Find all active demo sessions that have expired
        expired_sessions = DemoStudent.query.filter(
            DemoStudent.is_active == True,
            DemoStudent.expires_at < now
        ).all()

        cleaned_count = 0
        for demo_session in expired_sessions:
            try:
                session_id = demo_session.session_id

                cleanup_demo_student_data(demo_session)

                db.session.commit()
                cleaned_count += 1
                logger.info(
                    "Cleaned up expired demo session %s (student_id=%s)",
                    session_id,
                    demo_session.student_id,
                )

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error cleaning up demo session {demo_session.session_id}: {e}", exc_info=True)
                continue

        if cleaned_count > 0:
            logger.info(f"Demo session cleanup completed. Cleaned up {cleaned_count} expired sessions")

    except Exception as e:
        logger.error(f"Demo session cleanup job failed: {e}", exc_info=True)


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

    # Wrapper function that runs the cleanup_expired_demo_sessions_job with Flask app context
    def run_cleanup_demo_sessions():
        with app.app_context():
            cleanup_expired_demo_sessions_job()

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

        # Add the demo session cleanup job to run every 5 minutes
        scheduler.add_job(
            func=run_cleanup_demo_sessions,
            trigger='interval',
            minutes=5,
            id='cleanup_demo_sessions',
            name='Clean up expired demo sessions',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        scheduler.start()
        logger.info("Scheduled tasks initialized. Auto tap-out will run every hour, demo cleanup every 5 minutes.")
    else:
        logger.info("Scheduler already running")
