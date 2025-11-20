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


def init_scheduled_tasks(app):
    """
    Initialize and start scheduled tasks.

    Args:
        app: Flask application instance
    """
    from app.extensions import scheduler

    logger = logging.getLogger('scheduled_tasks')

    # Wrapper function that runs the job with Flask app context
    def run_with_context():
        with app.app_context():
            enforce_daily_limits_job()

    if not scheduler.running:
        # Add the auto tap-out enforcement job to run every hour
        scheduler.add_job(
            func=run_with_context,
            trigger='interval',
            hours=1,
            id='enforce_daily_limits',
            name='Enforce daily attendance limits',
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )

        scheduler.start()
        logger.info("Scheduled tasks initialized. Auto tap-out will run every hour.")
    else:
        logger.info("Scheduler already running")
