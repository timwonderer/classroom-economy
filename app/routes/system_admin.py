"""
System Admin routes for Classroom Token Hub.

High-level system administration including teacher management, invite codes,
system logs, error monitoring, and debug/testing tools.
"""

import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from sqlalchemy import delete, or_
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden, NotFound, ServiceUnavailable
import pyotp

from app.extensions import db
from app.models import (
    SystemAdmin, Admin, Student, AdminInviteCode, ErrorLog,
    Transaction, TapEvent, HallPassLog, StudentItem, RentPayment,
    StudentInsurance, InsuranceClaim, StudentTeacher
)
from app.auth import system_admin_required
from forms import SystemAdminLoginForm, SystemAdminInviteForm

# Import utility functions
from app.utils.helpers import is_safe_url

# Create blueprint
sysadmin_bp = Blueprint('sysadmin', __name__, url_prefix='/sysadmin')


def _get_teacher_student_count(teacher_id: int) -> int:
    """
    Get the count of students associated with a specific teacher.
    
    Counts students that are either:
    1. Linked via student_teachers table (many-to-many relationship), OR
    2. Have teacher_id set (legacy primary ownership during migration)
    
    Uses UNION to avoid double-counting students that appear in both.
    Optimized to count in database without loading student IDs.
    """
    # Get student IDs from student_teachers links
    linked_ids = db.session.query(StudentTeacher.student_id).filter(
        StudentTeacher.admin_id == teacher_id
    ).distinct()
    
    # Get student IDs from legacy teacher_id column
    legacy_ids = db.session.query(Student.id).filter(
        Student.teacher_id == teacher_id
    ).distinct()
    
    # Union the two queries and count - database does the work
    count = linked_ids.union(legacy_ids).count()
    
    return count


def _tail_log_lines(file_path: str, max_lines: int = 200, chunk_size: int = 8192):
    """Return the last ``max_lines`` from a log file without loading the entire file."""

    if not os.path.exists(file_path):
        return []

    lines = []
    buffer = b""
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()

        while len(lines) <= max_lines and position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            f.seek(position)
            buffer = f.read(read_size) + buffer
            lines = buffer.splitlines()

    return [line.decode(errors="ignore") for line in lines[-max_lines:]]


# -------------------- AUTHENTICATION --------------------

@sysadmin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """System admin login with TOTP authentication."""
    session.pop("is_system_admin", None)
    session.pop("last_activity", None)
    form = SystemAdminLoginForm()
    if form.validate_on_submit():
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
        lines = _tail_log_lines(log_file, max_lines=200)
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
    Shows admin details, student counts per teacher, signup date, and last login.
    
    Note: System admins see teacher info and student counts only, not individual student details.
    """
    # Get all admins with student counts
    admins = Admin.query.all()
    admin_data = []

    for admin in admins:
        # Count students associated with this specific teacher
        # Uses both student_teachers links and legacy teacher_id for accuracy
        student_count = _get_teacher_student_count(admin.id)

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
        primary_student_ids = [s.id for s in Student.query.filter_by(teacher_id=admin.id)]
        linked_student_ids = [
            st.student_id for st in StudentTeacher.query.filter_by(admin_id=admin.id)
        ]

        candidate_student_ids = set(primary_student_ids + linked_student_ids)

        shared_student_ids = set()
        if candidate_student_ids:
            shared_student_ids = set(
                sid for (sid,) in db.session.query(StudentTeacher.student_id)
                .filter(
                    StudentTeacher.student_id.in_(candidate_student_ids),
                    StudentTeacher.admin_id != admin.id,
                )
            )
            shared_student_ids.update([
                sid for (sid,) in db.session.query(Student.id)
                .filter(
                    Student.id.in_(candidate_student_ids),
                    Student.teacher_id.isnot(None),
                    Student.teacher_id != admin.id,
                )
            ])

        exclusive_student_ids = candidate_student_ids - shared_student_ids

        if shared_student_ids:
            StudentTeacher.query.filter(
                StudentTeacher.admin_id == admin.id,
                StudentTeacher.student_id.in_(shared_student_ids),
            ).delete(synchronize_session=False)
            Student.query.filter(
                Student.id.in_(shared_student_ids),
                Student.teacher_id == admin.id,
            ).update({Student.teacher_id: None}, synchronize_session=False)

        if exclusive_student_ids:
            Transaction.query.filter(Transaction.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            TapEvent.query.filter(TapEvent.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            HallPassLog.query.filter(HallPassLog.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            StudentItem.query.filter(StudentItem.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            RentPayment.query.filter(RentPayment.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            db.session.execute(delete(StudentInsurance).where(StudentInsurance.student_id.in_(exclusive_student_ids)))
            InsuranceClaim.query.filter(InsuranceClaim.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            StudentTeacher.query.filter(StudentTeacher.student_id.in_(exclusive_student_ids)).delete(synchronize_session=False)
            Student.query.filter(Student.id.in_(exclusive_student_ids)).delete(synchronize_session=False)

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        shared_notice = ""
        if shared_student_ids:
            shared_notice = f" Detached {len(shared_student_ids)} shared students without deleting their records."

        flash(
            f"Admin '{admin_username}' deleted. Removed {len(exclusive_student_ids)} exclusively-owned students.{shared_notice}",
            "success",
        )

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


@sysadmin_bp.route('/student-ownership', methods=['GET', 'POST'])
@system_admin_required
def student_ownership():
    """Manage which teachers have access to each student account."""
    action = request.form.get("action") if request.method == "POST" else None

    if action:
        student_id = request.form.get("student_id", type=int)
        admin_id = request.form.get("admin_id", type=int)
        student = Student.query.get_or_404(student_id)
        admin = Admin.query.get_or_404(admin_id)

        if action == "add":
            existing_link = StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).first()
            if existing_link:
                flash(f"{admin.username} already has access to {student.full_name}.", "info")
            else:
                db.session.add(StudentTeacher(student_id=student.id, admin_id=admin.id))
                if request.form.get("make_primary") == "on":
                    student.teacher_id = admin.id
                db.session.commit()
                flash(f"Added {admin.username} to {student.full_name}'s teacher list.", "success")
            return redirect(url_for('sysadmin.student_ownership'))

        if action == "remove":
            link = StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).first()
            if not link:
                flash("No matching teacher link found for removal.", "error")
                return redirect(url_for('sysadmin.student_ownership'))

            db.session.delete(link)
            # If removing the primary teacher, fall back to another linked teacher if available
            if student.teacher_id == admin.id:
                fallback = (
                    StudentTeacher.query
                    .filter(StudentTeacher.student_id == student.id, StudentTeacher.admin_id != admin.id)
                    .order_by(StudentTeacher.created_at.asc())
                    .first()
                )
                student.teacher_id = fallback.admin_id if fallback else None

            db.session.commit()
            flash(f"Removed {admin.username} from {student.full_name}.", "success")
            return redirect(url_for('sysadmin.student_ownership'))

        flash("Unsupported action.", "error")
        return redirect(url_for('sysadmin.student_ownership'))

    # GET request: render the mapping table
    students = Student.query.order_by(Student.first_name.asc(), Student.last_initial.asc()).all()
    teachers = Admin.query.order_by(Admin.username.asc()).all()
    teacher_lookup = {t.id: t for t in teachers}

    student_links = {}
    for link in StudentTeacher.query.all():
        student_links.setdefault(link.student_id, []).append(link.admin_id)

    return render_template(
        "system_admin_student_ownership.html",
        students=students,
        teachers=teachers,
        student_links=student_links,
        teacher_lookup=teacher_lookup,
        current_page="student_ownership",
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
        linked_student_ids = (
            db.session.query(StudentTeacher.student_id)
            .filter(StudentTeacher.admin_id == admin.id)
            .subquery()
        )

        affected_students = Student.query.filter(
            or_(Student.teacher_id == admin.id, Student.id.in_(linked_student_ids))
        ).all()
        student_count = len(affected_students)

        for student in affected_students:
            StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).delete()

            if student.teacher_id == admin.id:
                fallback = (
                    StudentTeacher.query
                    .filter(StudentTeacher.student_id == student.id)
                    .order_by(StudentTeacher.created_at.asc())
                    .first()
                )
                student.teacher_id = fallback.admin_id if fallback else None

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        flash(
            f"✅ Teacher '{admin_username}' deleted. Updated {student_count} student ownership records.",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Error deleting teacher {admin_id}")
        flash(f"❌ Error deleting teacher: {str(e)}", "error")

    return redirect(url_for('sysadmin.manage_teachers'))
