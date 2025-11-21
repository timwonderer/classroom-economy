"""
System Admin routes for Classroom Token Hub.

High-level system administration including teacher management, invite codes,
system logs, error monitoring, and debug/testing tools.
"""

import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from sqlalchemy import delete
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden, NotFound, ServiceUnavailable
import pyotp

from app.extensions import db
from app.models import (
    SystemAdmin, Admin, Student, AdminInviteCode, ErrorLog,
    Transaction, TapEvent, HallPassLog, StudentItem, RentPayment,
    StudentInsurance, InsuranceClaim, UserReport
)
from app.auth import system_admin_required
from forms import SystemAdminLoginForm, SystemAdminInviteForm

# Import utility functions
from app.utils.helpers import is_safe_url
from app.utils.turnstile import verify_turnstile_token

# Create blueprint
sysadmin_bp = Blueprint('sysadmin', __name__, url_prefix='/sysadmin')


# -------------------- AUTHENTICATION --------------------

@sysadmin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """System admin login with TOTP authentication."""
    session.pop("is_system_admin", None)
    session.pop("last_activity", None)
    form = SystemAdminLoginForm()
    if form.validate_on_submit():
        # Verify Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response')
        if not verify_turnstile_token(turnstile_token, request.remote_addr):
            current_app.logger.warning(f"Turnstile verification failed for system admin login attempt")
            flash("CAPTCHA verification failed. Please try again.", "error")
            return redirect(url_for('sysadmin.login'))

        username = form.username.data.strip()
        totp_code = form.totp_code.data.strip()
        admin = SystemAdmin.query.filter_by(username=username).first()
        if admin:
            totp = pyotp.TOTP(admin.totp_secret)
            if totp.verify(totp_code, valid_window=1):
                session["is_system_admin"] = True
                session['last_activity'] = datetime.now(timezone.utc).isoformat()
                flash("System admin login successful.")
                next_url = request.args.get("next")
                if not is_safe_url(next_url):
                    return redirect(url_for("sysadmin.dashboard"))
                return redirect(next_url or url_for("sysadmin.dashboard"))
        flash("Invalid credentials or TOTP.", "error")
        return redirect(url_for("sysadmin.login"))
    return render_template("system_admin_login.html", form=form)


@sysadmin_bp.route('/logout')
def logout():
    """System admin logout."""
    session.pop("is_system_admin", None)
    flash("Logged out.")
    return redirect(url_for("sysadmin.login"))


# -------------------- DASHBOARD --------------------

@sysadmin_bp.route('/dashboard', methods=['GET', 'POST'])
@system_admin_required
def dashboard():
    """
    System admin dashboard with unified statistics and quick actions.
    Shows teacher count, student count, active invites, recent teachers, and recent errors.
    """
    # Gather statistics
    total_teachers = Admin.query.count()
    total_students = Student.query.count()
    active_invites = AdminInviteCode.query.filter_by(used=False).count()
    system_admin_count = SystemAdmin.query.count()

    # Recent teachers (last 5)
    recent_teachers = Admin.query.order_by(Admin.created_at.desc()).limit(5).all()

    # Recent errors (last 5)
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(5).all()

    # System admins
    system_admins = SystemAdmin.query.order_by(SystemAdmin.username.asc()).all()

    return render_template(
        "system_admin_dashboard.html",
        total_teachers=total_teachers,
        total_students=total_students,
        active_invites=active_invites,
        system_admin_count=system_admin_count,
        recent_teachers=recent_teachers,
        recent_errors=recent_errors,
        system_admins=system_admins
    )


# -------------------- LOGGING AND MONITORING --------------------

@sysadmin_bp.route('/logs')
@system_admin_required
def logs():
    """
    View system logs from the log file.
    Parses and structures the last 200 lines of logs for display.
    """
    log_file = os.getenv("LOG_FILE", "app.log")
    structured_logs = []
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()[-200:]
        log_pattern = re.compile(r'\[(.*?)\]\s+(\w+)\s+in\s+(\w+):\s+(.*)')
        current_log = None
        for line in lines:
            match = log_pattern.match(line)
            if match:
                # Start a new log entry
                timestamp, level, module, message = match.groups()
                current_log = {
                    "timestamp": timestamp,
                    "level": level,
                    "module": module,
                    "message": message.strip()
                }
                structured_logs.append(current_log)
            else:
                # Continuation of the previous log entry (stack trace, etc.)
                if current_log:
                    current_log["message"] += "<br>" + line.strip()
                else:
                    # Orphan line with no preceding log; treat as its own entry
                    current_log = {
                        "timestamp": "",
                        "level": "",
                        "module": "",
                        "message": line.strip()
                    }
                    structured_logs.append(current_log)
    except Exception as e:
        structured_logs = [{"timestamp": "", "level": "ERROR", "module": "logs", "message": f"Error reading log file: {e}"}]
    return render_template("system_admin_logs.html", logs=structured_logs, current_page="sysadmin_logs")


@sysadmin_bp.route('/error-logs')
@system_admin_required
def error_logs():
    """
    View error logs from the database.
    Shows all errors captured by the error logging system with pagination and filtering.
    """
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get error type filter if provided
    error_type_filter = request.args.get('error_type', '')

    query = ErrorLog.query

    if error_type_filter:
        query = query.filter(ErrorLog.error_type == error_type_filter)

    # Paginate and order by most recent first
    pagination = query.order_by(ErrorLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    error_logs_data = pagination.items

    # Get distinct error types for filter dropdown
    error_types = db.session.query(ErrorLog.error_type).distinct().all()
    error_types = [et[0] for et in error_types if et[0]]

    return render_template(
        "system_admin_error_logs.html",
        error_logs=error_logs_data,
        pagination=pagination,
        error_types=error_types,
        current_error_type=error_type_filter,
        current_page="sysadmin_error_logs"
    )


@sysadmin_bp.route('/logs-testing')
@system_admin_required
def logs_testing():
    """
    Combined page for viewing error logs and testing error pages.
    Shows recent errors and provides links to test error handlers.
    """
    # Get recent error logs
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(50).all()

    # Get system logs URL
    logs_url = url_for("sysadmin.logs")

    return render_template(
        "system_admin_logs_testing.html",
        recent_errors=recent_errors,
        logs_url=logs_url,
        current_page="sysadmin_logs_testing"
    )


# -------------------- ERROR TESTING ROUTES --------------------

@sysadmin_bp.route('/test-errors/400')
@system_admin_required
def test_error_400():
    """Trigger a 400 Bad Request error for testing."""
    raise BadRequest("This is a test 400 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/401')
@system_admin_required
def test_error_401():
    """Trigger a 401 Unauthorized error for testing."""
    raise Unauthorized("This is a test 401 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/403')
@system_admin_required
def test_error_403():
    """Trigger a 403 Forbidden error for testing."""
    raise Forbidden("This is a test 403 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/404')
@system_admin_required
def test_error_404():
    """Trigger a 404 Not Found error for testing."""
    raise NotFound("This is a test 404 error triggered by system admin for testing purposes.")


@sysadmin_bp.route('/test-errors/500')
@system_admin_required
def test_error_500():
    """Trigger a 500 Internal Server Error for testing."""
    # Intentionally cause a division by zero error
    x = 1 / 0
    return "This should never be reached"


@sysadmin_bp.route('/test-errors/503')
@system_admin_required
def test_error_503():
    """Trigger a 503 Service Unavailable error for testing."""
    raise ServiceUnavailable("This is a test 503 error triggered by system admin for testing purposes.")


# -------------------- ADMIN (TEACHER) MANAGEMENT --------------------

@sysadmin_bp.route('/admins')
@system_admin_required
def manage_admins():
    """
    View and manage all admin (teacher) accounts.
    Shows admin details, student counts, signup date, and last login.
    """
    # Get all admins with student counts
    admins = Admin.query.all()
    admin_data = []

    for admin in admins:
        # Count students (will be accurate once multi-tenancy is implemented)
        student_count = Student.query.count()  # Currently counts all students
        # TODO: After multi-tenancy, use: Student.query.filter_by(teacher_id=admin.id).count()

        admin_data.append({
            'id': admin.id,
            'username': admin.username,
            'student_count': student_count,
            'created_at': admin.created_at,
            'last_login': admin.last_login
        })

    return render_template(
        'system_admin_manage_admins.html',
        admins=admin_data,
        current_page='sysadmin_admins'
    )


@sysadmin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@system_admin_required
def delete_admin(admin_id):
    """
    Delete an admin account and all students created under that teacher.
    This is a permanent action that cascades to all student data.
    """
    admin = Admin.query.get_or_404(admin_id)

    try:
        # Count students for feedback message
        # TODO: After multi-tenancy, filter by teacher_id
        student_count = Student.query.count()

        # Delete all students and their associated data
        # TODO: After multi-tenancy, filter by: Student.query.filter_by(teacher_id=admin_id).all()
        for student in Student.query.all():
            # Delete all related data for each student
            Transaction.query.filter_by(student_id=student.id).delete()
            TapEvent.query.filter_by(student_id=student.id).delete()
            HallPassLog.query.filter_by(student_id=student.id).delete()
            StudentItem.query.filter_by(student_id=student.id).delete()
            RentPayment.query.filter_by(student_id=student.id).delete()
            db.session.execute(delete(StudentInsurance).where(StudentInsurance.student_id == student.id))
            InsuranceClaim.query.filter_by(student_id=student.id).delete()

        # Delete all students
        Student.query.delete()

        # Delete the admin
        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        flash(f"Admin '{admin_username}' and {student_count} students deleted successfully.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting admin {admin_id}")
        flash(f"Error deleting admin: {str(e)}", "error")

    return redirect(url_for('sysadmin.manage_admins'))


@sysadmin_bp.route('/manage-teachers', methods=['GET', 'POST'])
@system_admin_required
def manage_teachers():
    """
    Combined page for teacher management and invite codes.
    Allows creation of invite codes and viewing all teachers.
    """
    # Handle invite code form submission
    form = SystemAdminInviteForm()
    if form.validate_on_submit():
        code = form.code.data or secrets.token_urlsafe(8)
        expiry_days = request.form.get('expiry_days', 30, type=int)
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        invite = AdminInviteCode(code=code, expires_at=expires_at)
        db.session.add(invite)
        db.session.commit()
        flash(f"✅ Invite code '{code}' created successfully.", "success")
        return redirect(url_for("sysadmin.manage_teachers") + "#invite-codes")

    # Get all invite codes
    invites = AdminInviteCode.query.order_by(AdminInviteCode.created_at.desc()).all()

    # Get all teachers
    teachers = Admin.query.order_by(Admin.created_at.desc()).all()

    return render_template(
        "system_admin_manage_teachers.html",
        form=form,
        invites=invites,
        teachers=teachers
    )


@sysadmin_bp.route('/manage-teachers/delete/<int:admin_id>', methods=['POST'])
@system_admin_required
def delete_teacher(admin_id):
    """
    Delete a teacher and all their associated data.
    This is a permanent action that cascades to all student data.
    """
    admin = Admin.query.get_or_404(admin_id)

    try:
        # Count students for feedback message
        student_count = Student.query.count()  # TODO: After multi-tenancy, filter by teacher_id

        # Delete all students and their associated data
        for student in Student.query.all():  # TODO: Filter by teacher_id
            Transaction.query.filter_by(student_id=student.id).delete()
            TapEvent.query.filter_by(student_id=student.id).delete()
            HallPassLog.query.filter_by(student_id=student.id).delete()
            StudentItem.query.filter_by(student_id=student.id).delete()
            RentPayment.query.filter_by(student_id=student.id).delete()
            db.session.execute(delete(StudentInsurance).where(StudentInsurance.student_id == student.id))
            InsuranceClaim.query.filter_by(student_id=student.id).delete()

        Student.query.delete()  # TODO: Filter by teacher_id

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        flash(f"✅ Teacher '{admin_username}' and {student_count} students deleted successfully.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting teacher {admin_id}")
        flash(f"❌ Error deleting teacher: {str(e)}", "error")

    return redirect(url_for('sysadmin.manage_teachers'))


# -------------------- USER REPORTS MANAGEMENT --------------------

@sysadmin_bp.route('/user-reports')
@system_admin_required
def user_reports():
    """View all user-submitted bug reports, suggestions, and feedback."""
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    report_type_filter = request.args.get('type', 'all')

    # Base query
    query = UserReport.query

    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if report_type_filter != 'all':
        query = query.filter_by(report_type=report_type_filter)

    # Order by submission date (newest first)
    reports = query.order_by(UserReport.submitted_at.desc()).all()

    # Get counts for badges
    new_count = UserReport.query.filter_by(status='new').count()
    reviewed_count = UserReport.query.filter_by(status='reviewed').count()
    rewarded_count = UserReport.query.filter_by(status='rewarded').count()

    return render_template('sysadmin_user_reports.html',
                         reports=reports,
                         status_filter=status_filter,
                         report_type_filter=report_type_filter,
                         new_count=new_count,
                         reviewed_count=reviewed_count,
                         rewarded_count=rewarded_count)


@sysadmin_bp.route('/user-reports/<int:report_id>')
@system_admin_required
def view_user_report(report_id):
    """View detailed information about a specific user report."""
    report = UserReport.query.get_or_404(report_id)
    return render_template('sysadmin_user_report_detail.html', report=report)


@sysadmin_bp.route('/user-reports/<int:report_id>/update', methods=['POST'])
@system_admin_required
def update_user_report(report_id):
    """Update status and add notes to a user report."""
    report = UserReport.query.get_or_404(report_id)

    try:
        # Get form data
        status = request.form.get('status')
        admin_notes = request.form.get('admin_notes', '').strip()

        # Update report
        if status and status in ['new', 'reviewed', 'rewarded', 'closed', 'spam']:
            report.status = status

        if admin_notes:
            report.admin_notes = admin_notes

        report.reviewed_at = datetime.utcnow()
        # Note: reviewed_by_sysadmin_id is nullable, set to None for now
        # Could be extended to track specific sysadmin if needed

        db.session.commit()
        flash("Report updated successfully!", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating report {report_id}: {str(e)}")
        flash("Error updating report. Please try again.", "error")

    return redirect(url_for('sysadmin.view_user_report', report_id=report_id))


@sysadmin_bp.route('/user-reports/<int:report_id>/send-reward', methods=['POST'])
@system_admin_required
def send_reward_to_reporter(report_id):
    """Send anonymous reward to bug reporter (students only)."""
    report = UserReport.query.get_or_404(report_id)

    try:
        # Validate this is a student report
        if not report._student_id:
            flash("Cannot send reward: This report is not from a student.", "error")
            return redirect(url_for('sysadmin.view_user_report', report_id=report_id))

        # Get reward amount from form
        reward_amount = float(request.form.get('reward_amount', 0))

        if reward_amount <= 0:
            flash("Reward amount must be greater than zero.", "error")
            return redirect(url_for('sysadmin.view_user_report', report_id=report_id))

        # Get the student
        student = Student.query.get(report._student_id)

        if not student:
            flash("Error: Student not found.", "error")
            return redirect(url_for('sysadmin.view_user_report', report_id=report_id))

        # Create transaction for reward
        transaction = Transaction(
            student_id=student.id,
            amount=reward_amount,
            account_type='checking',
            type='bug_bounty',
            description=f'Bug bounty reward for report #{report.id}'
        )
        db.session.add(transaction)

        # Update report status
        report.reward_amount = reward_amount
        report.reward_sent_at = datetime.utcnow()
        report.status = 'rewarded'

        db.session.commit()

        flash(f"Reward of ${reward_amount:.2f} sent anonymously to reporter!", "success")
        current_app.logger.info(f"Bug bounty reward of ${reward_amount} sent to student {student.id} for report #{report.id}")

    except ValueError:
        flash("Invalid reward amount.", "error")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending reward for report {report_id}: {str(e)}")
        flash(f"Error sending reward: {str(e)}", "error")

    return redirect(url_for('sysadmin.view_user_report', report_id=report_id))
