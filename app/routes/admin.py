"""
Admin routes for Classroom Token Hub.

Contains all admin/teacher-facing functionality including dashboard, student management,
store management, insurance, payroll, attendance tracking, and data import/export.
"""

import csv
import io
import os
import re
import base64
import math
import random
import string
import secrets
import qrcode
import hashlib
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, session,
    jsonify, Response, send_file, current_app, abort
)
from sqlalchemy import desc, text, or_, func
from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy as sa
import pyotp
import pytz

from app.extensions import db
from app.models import (
    Student, Admin, AdminInviteCode, StudentTeacher, Transaction, TapEvent, StoreItem, StudentItem,
    RentSettings, RentPayment, RentWaiver, InsurancePolicy, StudentInsurance, InsuranceClaim,
    HallPassLog, PayrollSettings, PayrollReward, PayrollFine, BankingSettings, TeacherBlock,
    DeletionRequest, DeletionRequestType, DeletionRequestStatus
)
from app.auth import admin_required, get_admin_student_query, get_student_for_admin
from forms import (
    AdminLoginForm, AdminSignupForm, AdminTOTPConfirmForm, StoreItemForm,
    InsurancePolicyForm, AdminClaimProcessForm, PayrollSettingsForm,
    PayrollRewardForm, PayrollFineForm, ManualPaymentForm, BankingSettingsForm
)

# Import utility functions
from app.utils.helpers import is_safe_url, format_utc_iso
from app.utils.constants import PERIOD_MAX_LENGTH, PERIOD_PATTERN
from hash_utils import get_random_salt, hash_hmac, hash_username, hash_username_lookup
from payroll import calculate_payroll
from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds

# Timezone
PACIFIC = pytz.timezone('America/Los_Angeles')

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# -------------------- DASHBOARD & QUICK ACTIONS --------------------


def _scoped_students(include_unassigned=True):
    """Return a query for students the current admin can access."""
    return get_admin_student_query(include_unassigned=include_unassigned)


def _student_scope_subquery(include_unassigned=True):
    """Return a subquery of student IDs the current admin can access."""
    return (
        _scoped_students(include_unassigned=include_unassigned)
        .with_entities(Student.id)
        .subquery()
    )


def _sanitize_csv_field(value):
    """Prevent CSV injection by prefixing risky leading characters."""

    if value is None:
        return ""

    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _get_student_or_404(student_id, include_unassigned=True):
    """Fetch a student the current admin can access or 404."""
    student = get_student_for_admin(student_id, include_unassigned=include_unassigned)
    if not student:
        abort(404)
    return student


def _link_student_to_admin(student: Student, admin_id):
    """Ensure the given admin is associated with the student."""
    if not admin_id:
        return
    existing_link = StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin_id).first()
    if not existing_link:
        db.session.add(StudentTeacher(student_id=student.id, admin_id=admin_id))

def auto_tapout_all_over_limit():
    """
    Checks all active students and auto-taps them out if they've exceeded their daily limit.
    This is called when admin views the dashboard to ensure limits are enforced.
    """
    from app.routes.api import check_and_auto_tapout_if_limit_reached

    # Get all students
    students = _scoped_students().all()
    tapped_out_count = 0

    for student in students:
        try:
            # Get the student's current active sessions
            student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            for period in student_blocks:
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                # If student is active, run the auto-tapout check
                if latest_event and latest_event.status == "active":
                    check_and_auto_tapout_if_limit_reached(student)
                    tapped_out_count += 1
                    break  # Only need to run once per student
        except Exception as e:
            current_app.logger.error(f"Error checking auto-tapout for student {student.id}: {e}")
            continue

    return tapped_out_count

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics, pending actions, and recent activity."""
    student_ids_subq = _student_scope_subquery()
    # Auto-tapout students who have exceeded their daily limit
    auto_tapout_all_over_limit()

    # Get all students for calculations
    students = _scoped_students().order_by(Student.first_name).all()
    student_lookup = {s.id: s for s in students}

    # Quick Stats
    total_students = len(students)
    total_balance = sum(s.checking_balance + s.savings_balance for s in students)
    avg_balance = total_balance / total_students if total_students > 0 else 0

    # Pending actions - count all types of pending approvals
    pending_redemptions_count = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentItem.status == 'processing')
        .count()
    )
    pending_hall_passes_count = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .count()
    )
    pending_insurance_claims_count = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(InsuranceClaim.status == 'pending')
        .count()
    )
    total_pending_actions = pending_redemptions_count + pending_hall_passes_count + pending_insurance_claims_count

    # Get recent items for each pending type (limited for display)
    recent_redemptions = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentItem.status == 'processing')
        .order_by(StudentItem.redemption_date.desc())
        .limit(5)
        .all()
    )
    recent_hall_passes = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.desc())
        .limit(5)
        .all()
    )
    recent_insurance_claims = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(InsuranceClaim.status == 'pending')
        .order_by(InsuranceClaim.filed_date.desc())
        .limit(5)
        .all()
    )

    # Recent transactions (limited to 5 for display)
    recent_transactions = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter_by(is_void=False)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
    total_transactions_today = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter(
            Transaction.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
            Transaction.is_void == False,
        )
        .count()
    )

    # Recent attendance logs (limited to 5 for display)
    raw_logs = (
        db.session.query(
            TapEvent,
            Student.first_name,
            Student.last_initial
        )
        .join(Student, TapEvent.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .order_by(TapEvent.timestamp.desc())
        .limit(5)
        .all()
    )
    recent_logs = []
    for log, first_name, last_initial in raw_logs:
        recent_logs.append({
            'student_id': log.student_id,
            'student_name': f"{first_name} {last_initial}.",
            'period': log.period,
            'timestamp': log.timestamp,
            'reason': log.reason,
            'status': log.status
        })

    # --- Payroll Info ---
    last_payroll_time = get_last_payroll_time()
    payroll_summary = calculate_payroll(students, last_payroll_time)
    total_payroll_estimate = sum(payroll_summary.values())

    # Calculate next payroll date (keep in UTC for template conversion)
    if last_payroll_time:
        next_payroll_date = last_payroll_time + timedelta(days=14)
    else:
        now_utc = datetime.now(timezone.utc)
        days_until_friday = (4 - now_utc.weekday() + 7) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_payroll_date = now_utc + timedelta(days=days_until_friday)

    return render_template(
        'admin_dashboard.html',
        # Quick stats
        total_students=total_students,
        total_balance=total_balance,
        avg_balance=avg_balance,
        total_pending_actions=total_pending_actions,
        pending_redemptions_count=pending_redemptions_count,
        pending_hall_passes_count=pending_hall_passes_count,
        pending_insurance_claims_count=pending_insurance_claims_count,
        total_transactions_today=total_transactions_today,
        # Payroll info
        total_payroll_estimate=total_payroll_estimate,
        next_payroll_date=next_payroll_date,
        # Limited data for cards
        recent_redemptions=recent_redemptions,
        recent_hall_passes=recent_hall_passes,
        recent_insurance_claims=recent_insurance_claims,
        recent_transactions=recent_transactions,
        recent_logs=recent_logs,
        # Lookup table
        student_lookup=student_lookup,
        current_page="dashboard"
    )


@admin_bp.route('/bonuses', methods=['POST'])
@admin_required
def give_bonus_all():
    """Give bonus or payroll adjustment to all students."""
    title = request.form.get('title')
    amount = float(request.form.get('amount'))
    tx_type = request.form.get('type')

    # Stream students in batches to reduce memory usage
    students = _scoped_students().yield_per(50)
    for student in students:
        tx = Transaction(student_id=student.id, amount=amount, type=tx_type, description=title, account_type='checking')
        db.session.add(tx)

    db.session.commit()
    flash("Bonus/Payroll posted successfully!")
    return redirect(url_for('admin.dashboard'))


# -------------------- AUTHENTICATION --------------------

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login with TOTP authentication."""
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("last_activity", None)
    form = AdminLoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        totp_code = form.totp_code.data.strip()
        admin = Admin.query.filter_by(username=username).first()
        if admin:
            totp = pyotp.TOTP(admin.totp_secret)
            if totp.verify(totp_code, valid_window=1):
                # Update last login timestamp
                admin.last_login = datetime.utcnow()
                db.session.commit()

                session["is_admin"] = True
                session["admin_id"] = admin.id
                session["last_activity"] = datetime.now(timezone.utc).isoformat()
                current_app.logger.info(f"✅ Admin login success for {username}")
                flash("Admin login successful.")
                next_url = request.args.get("next")
                if not is_safe_url(next_url):
                    return redirect(url_for("admin.dashboard"))
                return redirect(next_url or url_for("admin.dashboard"))
        current_app.logger.warning(f"🔑 Admin login failed for {username}")
        flash("Invalid credentials or TOTP code.", "error")
        return redirect(url_for("admin.login", next=request.args.get("next")))
    return render_template("admin_login.html", form=form)


@admin_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    TOTP-only admin registration. Requires valid invite code.
    Uses AdminSignupForm for CSRF and validation.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    form = AdminSignupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        invite_code = form.invite_code.data.strip()
        totp_code = request.form.get("totp_code", "").strip()
        # Step 1: Validate invite code
        code_row = db.session.execute(
            text("SELECT * FROM admin_invite_codes WHERE code = :code"),
            {"code": invite_code}
        ).fetchone()
        if not code_row:
            current_app.logger.warning(f"🛑 Admin signup failed: invalid invite code")
            msg = "Invalid invite code."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        if code_row.used:
            current_app.logger.warning(f"🛑 Admin signup failed: invite code already used")
            msg = "Invite code already used."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        if code_row.expires_at and code_row.expires_at < datetime.utcnow():
            current_app.logger.warning(f"🛑 Admin signup failed: invite code expired")
            msg = "Invite code expired."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        # Step 2: Check username uniqueness
        if Admin.query.filter_by(username=username).first():
            current_app.logger.warning(f"🛑 Admin signup failed: username already exists")
            msg = "Username already exists."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin.signup'))
        # Step 3: Generate TOTP secret and show QR code (if not already in session)
        if "admin_totp_secret" not in session or session.get("admin_totp_username") != username:
            totp_secret = pyotp.random_base32()
            session["admin_totp_secret"] = totp_secret
            session["admin_totp_username"] = username
        else:
            totp_secret = session["admin_totp_secret"]
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
        # Step 4: If no TOTP code submitted yet, show QR
        if not totp_code:
            # Generate QR code in-memory
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            current_app.logger.info(f"🔐 Admin signup: showing QR for {username}")
            form = AdminTOTPConfirmForm()
            return render_template(
                "admin_signup_totp.html",
                form=form,
                username=username,
                invite_code=invite_code,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 5: Validate entered TOTP code
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(totp_code):
            current_app.logger.warning(f"🛑 Admin signup failed: invalid TOTP code for {username}")
            msg = "Invalid TOTP code. Please try again."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            # Show QR again for retry
            totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy Admin")
            img = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            return render_template(
                "admin_signup_totp.html",
                form=form,
                username=username,
                invite_code=invite_code,
                qr_b64=img_b64,
                totp_secret=totp_secret
            )
        # Step 6: Create admin account and mark invite as used
        # Log the TOTP secret being saved for debug
        current_app.logger.info(f"🎯 Admin signup: TOTP secret being saved for {username}")
        new_admin = Admin(username=username, totp_secret=totp_secret)
        db.session.add(new_admin)
        db.session.execute(
            text("UPDATE admin_invite_codes SET used = TRUE WHERE code = :code"),
            {"code": invite_code}
        )
        db.session.commit()
        # Clear session
        session.pop("admin_totp_secret", None)
        session.pop("admin_totp_username", None)
        current_app.logger.info(f"🎉 Admin signup: {username} created successfully via invite")
        msg = "Admin account created successfully! Please log in using your authenticator app."
        if is_json:
            return jsonify(status="success", message=msg)
        flash(msg, "success")
        return redirect(url_for("admin.login"))
    # GET or invalid POST: render signup form with form instance (for CSRF)
    return render_template("admin_signup.html", form=form)


@admin_bp.route('/logout')
def logout():
    """Admin logout."""
    session.pop("is_admin", None)
    session.pop("admin_id", None)
    session.pop("last_activity", None)
    flash("Logged out.")
    return redirect(url_for("admin.login"))


# -------------------- STUDENT MANAGEMENT --------------------

@admin_bp.route('/students')
@admin_required
def students():
    """View all students with basic information organized by block."""
    all_students = _scoped_students().order_by(Student.block, Student.first_name).all()

    # Get unique blocks - split comma-separated blocks into individual blocks
    blocks = sorted({b.strip() for s in all_students for b in (s.block or "").split(',') if b.strip()})

    # Check if there are any students without block assignments
    unassigned_students = [s for s in all_students if not s.block or not s.block.strip()]
    if unassigned_students:
        # Add "Unassigned" as a special block at the beginning
        blocks = ["Unassigned"] + blocks

    # Group students by block (students can appear in multiple blocks)
    students_by_block = {}

    # Handle unassigned students first
    if unassigned_students:
        students_by_block["Unassigned"] = unassigned_students

    # Group students by their assigned blocks
    for block in blocks:
        if block != "Unassigned":  # Skip the special "Unassigned" block
            students_by_block[block] = [
                s for s in all_students
                if s.block and block.upper() in [b.strip().upper() for b in s.block.split(',')]
            ]

    # Add username_display attribute to each student
    for student in all_students:
        if student.username_hash and student.has_completed_setup:
            # Username is hashed, we need to display a placeholder
            student.username_display = f"user_{student.id}"
        else:
            student.username_display = "Not Set"

    return render_template('admin_students.html',
                         students=all_students,
                         blocks=blocks,
                         students_by_block=students_by_block,
                         current_page="students")


@admin_bp.route('/students/<int:student_id>')
@admin_required
def student_detail(student_id):
    """View detailed information for a specific student."""
    student = _get_student_or_404(student_id)
    # Remove deprecated last_tap_in/last_tap_out logic; rely on TapEvent backend.
    # Fetch last rent payment
    latest_rent = Transaction.query.filter_by(student_id=student.id, type="rent").order_by(Transaction.timestamp.desc()).first()
    student.rent_last_paid = latest_rent.timestamp if latest_rent else None

    # Fetch last property tax payment
    latest_tax = Transaction.query.filter_by(student_id=student.id, type="property_tax").order_by(Transaction.timestamp.desc()).first()
    student.property_tax_last_paid = latest_tax.timestamp if latest_tax else None

    # Compute due dates and overdue status
    from datetime import date
    today = datetime.now(PACIFIC).date()
    # Rent due on 5th, overdue after 6th
    rent_due = date(today.year, today.month, 5)
    student.rent_due_date = rent_due
    student.rent_overdue = today > rent_due and (not student.rent_last_paid or student.rent_last_paid.astimezone(PACIFIC).date() <= rent_due)

    # Property tax due on 5th, overdue after 6th
    tax_due = date(today.year, today.month, 5)
    student.property_tax_due_date = tax_due
    student.property_tax_overdue = today > tax_due and (not student.property_tax_last_paid or student.property_tax_last_paid.astimezone(PACIFIC).date() <= tax_due)

    transactions = Transaction.query.filter_by(student_id=student.id).order_by(Transaction.timestamp.desc()).all()
    student_items = student.items.order_by(StudentItem.purchase_date.desc()).all()
    # Fetch most recent TapEvent for this student
    latest_tap_event = TapEvent.query.filter_by(student_id=student.id).order_by(TapEvent.timestamp.desc()).first()

    # Get student's active insurance policy
    active_insurance = StudentInsurance.query.filter_by(
        student_id=student.id,
        status='active'
    ).first()

    # Get all blocks for the edit modal
    all_students = _scoped_students().all()
    blocks = sorted({b.strip() for s in all_students for b in (s.block or "").split(',') if b.strip()})

    return render_template('student_detail.html', student=student, transactions=transactions, student_items=student_items, latest_tap_event=latest_tap_event, active_insurance=active_insurance, blocks=blocks)


@admin_bp.route('/student/<int:student_id>/set-hall-passes', methods=['POST'])
@admin_required
def set_hall_passes(student_id):
    """Set hall pass balance for a student."""
    student = _get_student_or_404(student_id)
    new_balance = request.form.get('hall_passes', type=int)

    if new_balance is not None and new_balance >= 0:
        student.hall_passes = new_balance
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s hall pass balance to {new_balance}.", "success")
    else:
        flash("Invalid hall pass balance provided.", "error")

    return redirect(url_for('admin.student_detail', student_id=student_id))


@admin_bp.route('/student/edit', methods=['POST'])
@admin_required
def edit_student():
    """Edit student basic information."""
    student_id = request.form.get('student_id', type=int)
    student = _get_student_or_404(student_id)

    # Get form data
    new_first_name = request.form.get('first_name', '').strip()
    last_name_input = request.form.get('last_name', '').strip()
    new_last_initial = last_name_input[0].upper() if last_name_input else student.last_initial

    # Get selected blocks (multiple checkboxes)
    selected_blocks = request.form.getlist('blocks')

    # Join blocks with commas (e.g., "A,B,C")
    # At least one block is required for tap/hall pass functionality to work
    if selected_blocks:
        new_blocks = ','.join(sorted(b.strip().upper() for b in selected_blocks))
    else:
        # No blocks selected - this would break tap/hall pass functionality
        flash("At least one block must be selected.", "error")
        return redirect(url_for('admin.student_detail', student_id=student_id))

    # Check if name changed (need to recalculate hashes)
    name_changed = (new_first_name != student.first_name or new_last_initial != student.last_initial)

    # Update basic fields
    student.first_name = new_first_name
    student.last_initial = new_last_initial
    student.block = new_blocks

    # If name changed, recalculate name code and hashes
    if name_changed:
        # Generate new name code (MUST match original algorithm for consistency)
        # vowels from first_name + consonants from last_name
        # Note: We only have last_initial, so we reconstruct using last_name_input
        vowels = re.findall(r'[AEIOUaeiou]', new_first_name)
        consonants = re.findall(r'[^AEIOUaeiou\W\d_]', last_name_input)
        name_code = ''.join(vowels + consonants).lower()

        # Regenerate first_half_hash (name code hash)
        student.first_half_hash = hash_hmac(name_code.encode(), student.salt)

    # Update DOB sum if provided (and recalculate second_half_hash)
    dob_sum_str = request.form.get('dob_sum', '').strip()
    if dob_sum_str:
        new_dob_sum = int(dob_sum_str)
        if new_dob_sum != student.dob_sum:
            student.dob_sum = new_dob_sum
            # Regenerate second_half_hash (DOB sum hash)
            student.second_half_hash = hash_hmac(str(new_dob_sum).encode(), student.salt)

    # Handle login reset
    reset_login = request.form.get('reset_login') == 'on'
    if reset_login:
        # Clear login credentials but keep account data
        student.username_hash = None
        student.username_lookup_hash = None
        student.pin_hash = None
        student.passphrase_hash = None
        student.has_completed_setup = False
        flash(f"{student.full_name}'s login has been reset. They will need to re-claim their account.", "warning")

    try:
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s information.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/delete', methods=['GET', 'POST'])
@admin_required
def delete_student():
    """Delete a student and all associated data."""
    current_app.logger.info(f"Delete student route accessed. Method: {request.method}, Form data: {dict(request.form)}")

    # If GET request, show error and redirect (for debugging)
    if request.method == 'GET':
        flash("Delete student must be accessed via POST request.", "error")
        return redirect(url_for('admin.students'))

    student_id = request.form.get('student_id', type=int)
    confirmation = request.form.get('confirmation', '').strip()

    if not student_id:
        current_app.logger.error("No student_id provided in delete request")
        flash("Error: No student ID provided.", "error")
        return redirect(url_for('admin.students'))

    if confirmation != 'DELETE':
        current_app.logger.info(f"Delete cancelled: confirmation '{confirmation}' != 'DELETE'")
        flash("Deletion cancelled: confirmation text did not match.", "warning")
        return redirect(url_for('admin.students'))

    student = _get_student_or_404(student_id)
    student_name = student.full_name

    try:
        # Delete associated records (cascade should handle this, but being explicit)
        Transaction.query.filter_by(student_id=student.id).delete()
        TapEvent.query.filter_by(student_id=student.id).delete()
        StudentItem.query.filter_by(student_id=student.id).delete()
        RentPayment.query.filter_by(student_id=student.id).delete()
        StudentInsurance.query.filter_by(student_id=student.id).delete()
        HallPassLog.query.filter_by(student_id=student.id).delete()

        # Delete the student
        db.session.delete(student)
        db.session.commit()

        flash(f"Successfully deleted {student_name} and all associated data.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/students/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_students():
    """Delete multiple students at once."""
    data = request.get_json()
    student_ids = data.get('student_ids', [])

    if not student_ids:
        return jsonify({"status": "error", "message": "No students selected."}), 400

    try:
        deleted_count = 0
        for student_id in student_ids:
            student = _get_student_or_404(student_id)
            if student:
                # Delete associated records
                Transaction.query.filter_by(student_id=student.id).delete()
                TapEvent.query.filter_by(student_id=student.id).delete()
                StudentItem.query.filter_by(student_id=student.id).delete()
                RentPayment.query.filter_by(student_id=student.id).delete()
                RentWaiver.query.filter_by(student_id=student.id).delete()
                StudentInsurance.query.filter_by(student_id=student.id).delete()
                InsuranceClaim.query.filter_by(student_id=student.id).delete()
                HallPassLog.query.filter_by(student_id=student.id).delete()

                # Delete the student
                db.session.delete(student)
                deleted_count += 1

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted {deleted_count} student(s) and all associated data."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/students/delete-block', methods=['POST'])
@admin_required
def delete_block():
    """Delete all students in a specific block."""
    data = request.get_json()
    block = data.get('block', '').strip().upper()

    if not block:
        return jsonify({"status": "error", "message": "No block specified."}), 400

    try:
        students = _scoped_students().filter_by(block=block).all()
        deleted_count = len(students)

        for student in students:
            # Delete associated records
            Transaction.query.filter_by(student_id=student.id).delete()
            TapEvent.query.filter_by(student_id=student.id).delete()
            StudentItem.query.filter_by(student_id=student.id).delete()
            RentPayment.query.filter_by(student_id=student.id).delete()
            RentWaiver.query.filter_by(student_id=student.id).delete()
            StudentInsurance.query.filter_by(student_id=student.id).delete()
            InsuranceClaim.query.filter_by(student_id=student.id).delete()
            HallPassLog.query.filter_by(student_id=student.id).delete()

            # Delete the student
            db.session.delete(student)

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Successfully deleted all {deleted_count} student(s) in Block {block} and all associated data."
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@admin_bp.route('/student/add-individual', methods=['POST'])
@admin_required
def add_individual_student():
    """Add a single student (same as bulk upload but for one student)."""
    try:
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob', '').strip()
        block = request.form.get('block', '').strip().upper()

        if not all([first_name, last_name, dob_str, block]):
            flash("All fields are required.", "error")
            return redirect(url_for('admin.students'))

        # Generate last_initial
        last_initial = last_name[0].upper()

        # Parse DOB and calculate sum
        month, day, year = map(int, dob_str.split('/'))
        dob_sum = month + day + year

        # Generate salt
        salt = get_random_salt()

        # Compute first_half_hash: CONCAT(last_initial, DOB_sum)
        # Updated to match new credential system
        credential = f"{last_initial}{dob_sum}"  # e.g., "S2025"
        first_half_hash = hash_hmac(credential.encode(), salt)
        second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        from app.utils.name_utils import hash_last_name_parts
        last_name_parts = hash_last_name_parts(last_name, salt)

        # Check for duplicates - need to check ALL students GLOBALLY (not scoped to teacher)
        # This prevents creating duplicate accounts when multiple teachers have the same student
        potential_duplicates = Student.query.filter_by(
            last_initial=last_initial,
            dob_sum=dob_sum
        ).all()

        # Check if any existing student matches (using new credential system)
        from app.utils.name_utils import verify_last_name_parts

        for existing_student in potential_duplicates:
            if existing_student.first_name == first_name:
                # Verify credential matches
                test_credential = f"{last_initial}{dob_sum}"
                credential_matches = existing_student.first_half_hash == hash_hmac(test_credential.encode(), existing_student.salt)

                # Also check fuzzy last name matching
                fuzzy_match = False
                if existing_student.last_name_hash_by_part:
                    fuzzy_match = verify_last_name_parts(
                        last_name,
                        existing_student.last_name_hash_by_part,
                        existing_student.salt
                    )

                # Match if BOTH credential AND last name match
                if credential_matches and fuzzy_match:
                    # Student already exists - link to this teacher instead of creating duplicate
                    current_admin_id = session.get("admin_id")

                    # Check if this teacher is already linked to this student
                    from app.models import StudentTeacher
                    existing_link = StudentTeacher.query.filter_by(
                        student_id=existing_student.id,
                        admin_id=current_admin_id
                    ).first()

                    if existing_link:
                        flash(f"Student {first_name} {last_name} is already in your class.", "info")
                    else:
                        # Link this teacher to the existing student
                        _link_student_to_admin(existing_student, current_admin_id)
                        db.session.commit()
                        flash(f"Student {first_name} {last_name} already exists. Added to your class.", "success")

                    return redirect(url_for('admin.students'))

        # Create student
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=dob_sum,
            last_name_hash_by_part=last_name_parts,
            has_completed_setup=False,
            teacher_id=session.get("admin_id"),
        )

        db.session.add(new_student)
        db.session.flush()
        _link_student_to_admin(new_student, session.get("admin_id"))
        db.session.commit()

        flash(f"Successfully added {first_name} {last_initial}. to block {block}.", "success")
    except ValueError:
        flash("Invalid date format. Use MM/DD/YYYY.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


@admin_bp.route('/student/add-manual', methods=['POST'])
@admin_required
def add_manual_student():
    """Add a student with full manual configuration (advanced mode)."""
    try:
        from werkzeug.security import generate_password_hash

        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        dob_str = request.form.get('dob', '').strip()
        block = request.form.get('block', '').strip().upper()
        username = request.form.get('username', '').strip()
        pin = request.form.get('pin', '').strip()
        passphrase = request.form.get('passphrase', '').strip()
        hall_passes = int(request.form.get('hall_passes', 3))
        rent_enabled = request.form.get('rent_enabled') == 'on'
        setup_complete = request.form.get('setup_complete') == 'on'

        if not all([first_name, last_name, dob_str, block]):
            flash("Required fields missing.", "error")
            return redirect(url_for('admin.students'))

        # Generate last_initial
        last_initial = last_name[0].upper()

        # Parse DOB and calculate sum
        month, day, year = map(int, dob_str.split('/'))
        dob_sum = month + day + year

        # Generate salt
        salt = get_random_salt()

        # Compute first_half_hash: CONCAT(last_initial, DOB_sum)
        # Updated to match new credential system
        credential = f"{last_initial}{dob_sum}"  # e.g., "S2025"
        first_half_hash = hash_hmac(credential.encode(), salt)
        second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

        # Compute last_name_hash_by_part for fuzzy matching
        from app.utils.name_utils import hash_last_name_parts, verify_last_name_parts
        last_name_parts = hash_last_name_parts(last_name, salt)

        # Check for duplicates GLOBALLY (not scoped to teacher)
        potential_duplicates = Student.query.filter_by(
            last_initial=last_initial,
            dob_sum=dob_sum
        ).all()

        for existing_student in potential_duplicates:
            if existing_student.first_name == first_name:
                # Verify credential matches
                test_credential = f"{last_initial}{dob_sum}"
                credential_matches = existing_student.first_half_hash == hash_hmac(test_credential.encode(), existing_student.salt)

                # Also check fuzzy last name matching
                fuzzy_match = False
                if existing_student.last_name_hash_by_part:
                    fuzzy_match = verify_last_name_parts(
                        last_name,
                        existing_student.last_name_hash_by_part,
                        existing_student.salt
                    )

                if credential_matches and fuzzy_match:
                    flash(f"Student {first_name} {last_name} already exists. Linking to your class.", "warning")
                    # Link to this teacher
                    from app.models import StudentTeacher
                    current_admin_id = session.get("admin_id")
                    existing_link = StudentTeacher.query.filter_by(
                        student_id=existing_student.id,
                        admin_id=current_admin_id
                    ).first()
                    if not existing_link:
                        _link_student_to_admin(existing_student, current_admin_id)
                        db.session.commit()
                    return redirect(url_for('admin.students'))

        # Create student
        new_student = Student(
            first_name=first_name,
            last_initial=last_initial,
            block=block,
            salt=salt,
            first_half_hash=first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=dob_sum,
            last_name_hash_by_part=last_name_parts,
            hall_passes=hall_passes,
            is_rent_enabled=rent_enabled,
            has_completed_setup=setup_complete,
            teacher_id=session.get("admin_id"),
        )

        # Set username if provided
        if username:
            new_student.username_hash = hash_username(username, salt)
            new_student.username_lookup_hash = hash_username_lookup(username)

        # Set PIN if provided
        if pin:
            new_student.pin_hash = generate_password_hash(pin)

        # Set passphrase if provided
        if passphrase:
            new_student.passphrase_hash = generate_password_hash(passphrase)

        db.session.add(new_student)
        db.session.flush()
        _link_student_to_admin(new_student, session.get("admin_id"))
        db.session.commit()

        flash(f"Successfully created {first_name} {last_initial}. in block {block} (manual mode).", "success")
    except ValueError:
        flash("Invalid date format. Use MM/DD/YYYY.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating student: {str(e)}", "error")

    return redirect(url_for('admin.students'))


# -------------------- STORE MANAGEMENT --------------------

@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store_management():
    """Manage store items - view, create, edit, delete."""
    student_ids_subq = _student_scope_subquery()
    form = StoreItemForm()
    if form.validate_on_submit():
        new_item = StoreItem(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            item_type=form.item_type.data,
            inventory=form.inventory.data,
            limit_per_student=form.limit_per_student.data,
            auto_delist_date=form.auto_delist_date.data,
            auto_expiry_days=form.auto_expiry_days.data,
            is_active=form.is_active.data,
            # Bundle settings
            is_bundle=form.is_bundle.data,
            bundle_quantity=form.bundle_quantity.data if form.is_bundle.data else None,
            # Bulk discount settings
            bulk_discount_enabled=form.bulk_discount_enabled.data,
            bulk_discount_quantity=form.bulk_discount_quantity.data if form.bulk_discount_enabled.data else None,
            bulk_discount_percentage=form.bulk_discount_percentage.data if form.bulk_discount_enabled.data else None
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"'{new_item.name}' has been added to the store.", "success")
        return redirect(url_for('admin.store_management'))

    items = StoreItem.query.order_by(StoreItem.name).all()

    # Get store statistics for overview tab
    from app.models import StudentItem
    total_items = len(items)
    active_items = len([i for i in items if i.is_active])
    total_purchases = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .count()
    )

    return render_template('admin_store.html', form=form, items=items, current_page="store",
                         total_items=total_items, active_items=active_items, total_purchases=total_purchases)


@admin_bp.route('/store/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_store_item(item_id):
    """Edit an existing store item."""
    item = StoreItem.query.get_or_404(item_id)
    form = StoreItemForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        db.session.commit()
        flash(f"'{item.name}' has been updated.", "success")
        return redirect(url_for('admin.store_management'))
    return render_template('admin_edit_item.html', form=form, item=item, current_page="store")


@admin_bp.route('/store/delete/<int:item_id>', methods=['POST'])
@admin_required
def delete_store_item(item_id):
    """Deactivate a store item (soft delete)."""
    item = StoreItem.query.get_or_404(item_id)
    # To preserve history, we'll just deactivate it instead of a hard delete
    # A hard delete would be: db.session.delete(item)
    item.is_active = False
    db.session.commit()
    flash(f"'{item.name}' has been deactivated and removed from the store.", "success")
    return redirect(url_for('admin.store_management'))


@admin_bp.route('/store/hard-delete/<int:item_id>', methods=['POST'])
@admin_required
def hard_delete_store_item(item_id):
    """Permanently delete a store item (hard delete)."""
    item = StoreItem.query.get_or_404(item_id)
    item_name = item.name

    # Check if there are any student purchases of this item
    from app.models import StudentItem
    purchase_count = (
        StudentItem.query
        .join(Student, StudentItem.student_id == Student.id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .filter_by(store_item_id=item_id)
        .count()
    )

    if purchase_count > 0:
        flash(f"Cannot permanently delete '{item_name}' because it has {purchase_count} purchase record(s). Please deactivate instead.", "danger")
        return redirect(url_for('admin.store_management'))

    # Safe to delete - no purchase history
    db.session.delete(item)
    db.session.commit()
    flash(f"'{item_name}' has been permanently deleted from the database.", "success")
    return redirect(url_for('admin.store_management'))


# -------------------- RENT SETTINGS --------------------

@admin_bp.route('/rent-settings', methods=['GET', 'POST'])
@admin_required
def rent_settings():
    """Configure rent settings."""
    student_ids_subq = _student_scope_subquery()
    # Get or create rent settings (singleton)
    settings = RentSettings.query.first()
    if not settings:
        settings = RentSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        # Main toggle
        settings.is_enabled = request.form.get('is_enabled') == 'on'

        # Rent amount and frequency
        settings.rent_amount = float(request.form.get('rent_amount', 50.0))
        settings.frequency_type = request.form.get('frequency_type', 'monthly')

        if settings.frequency_type == 'custom':
            settings.custom_frequency_value = int(request.form.get('custom_frequency_value', 1))
            settings.custom_frequency_unit = request.form.get('custom_frequency_unit', 'days')
        else:
            settings.custom_frequency_value = None
            settings.custom_frequency_unit = None

        # Due date settings
        first_due_date_str = request.form.get('first_rent_due_date')
        if first_due_date_str:
            settings.first_rent_due_date = datetime.strptime(first_due_date_str, '%Y-%m-%d')
        else:
            settings.first_rent_due_date = None

        settings.due_day_of_month = int(request.form.get('due_day_of_month', 1))

        # Grace period and late penalties
        settings.grace_period_days = int(request.form.get('grace_period_days', 3))
        settings.late_penalty_amount = float(request.form.get('late_penalty_amount', 10.0))
        settings.late_penalty_type = request.form.get('late_penalty_type', 'once')

        if settings.late_penalty_type == 'recurring':
            settings.late_penalty_frequency_days = int(request.form.get('late_penalty_frequency_days', 7))
        else:
            settings.late_penalty_frequency_days = None

        # Student payment options
        settings.bill_preview_enabled = request.form.get('bill_preview_enabled') == 'on'
        settings.bill_preview_days = int(request.form.get('bill_preview_days', 7))
        settings.allow_incremental_payment = request.form.get('allow_incremental_payment') == 'on'
        settings.prevent_purchase_when_late = request.form.get('prevent_purchase_when_late') == 'on'

        db.session.commit()
        flash("Rent settings updated successfully!", "success")
        return redirect(url_for('admin.rent_settings'))

    # Get statistics
    total_students = _scoped_students().filter_by(is_rent_enabled=True).count()
    current_month = datetime.now().month
    current_year = datetime.now().year
    paid_this_month = (
        RentPayment.query
        .filter(RentPayment.student_id.in_(student_ids_subq))
        .filter_by(period_month=current_month, period_year=current_year)
        .count()
    )

    # Get active waivers
    now = datetime.now(timezone.utc)
    active_waivers = (
        RentWaiver.query
        .join(Student, RentWaiver.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(RentWaiver.waiver_end_date >= now)
        .all()
    )

    # Get all students for waiver form
    all_students = _scoped_students().order_by(Student.first_name).all()

    # Calculate payroll warning
    payroll_warning = None
    if settings.is_enabled and settings.rent_amount > 0:
        # Get average payroll amount per student per month
        payroll_settings = PayrollSettings.query.filter_by(is_active=True).first()
        if payroll_settings:
            # Calculate rent per month based on frequency
            rent_per_month = settings.rent_amount
            if settings.frequency_type == 'daily':
                rent_per_month = settings.rent_amount * 30
            elif settings.frequency_type == 'weekly':
                rent_per_month = settings.rent_amount * 4
            elif settings.frequency_type == 'custom':
                if settings.custom_frequency_unit == 'days':
                    rent_per_month = settings.rent_amount * (30 / settings.custom_frequency_value)
                elif settings.custom_frequency_unit == 'weeks':
                    rent_per_month = settings.rent_amount * (30 / (settings.custom_frequency_value * 7))
                elif settings.custom_frequency_unit == 'months':
                    rent_per_month = settings.rent_amount / settings.custom_frequency_value

            # Estimate monthly payroll (assuming average 20 work days, 6 hours per day)
            # Using simple mode settings if available
            pay_per_minute = payroll_settings.pay_rate
            estimated_monthly_payroll = pay_per_minute * 60 * 6 * 20  # 6 hours/day * 20 days

            if rent_per_month > estimated_monthly_payroll * 0.8:  # If rent is more than 80% of payroll
                payroll_warning = f"Rent (${rent_per_month:.2f}/month) exceeds recommended 80% of estimated monthly payroll (${estimated_monthly_payroll:.2f}). Students may struggle to afford rent."

    return render_template('admin_rent_settings.html',
                          settings=settings,
                          total_students=total_students,
                          paid_this_month=paid_this_month,
                          active_waivers=active_waivers,
                          all_students=all_students,
                          payroll_warning=payroll_warning)


@admin_bp.route('/rent-waiver/add', methods=['POST'])
@admin_required
def add_rent_waiver():
    """Add rent waiver for selected students."""
    student_ids = request.form.getlist('student_ids')
    periods_count = int(request.form.get('periods_count', 1))
    reason = request.form.get('reason', '')

    if not student_ids:
        flash("Please select at least one student.", "danger")
        return redirect(url_for('admin.rent_settings'))

    # Get rent settings to calculate waiver period
    settings = RentSettings.query.first()
    if not settings:
        flash("Rent settings not configured.", "danger")
        return redirect(url_for('admin.rent_settings'))

    # Calculate waiver end date based on frequency
    now = datetime.now(timezone.utc)
    waiver_start = now

    # Calculate days per period based on frequency type
    if settings.frequency_type == 'daily':
        days_per_period = 1
    elif settings.frequency_type == 'weekly':
        days_per_period = 7
    elif settings.frequency_type == 'monthly':
        days_per_period = 30
    elif settings.frequency_type == 'custom':
        if settings.custom_frequency_unit == 'days':
            days_per_period = settings.custom_frequency_value
        elif settings.custom_frequency_unit == 'weeks':
            days_per_period = settings.custom_frequency_value * 7
        elif settings.custom_frequency_unit == 'months':
            days_per_period = settings.custom_frequency_value * 30
        else:
            days_per_period = 30
    else:
        days_per_period = 30

    total_days = days_per_period * periods_count
    waiver_end = waiver_start + timedelta(days=total_days)

    # Get current admin
    admin_id = session.get('admin_id')

    # Create waivers for each student
    count = 0
    for student_id in student_ids:
        student = _get_student_or_404(int(student_id))
        if student:
            waiver = RentWaiver(
                student_id=student.id,
                waiver_start_date=waiver_start,
                waiver_end_date=waiver_end,
                periods_count=periods_count,
                reason=reason,
                created_by_admin_id=admin_id
            )
            db.session.add(waiver)
            count += 1

    db.session.commit()
    flash(f"Rent waiver added for {count} student(s) for {periods_count} period(s).", "success")
    return redirect(url_for('admin.rent_settings'))


@admin_bp.route('/rent-waiver/<int:waiver_id>/remove', methods=['POST'])
@admin_required
def remove_rent_waiver(waiver_id):
    """Remove a rent waiver."""
    waiver = RentWaiver.query.get_or_404(waiver_id)
    _get_student_or_404(waiver.student_id)
    student_name = waiver.student.full_name
    db.session.delete(waiver)
    db.session.commit()
    flash(f"Rent waiver removed for {student_name}.", "success")
    return redirect(url_for('admin.rent_settings'))


# -------------------- INSURANCE MANAGEMENT --------------------


def _get_tier_namespace_seed(teacher_id):
    """Return a stable seed for tenant-scoped tier IDs using the teacher's join code."""
    join_code_row = (
        TeacherBlock.query
        .filter_by(teacher_id=teacher_id)
        .with_entities(TeacherBlock.join_code)
        .order_by(TeacherBlock.join_code)
        .first()
    )

    return join_code_row[0] if join_code_row else f"teacher-{teacher_id}"


def _generate_tenant_scoped_tier_id(seed, sequence):
    """Create a globally unique tier ID by hashing the teacher join code with a sequence."""
    digest = hashlib.blake2b(f"{seed}:{sequence}".encode(), digest_size=8).digest()
    candidate = int.from_bytes(digest, byteorder='big') % 2_000_000_000
    return candidate or sequence


def _next_tenant_scoped_tier_id(seed, existing_ids):
    """Return the next available tier ID that won't collide across teachers."""
    sequence = len(existing_ids) + 1
    candidate = _generate_tenant_scoped_tier_id(seed, sequence)

    while candidate in existing_ids:
        sequence += 1
        candidate = _generate_tenant_scoped_tier_id(seed, sequence)

    return candidate


@admin_bp.route('/insurance', methods=['GET', 'POST'])
@admin_required
def insurance_management():
    """Main insurance management dashboard."""
    student_ids_subq = _student_scope_subquery()
    form = InsurancePolicyForm()

    current_teacher_id = session.get('admin_id')
    existing_policies = InsurancePolicy.query.filter_by(teacher_id=current_teacher_id).all()

    # Collect existing tier groups for the current teacher
    tier_groups_map = {}
    for policy in existing_policies:
        if policy.tier_category_id:
            category_id = policy.tier_category_id
            if category_id not in tier_groups_map:
                tier_groups_map[category_id] = {
                    'id': category_id,
                    'name': policy.tier_name or f"Group {category_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups_map[category_id]['policies'].append(policy.title)

    tier_groups = sorted(tier_groups_map.values(), key=lambda g: g['id'])
    tier_namespace_seed = _get_tier_namespace_seed(current_teacher_id)
    existing_tier_ids = set(tier_groups_map.keys())
    next_tier_category_id = _next_tenant_scoped_tier_id(tier_namespace_seed, existing_tier_ids)

    if request.method == 'POST' and form.validate_on_submit():
        # Generate unique policy code
        policy_code = secrets.token_urlsafe(12)[:16]
        while InsurancePolicy.query.filter_by(policy_code=policy_code).first():
            policy_code = secrets.token_urlsafe(12)[:16]

        tier_category_id = None
        if form.tier_category_id.data:
            tier_category_id = form.tier_category_id.data
        elif form.tier_name.data or form.tier_color.data:
            tier_category_id = next_tier_category_id

        # Create new insurance policy
        policy = InsurancePolicy(
            policy_code=policy_code,
            teacher_id=session.get('admin_id'),
            title=form.title.data,
            description=form.description.data,
            premium=form.premium.data,
            charge_frequency=form.charge_frequency.data,
            autopay=form.autopay.data,
            waiting_period_days=form.waiting_period_days.data,
            max_claims_count=form.max_claims_count.data,
            max_claims_period=form.max_claims_period.data,
            max_claim_amount=form.max_claim_amount.data,
            max_payout_per_period=form.max_payout_per_period.data,
            claim_type=form.claim_type.data,
            is_monetary=form.claim_type.data != 'non_monetary',
            no_repurchase_after_cancel=form.no_repurchase_after_cancel.data,
            repurchase_wait_days=form.repurchase_wait_days.data,
            auto_cancel_nonpay_days=form.auto_cancel_nonpay_days.data,
            claim_time_limit_days=form.claim_time_limit_days.data,
            bundle_discount_percent=form.bundle_discount_percent.data,
            marketing_badge=form.marketing_badge.data if form.marketing_badge.data else None,
            tier_category_id=tier_category_id,
            tier_name=form.tier_name.data if form.tier_name.data else None,
            tier_color=form.tier_color.data if form.tier_color.data else None,
            settings_mode=request.form.get('settings_mode', 'advanced'),
            is_active=form.is_active.data
        )
        db.session.add(policy)
        db.session.commit()
        flash(f"Insurance policy '{policy.title}' created successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get policies for current teacher only
    policies = existing_policies

    # Get all student enrollments
    active_enrollments = (
        StudentInsurance.query
        .join(Student, StudentInsurance.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentInsurance.status == 'active')
        .all()
    )
    cancelled_enrollments = (
        StudentInsurance.query
        .join(Student, StudentInsurance.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(StudentInsurance.status == 'cancelled')
        .all()
    )

    # Get all claims
    claims = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .order_by(InsuranceClaim.filed_date.desc())
        .all()
    )
    pending_claims_count = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(InsuranceClaim.status == 'pending')
        .count()
    )

    return render_template('admin_insurance.html',
                          form=form,
                          policies=policies,
                          active_enrollments=active_enrollments,
                          cancelled_enrollments=cancelled_enrollments,
                          claims=claims,
                          pending_claims_count=pending_claims_count,
                          tier_groups=tier_groups,
                          next_tier_category_id=next_tier_category_id)


@admin_bp.route('/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def edit_insurance_policy(policy_id):
    """Edit existing insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    form = InsurancePolicyForm(obj=policy)

    teacher_policies = InsurancePolicy.query.filter_by(teacher_id=session.get('admin_id')).all()
    tier_groups_map = {}
    for teacher_policy in teacher_policies:
        if teacher_policy.tier_category_id:
            category_id = teacher_policy.tier_category_id
            if category_id not in tier_groups_map:
                tier_groups_map[category_id] = {
                    'id': category_id,
                    'name': teacher_policy.tier_name or f"Group {category_id}",
                    'color': teacher_policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups_map[category_id]['policies'].append(teacher_policy.title)

    tier_groups = sorted(tier_groups_map.values(), key=lambda g: g['id'])
    tier_namespace_seed = _get_tier_namespace_seed(policy.teacher_id)
    existing_tier_ids = set(tier_groups_map.keys())
    next_tier_category_id = _next_tenant_scoped_tier_id(tier_namespace_seed, existing_tier_ids)

    if request.method == 'POST' and form.validate_on_submit():
        policy.title = form.title.data
        policy.description = form.description.data
        policy.premium = form.premium.data
        policy.charge_frequency = form.charge_frequency.data
        policy.autopay = form.autopay.data
        policy.waiting_period_days = form.waiting_period_days.data
        policy.max_claims_count = form.max_claims_count.data
        policy.max_claims_period = form.max_claims_period.data
        policy.max_claim_amount = form.max_claim_amount.data
        policy.max_payout_per_period = form.max_payout_per_period.data
        policy.claim_type = form.claim_type.data
        policy.is_monetary = form.claim_type.data != 'non_monetary'
        policy.no_repurchase_after_cancel = form.no_repurchase_after_cancel.data
        policy.enable_repurchase_cooldown = form.enable_repurchase_cooldown.data
        policy.repurchase_wait_days = form.repurchase_wait_days.data
        policy.auto_cancel_nonpay_days = form.auto_cancel_nonpay_days.data
        policy.claim_time_limit_days = form.claim_time_limit_days.data
        policy.bundle_with_policy_ids = form.bundle_with_policy_ids.data
        policy.bundle_discount_percent = form.bundle_discount_percent.data
        policy.bundle_discount_amount = form.bundle_discount_amount.data
        policy.marketing_badge = form.marketing_badge.data if form.marketing_badge.data else None
        if form.tier_category_id.data:
            policy.tier_category_id = form.tier_category_id.data
        elif form.tier_name.data or form.tier_color.data:
            policy.tier_category_id = next_tier_category_id
        else:
            policy.tier_category_id = None
        policy.tier_name = form.tier_name.data if form.tier_name.data else None
        policy.tier_color = form.tier_color.data if form.tier_color.data else None
        policy.is_active = form.is_active.data

        db.session.commit()
        flash(f"Insurance policy '{policy.title}' updated successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get other active policies for bundle selection (excluding current policy)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.id != policy_id
    ).all()

    return render_template(
        'admin_edit_insurance_policy.html',
        form=form,
        policy=policy,
        available_policies=available_policies,
        tier_groups=tier_groups,
        next_tier_category_id=next_tier_category_id
    )


@admin_bp.route('/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
def deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    policy.is_active = False
    db.session.commit()
    flash(f"Insurance policy '{policy.title}' has been deactivated.", "success")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/delete/<int:policy_id>', methods=['POST'])
@admin_required
def delete_insurance_policy(policy_id):
    """Delete an insurance policy and all associated data.

    Since each teacher has their own policy instances (identified by policy_code),
    this safely deletes only the current teacher's policy data without affecting
    other teachers.
    """
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    force_delete = request.form.get('force_delete') == 'true'

    student_ids_subq = _student_scope_subquery()

    # Check for active enrollments within scope
    active_enrollments = StudentInsurance.query.filter(
        StudentInsurance.policy_id == policy_id,
        StudentInsurance.status == 'active',
        StudentInsurance.student_id.in_(student_ids_subq),
    ).count()

    # Check for pending claims within scope
    pending_claims = InsuranceClaim.query.filter(
        InsuranceClaim.policy_id == policy_id,
        InsuranceClaim.status == 'pending',
        InsuranceClaim.student_id.in_(student_ids_subq),
    ).count()

    if not force_delete and (active_enrollments > 0 or pending_claims > 0):
        flash(f"Cannot delete policy '{policy.title}': {active_enrollments} active enrollments and {pending_claims} pending claims. Cancel all enrollments first or use force delete.", "danger")
        return redirect(url_for('admin.insurance_management'))

    try:
        # Cancel active enrollments if force delete
        if force_delete and active_enrollments > 0:
            cancelled_count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.status == 'active',
                StudentInsurance.student_id.in_(student_ids_subq),
            ).update({'status': 'cancelled'}, synchronize_session=False)
            flash(f"Cancelled {cancelled_count} active enrollments.", "info")

        # Delete all claims for this policy
        claims_deleted = InsuranceClaim.query.filter(
            InsuranceClaim.policy_id == policy_id,
            InsuranceClaim.student_id.in_(student_ids_subq),
        ).delete(synchronize_session=False)

        # Delete all enrollments for this policy
        enrollments_deleted = StudentInsurance.query.filter(
            StudentInsurance.policy_id == policy_id,
            StudentInsurance.student_id.in_(student_ids_subq),
        ).delete(synchronize_session=False)

        # Delete the policy itself
        db.session.delete(policy)
        db.session.commit()

        flash(f"Successfully deleted policy '{policy.title}' ({enrollments_deleted} enrollments and {claims_deleted} claims removed).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting policy: {str(e)}", "danger")

    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/mass-remove/<int:policy_id>', methods=['POST'])
@admin_required
def mass_remove_policy(policy_id):
    """Cancel insurance policy for multiple or all students."""
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Verify this policy belongs to the current teacher
    if policy.teacher_id != session.get('admin_id'):
        abort(403)

    # Get list of student IDs to remove (or 'all')
    student_ids_raw = request.form.get('student_ids', 'all')

    # Get scoped student IDs subquery
    student_ids_subq = _student_scope_subquery()

    if student_ids_raw == 'all':
        # Cancel for all active students in scope
        count = StudentInsurance.query.filter(
            StudentInsurance.policy_id == policy_id,
            StudentInsurance.status == 'active',
            StudentInsurance.student_id.in_(student_ids_subq)
        ).update({'status': 'cancelled'}, synchronize_session=False)
    else:
        # Cancel for specific students
        try:
            student_ids = [int(sid.strip()) for sid in student_ids_raw.split(',') if sid.strip()]
            count = StudentInsurance.query.filter(
                StudentInsurance.policy_id == policy_id,
                StudentInsurance.student_id.in_(student_ids),
                StudentInsurance.student_id.in_(student_ids_subq),
                StudentInsurance.status == 'active'
            ).update({'status': 'cancelled'}, synchronize_session=False)
        except ValueError:
            flash("Invalid student IDs provided.", "danger")
            return redirect(url_for('admin.insurance_management'))

    db.session.commit()

    if student_ids_raw == 'all':
        flash(f"Cancelled policy '{policy.title}' for {count} students.", "success")
    else:
        flash(f"Cancelled policy '{policy.title}' for {count} selected students.", "success")

    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/student-policy/<int:enrollment_id>')
@admin_required
def view_student_policy(enrollment_id):
    """View student's policy enrollment details and claims history."""
    enrollment = (
        StudentInsurance.query
        .join(Student, StudentInsurance.student_id == Student.id)
        .filter(StudentInsurance.id == enrollment_id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )

    # Get claims for this enrollment
    claims = InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    return render_template('admin_view_student_policy.html',
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          student=enrollment.student,
                          claims=claims)


@admin_bp.route('/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def process_claim(claim_id):
    """Process insurance claim with auto-deposit for monetary claims."""
    claim = (
        InsuranceClaim.query
        .join(Student, InsuranceClaim.student_id == Student.id)
        .filter(InsuranceClaim.id == claim_id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )
    form = AdminClaimProcessForm(obj=claim)

    # Get enrollment details
    enrollment = StudentInsurance.query.get(claim.student_insurance_id)

    def _get_period_bounds():
        now = datetime.utcnow()
        if claim.policy.max_claims_period == 'year':
            return (
                now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                now.replace(month=12, day=31, hour=23, minute=59, second=59),
            )
        if claim.policy.max_claims_period == 'semester':
            if now.month <= 6:
                return (
                    now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                    now.replace(month=6, day=30, hour=23, minute=59, second=59),
                )
            return (
                now.replace(month=7, day=1, hour=0, minute=0, second=0, microsecond=0),
                now.replace(month=12, day=31, hour=23, minute=59, second=59),
            )
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(seconds=1)
        return period_start, period_end

    period_start, period_end = _get_period_bounds()

    def _claim_base_amount(target_claim):
        if target_claim.policy.claim_type == 'transaction_monetary' and target_claim.transaction:
            return abs(target_claim.transaction.amount)
        return target_claim.claim_amount or 0.0

    # Validate claim
    validation_errors = []

    # Check if coverage has started (past waiting period)
    if not enrollment.coverage_start_date or enrollment.coverage_start_date > datetime.utcnow():
        validation_errors.append("Coverage has not started yet (still in waiting period)")

    # Check if payment is current
    if not enrollment.payment_current:
        validation_errors.append("Premium payments are not current")

    if claim.policy.claim_type == 'transaction_monetary' and not claim.transaction:
        validation_errors.append("Transaction-based claim is missing a linked transaction")
    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction and claim.transaction.is_void:
        validation_errors.append("Linked transaction has been voided and cannot be reimbursed")

    # P0-3 Fix: Validate transaction ownership to prevent cross-student fraud
    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction:
        if claim.transaction.student_id != claim.student_id:
            validation_errors.append(
                f"SECURITY: Transaction ownership mismatch. "
                f"Transaction belongs to student ID {claim.transaction.student_id}, "
                f"but claim filed by student ID {claim.student_id}."
            )
            current_app.logger.error(
                f"SECURITY ALERT: Transaction ownership mismatch in claim {claim.id}. "
                f"Claim student_id={claim.student_id}, transaction student_id={claim.transaction.student_id}"
            )

    if claim.policy.claim_type == 'transaction_monetary' and claim.transaction_id:
        duplicate_claim = InsuranceClaim.query.filter(
            InsuranceClaim.transaction_id == claim.transaction_id,
            InsuranceClaim.id != claim.id,
        ).first()
        if duplicate_claim:
            validation_errors.append("Another claim is already tied to this transaction")

    incident_reference = claim.transaction.timestamp if claim.policy.claim_type == 'transaction_monetary' and claim.transaction else claim.incident_date
    days_since_incident = (datetime.utcnow() - incident_reference).days
    if days_since_incident > claim.policy.claim_time_limit_days:
        validation_errors.append(f"Claim filed too late ({days_since_incident} days after incident, limit is {claim.policy.claim_time_limit_days} days)")

    # Check max claims count
    approved_claims = InsuranceClaim.query.filter(
        InsuranceClaim.student_insurance_id == enrollment.id,
        InsuranceClaim.status.in_(['approved', 'paid']),
        InsuranceClaim.processed_date >= period_start,
        InsuranceClaim.processed_date <= period_end,
        InsuranceClaim.id != claim.id,
    )
    if claim.policy.max_claims_count and approved_claims.count() >= claim.policy.max_claims_count:
        validation_errors.append(f"Maximum claims limit reached ({claim.policy.max_claims_count} per {claim.policy.max_claims_period})")

    period_payouts = None
    remaining_period_cap = None
    if claim.policy.max_payout_per_period:
        period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid']),
            InsuranceClaim.processed_date >= period_start,
            InsuranceClaim.processed_date <= period_end,
            InsuranceClaim.approved_amount.isnot(None),
            InsuranceClaim.id != claim.id,
        ).scalar() or 0.0

        requested_amount = _claim_base_amount(claim)
        remaining_period_cap = max(claim.policy.max_payout_per_period - period_payouts, 0)
        if remaining_period_cap is not None and requested_amount > remaining_period_cap and claim.policy.claim_type != 'non_monetary':
            validation_errors.append(
                f"Maximum payout limit would be exceeded (${period_payouts:.2f} paid + ${requested_amount:.2f} requested > ${claim.policy.max_payout_per_period:.2f} limit per {claim.policy.max_claims_period})"
            )

    # Get claims statistics
    claims_stats = {
        'pending': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='pending').count(),
        'approved': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='approved').count(),
        'rejected': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='rejected').count(),
        'paid': InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id, status='paid').count(),
    }

    if request.method == 'POST' and form.validate_on_submit():
        old_status = claim.status
        new_status = form.status.data

        is_monetary_claim = claim.policy.claim_type != 'non_monetary'
        requires_payout = is_monetary_claim and new_status in ('approved', 'paid') and old_status not in ('approved', 'paid')

        if validation_errors and requires_payout:
            flash("Resolve validation errors before approving or paying out this claim.", "danger")
            return redirect(url_for('admin.process_claim', claim_id=claim_id))

        claim.status = new_status
        claim.admin_notes = form.admin_notes.data
        claim.rejection_reason = form.rejection_reason.data if new_status == 'rejected' else None
        claim.processed_date = datetime.utcnow()
        claim.processed_by_admin_id = session.get('admin_id')

        # Handle monetary claims - auto-deposit when approved/paid
        if requires_payout:
            approved_claims_count = approved_claims.count()
            if claim.policy.max_claims_count and approved_claims_count >= claim.policy.max_claims_count:
                flash(f"Cannot approve claim: maximum of {claim.policy.max_claims_count} claims already reached this {claim.policy.max_claims_period}.", "danger")
                db.session.rollback()
                return redirect(url_for('admin.process_claim', claim_id=claim_id))

            base_amount = _claim_base_amount(claim)
            approved_amount = base_amount
            if claim.policy.claim_type == 'legacy_monetary' and form.approved_amount.data is not None:
                approved_amount = form.approved_amount.data

            if claim.policy.max_claim_amount:
                approved_amount = min(approved_amount, claim.policy.max_claim_amount)

            if remaining_period_cap is not None:
                if remaining_period_cap <= 0:
                    flash(
                        f"Cannot approve claim: Would exceed maximum payout limit of ${claim.policy.max_payout_per_period:.2f} per {claim.policy.max_claims_period} (${period_payouts:.2f} already paid)",
                        "danger",
                    )
                    db.session.rollback()
                    return redirect(url_for('admin.process_claim', claim_id=claim_id))
                approved_amount = min(approved_amount, remaining_period_cap)

            claim.approved_amount = approved_amount

            # Auto-deposit to student's checking account via transaction
            student = claim.student

            transaction_description = f"Insurance reimbursement for claim #{claim.id} ({claim.policy.title})"
            if claim.transaction_id:
                transaction_description += f" linked to transaction #{claim.transaction_id}"

            transaction = Transaction(
                student_id=student.id,
                teacher_id=claim.policy.teacher_id,
                amount=approved_amount,
                account_type='checking',
                type='insurance_reimbursement',
                description=transaction_description,
            )
            db.session.add(transaction)

            flash(f"Monetary claim approved! ${approved_amount:.2f} deposited to {student.full_name}'s checking account.", "success")
        elif claim.policy.claim_type == 'non_monetary' and new_status == 'approved':
            claim.approved_amount = None
            flash(f"Non-monetary claim approved for {claim.claim_item}. Item/service will be provided offline.", "success")
        elif new_status == 'rejected':
            flash("Claim has been rejected.", "warning")

        db.session.commit()
        return redirect(url_for('admin.insurance_management'))

    return render_template('admin_process_claim.html',
                          claim=claim,
                          form=form,
                          enrollment=enrollment,
                          validation_errors=validation_errors,
                          claims_stats=claims_stats,
                          remaining_period_cap=remaining_period_cap,
                          period_payouts=period_payouts)


# -------------------- TRANSACTIONS --------------------

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """Redirect to banking page - transactions now under banking."""
    # Preserve query parameters when redirecting
    return redirect(url_for('admin.banking', **request.args))


@admin_bp.route('/void-transaction/<int:transaction_id>', methods=['POST'])
@admin_required
def void_transaction(transaction_id):
    """Void a transaction."""
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    tx = (
        Transaction.query
        .join(Student, Transaction.student_id == Student.id)
        .filter(Transaction.id == transaction_id)
        .filter(Student.id.in_(_student_scope_subquery()))
        .first_or_404()
    )
    tx.is_void = True
    try:
        db.session.commit()
        current_app.logger.info(f"Transaction {transaction_id} voided")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to void transaction {transaction_id}: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Failed to void transaction"), 500
        flash("Error voiding transaction.", "error")
        return redirect(request.referrer or url_for('admin.dashboard'))
    if is_json:
        return jsonify(status="success", message="Transaction voided.")
    flash("✅ Transaction voided.", "success")
    return redirect(request.referrer or url_for('admin.dashboard'))


# -------------------- HALL PASS MANAGEMENT --------------------

@admin_bp.route('/hall-pass')
@admin_required
def hall_pass():
    """Manage hall pass requests and active passes."""
    student_ids_subq = _student_scope_subquery()
    pending_requests = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'pending')
        .order_by(HallPassLog.request_time.asc())
        .all()
    )
    approved_queue = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'approved')
        .order_by(HallPassLog.decision_time.asc())
        .all()
    )
    out_of_class = (
        HallPassLog.query
        .join(Student, HallPassLog.student_id == Student.id)
        .filter(Student.id.in_(student_ids_subq))
        .filter(HallPassLog.status == 'left')
        .order_by(HallPassLog.left_time.asc())
        .all()
    )

    return render_template(
        'admin_hall_pass.html',
        pending_requests=pending_requests,
        approved_queue=approved_queue,
        out_of_class=out_of_class,
        current_page="hall_pass"
    )


# -------------------- PAYROLL --------------------

@admin_bp.route('/payroll-history')
@admin_required
def payroll_history():
    """View payroll history with filtering."""
    current_app.logger.info("🧭 Entered admin_payroll_history route")
    student_ids_subq = _student_scope_subquery()

    block = request.args.get("block")
    current_app.logger.info(f"📊 Block filter: {block}")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    current_app.logger.info(f"📅 Date filters: start={start_date_str}, end={end_date_str}")

    query = Transaction.query.filter(
        Transaction.student_id.in_(student_ids_subq),
        Transaction.type == "payroll",
    )

    if block:
        # Stream students in batches for this block
        student_ids = [s.id for s in _scoped_students().filter_by(block=block).yield_per(50).all()]
        current_app.logger.info(f"👥 Student IDs in block '{block}': {student_ids}")
        query = query.filter(Transaction.student_id.in_(student_ids))

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        query = query.filter(Transaction.timestamp >= start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)

    payroll_transactions = query.order_by(desc(Transaction.timestamp)).all()
    current_app.logger.info(f"🔎 Payroll transactions found: {len(payroll_transactions)}")

    # Stream students in batches to reduce memory usage for the lookup
    student_lookup = {s.id: s for s in _scoped_students().yield_per(50)}
    # Gather distinct block names for the dropdown
    blocks = sorted({s.block for s in student_lookup.values() if s.block})

    payroll_records = []
    for tx in payroll_transactions:
        student = student_lookup.get(tx.student_id)
        payroll_records.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'block': student.block if student else 'Unknown',
            'student_id': student.id if student else tx.student_id,
            'student_name': student.full_name if student else 'Unknown',
            'amount': tx.amount,
            'notes': tx.description,
        })

    current_app.logger.info(f"📄 Payroll records prepared: {len(payroll_records)}")

    # Current timestamp for header (Pacific Time)
    pacific = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(pacific)

    return render_template(
        'admin_payroll_history.html',
        payroll_history=payroll_records,
        blocks=blocks,
        current_page="payroll_history",
        selected_block=block,
        selected_start=start_date_str,
        selected_end=end_date_str,
        current_time=current_time
    )


@admin_bp.route('/run-payroll', methods=['POST'])
@admin_required
def run_payroll():
    """
    Run payroll by computing earned seconds from TapEvent append-only log.
    For each student, for each block, match active/inactive pairs since last payroll,
    sum total seconds, and post Transaction(s) of type 'payroll'.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        last_payroll_tx = Transaction.query.filter_by(type="payroll").order_by(Transaction.timestamp.desc()).first()
        last_payroll_time = last_payroll_tx.timestamp if last_payroll_tx else None
        current_app.logger.info(f"🧮 RUN PAYROLL: Last payroll at {last_payroll_time}")

        students = _scoped_students().all()
        summary = calculate_payroll(students, last_payroll_time)

        for student_id, amount in summary.items():
            tx = Transaction(
                student_id=student_id,
                amount=amount,
                description=f"Payroll based on attendance",
                account_type="checking",
                type="payroll"
            )
            db.session.add(tx)

        db.session.commit()
        current_app.logger.info(f"✅ Payroll complete. Paid {len(summary)} students.")
        if is_json:
            return jsonify(status="success", message=f"Payroll complete. Paid {len(summary)} students.")
        flash(f"✅ Payroll complete. Paid {len(summary)} students.", "admin_success")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Payroll error: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Payroll error occurred. Check logs."), 500
        flash("Payroll error occurred. Check logs.", "admin_error")
    if not is_json:
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/payroll')
@admin_required
def payroll():
    """
    Enhanced payroll page with tabs for settings, students, rewards, fines, and manual payments.
    """
    pacific = pytz.timezone('America/Los_Angeles')
    last_payroll_time = get_last_payroll_time()

    # Normalize to UTC to avoid any naive/aware mismatches downstream
    if last_payroll_time and last_payroll_time.tzinfo is None:
        last_payroll_time = last_payroll_time.replace(tzinfo=timezone.utc)


    now_utc = datetime.now(timezone.utc)

    # Get student scope subquery for filtering
    student_ids_subq = _student_scope_subquery()

    # Get all students
    students = _scoped_students().all()

    # Get all blocks (split multi-block assignments like "A, B")
    blocks = sorted({b.strip() for s in students for b in (s.block or "").split(',') if b.strip()})

    # Check if payroll settings exist
    has_settings = PayrollSettings.query.first() is not None
    show_setup_banner = not has_settings

    # Get payroll settings
    block_settings = PayrollSettings.query.filter_by(is_active=True).all()

    # Get default/global settings for form pre-population
    default_setting = PayrollSettings.query.filter_by(block=None, is_active=True).first()

    # Organize settings by block for display and lookup
    settings_by_block = {}
    for setting in block_settings:
        if setting.block:
            settings_by_block[setting.block] = setting

    def _as_utc(dt):
        if not dt:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    def _compute_next_pay_date(setting, now):
        freq_days = setting.payroll_frequency_days if setting and setting.payroll_frequency_days else 14
        first_pay = _as_utc(setting.first_pay_date) if setting and setting.first_pay_date else None

        # Anchor the schedule strictly to the configured first pay date so manual runs
        # don't shift the calendar. If no first date is set, fall back to now + frequency.
        if first_pay:
            if first_pay > now:
                return first_pay

            elapsed_days = (now - first_pay).days
            periods_since_first = elapsed_days // freq_days
            candidate = first_pay + timedelta(days=freq_days * (periods_since_first + 1))
        else:
            candidate = now + timedelta(days=freq_days)

        while candidate <= now:
            candidate += timedelta(days=freq_days)
        return candidate

    # Next scheduled payroll calculation (keep in UTC for template)
    next_pay_date_utc = _compute_next_pay_date(default_setting, now_utc)

    # Recent payroll activity
    recent_payrolls = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter_by(type='payroll')
        .order_by(Transaction.timestamp.desc())
        .limit(20)
        .all()
    )

    # Calculate payroll estimates
    payroll_summary = calculate_payroll(students, last_payroll_time)
    total_payroll_estimate = sum(payroll_summary.values())

    # Next payroll by block
    next_payroll_by_block = []
    for block in blocks:
        block_students = [s for s in students if block in [b.strip() for b in (s.block or '').split(',')]]
        block_estimate = sum(payroll_summary.get(s.id, 0) for s in block_students)
        setting = settings_by_block.get(block, default_setting)
        block_next_payroll = _compute_next_pay_date(setting, now_utc)
        next_payroll_by_block.append({
            'block': block,
            'next_date': block_next_payroll,  # Keep in UTC
            'next_date_iso': format_utc_iso(block_next_payroll),
            'estimate': block_estimate
        })

    # Student statistics
    student_stats = []
    for student in students:
        # Calculate unpaid minutes across all blocks
        unpaid_seconds = 0
        student_blocks = [b.strip() for b in (student.block or "").split(',') if b.strip()]
        for block in student_blocks:
            # TapEvent.period is stored in uppercase, so uppercase the block name
            unpaid_seconds += calculate_unpaid_attendance_seconds(student.id, block.upper(), last_payroll_time)

        unpaid_minutes = unpaid_seconds / 60.0
        estimated_payout = payroll_summary.get(student.id, 0)

        # Get last payroll date
        last_payroll = Transaction.query.filter_by(
            student_id=student.id,
            type='payroll'
        ).order_by(Transaction.timestamp.desc()).first()

        # Total earned from payroll
        total_earned = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.student_id == student.id,
            Transaction.type == 'payroll',
            Transaction.is_void == False
        ).scalar() or 0.0

        student_stats.append({
            'student_id': student.id,
            'student_name': student.full_name,
            'block': student.block,
            'unpaid_minutes': int(unpaid_minutes),
            'estimated_payout': estimated_payout,
            'last_payroll_date': last_payroll.timestamp if last_payroll else None,
            'total_earned': total_earned
        })

    # Get rewards and fines
    rewards = PayrollReward.query.order_by(PayrollReward.created_at.desc()).all()
    fines = PayrollFine.query.order_by(PayrollFine.created_at.desc()).all()

    # Initialize forms
    settings_form = PayrollSettingsForm()
    settings_form.block.choices = [('', 'Global (All Blocks)')] + [(b, b) for b in blocks]

    reward_form = PayrollRewardForm()
    fine_form = PayrollFineForm()
    manual_payment_form = ManualPaymentForm()

    # Quick stats
    avg_payout = total_payroll_estimate / len(students) if students else 0

    # Payroll history for History tab (all transaction types, not just payroll)
    payroll_history_transactions = (
        Transaction.query
        .filter(Transaction.student_id.in_(student_ids_subq))
        .filter(Transaction.type.in_(['payroll', 'reward', 'fine', 'manual_payment']))
        .order_by(Transaction.timestamp.desc())
        .limit(100)
        .all()
    )
    student_lookup = {s.id: s for s in students}
    payroll_history = []
    for tx in payroll_history_transactions:
        student = student_lookup.get(tx.student_id)
        payroll_history.append({
            'transaction_id': tx.id,
            'timestamp': tx.timestamp,
            'type': tx.type or 'manual_payment',
            'block': student.block if student else 'Unknown',
            'student_id': tx.student_id,
            'student': student,
            'student_name': student.full_name if student else 'Unknown',
            'amount': tx.amount,
            'notes': tx.description or '',
            'is_void': tx.is_void
        })

    return render_template(
        'admin_payroll.html',
        # Overview tab
        recent_payrolls=recent_payrolls,
        next_payroll_date=next_pay_date_utc,  # Pass UTC timestamp
        next_payroll_by_block=next_payroll_by_block,
        total_payroll_estimate=total_payroll_estimate,
        total_students=len(students),
        avg_payout=avg_payout,
        total_blocks=len(blocks),
        # Settings tab
        settings_form=settings_form,
        block_settings=block_settings,
        default_setting=default_setting,
        settings_by_block=settings_by_block,
        next_global_payroll=next_pay_date_utc,  # Pass UTC timestamp
        show_setup_banner=show_setup_banner,
        # Students tab
        student_stats=student_stats,
        # Rewards & Fines tab
        rewards=rewards,
        fines=fines,
        reward_form=reward_form,
        fine_form=fine_form,
        # Manual Payment tab
        manual_payment_form=manual_payment_form,
        all_students=students,
        # History tab
        payroll_history=payroll_history,
        # General
        blocks=blocks,
        current_page="payroll",
        format_utc_iso=format_utc_iso
    )


@admin_bp.route('/payroll/settings', methods=['POST'])
@admin_required
def payroll_settings():
    """Save payroll settings for a block or globally (Simple or Advanced mode)."""
    try:
        # Get all blocks
        students = _scoped_students().all()
        blocks = sorted(set(s.block for s in students if s.block))

        # Determine which mode we're in
        settings_mode = request.form.get('settings_mode', 'simple')

        # Parse form data based on mode
        if settings_mode == 'simple':
            # Simple mode fields
            pay_rate_per_hour = float(request.form.get('simple_pay_rate', 15.0))
            pay_rate_per_minute = pay_rate_per_hour / 60.0  # Convert to per-minute for storage

            frequency = request.form.get('simple_frequency', 'biweekly')
            frequency_days_map = {'weekly': 7, 'biweekly': 14, 'monthly': 30}
            payroll_frequency_days = frequency_days_map.get(frequency, 14)

            first_pay_date_str = request.form.get('simple_first_pay_date')
            first_pay_date = datetime.strptime(first_pay_date_str, '%Y-%m-%d') if first_pay_date_str else None

            daily_limit_hours = request.form.get('simple_daily_limit')
            daily_limit_hours = float(daily_limit_hours) if daily_limit_hours else None

            apply_to = request.form.get('simple_apply_to', 'all')
            selected_blocks = request.form.getlist('simple_blocks[]') if apply_to == 'selected' else blocks

            # Create settings dict for simple mode
            settings_data = {
                'settings_mode': 'simple',
                'pay_rate': pay_rate_per_minute,
                'payroll_frequency_days': payroll_frequency_days,
                'first_pay_date': first_pay_date,
                'daily_limit_hours': daily_limit_hours,
                'time_unit': 'minutes',
                'pay_schedule_type': frequency,
                'is_active': True,
                # Reset advanced fields
                'overtime_enabled': False,
                'overtime_threshold': None,
                'overtime_threshold_unit': None,
                'overtime_threshold_period': None,
                'overtime_multiplier': 1.0,
                'max_time_per_day': None,
                'max_time_per_day_unit': None,
                'rounding_mode': 'down'
            }

        else:  # Advanced mode
            pay_amount = float(request.form.get('adv_pay_amount', 0.25))
            time_unit = request.form.get('adv_time_unit', 'minutes')

            # Convert to per-minute for storage
            unit_to_minute_multiplier = {
                'seconds': 60,
                'minutes': 1,
                'hours': 1/60,
                'days': 1/(60*24)
            }
            pay_rate_per_minute = pay_amount * unit_to_minute_multiplier.get(time_unit, 1)

            # Overtime settings
            overtime_enabled = 'adv_overtime_enabled' in request.form
            overtime_threshold = request.form.get('adv_overtime_threshold')
            overtime_threshold = float(overtime_threshold) if overtime_threshold else None
            overtime_unit = request.form.get('adv_overtime_unit')
            overtime_period = request.form.get('adv_overtime_period')
            overtime_multiplier = request.form.get('adv_overtime_multiplier')
            overtime_multiplier = float(overtime_multiplier) if overtime_multiplier else 1.0

            # Max time per day
            max_time_value = request.form.get('adv_max_time_value')
            max_time_value = float(max_time_value) if max_time_value else None
            max_time_unit = request.form.get('adv_max_time_unit')

            # Pay schedule
            pay_schedule = request.form.get('adv_pay_schedule', 'biweekly')
            custom_value = request.form.get('adv_custom_schedule_value')
            custom_unit = request.form.get('adv_custom_schedule_unit')

            # Calculate payroll_frequency_days
            if pay_schedule == 'custom':
                custom_value = int(custom_value) if custom_value else 14
                if custom_unit == 'weeks':
                    payroll_frequency_days = custom_value * 7
                else:  # days
                    payroll_frequency_days = custom_value
            else:
                schedule_map = {'daily': 1, 'weekly': 7, 'biweekly': 14, 'monthly': 30}
                payroll_frequency_days = schedule_map.get(pay_schedule, 14)

            first_pay_date_str = request.form.get('adv_first_pay_date')
            first_pay_date = datetime.strptime(first_pay_date_str, '%Y-%m-%d') if first_pay_date_str else None

            rounding = request.form.get('adv_rounding', 'down')

            apply_to = request.form.get('adv_apply_to', 'all')
            selected_blocks = request.form.getlist('adv_blocks[]') if apply_to == 'selected' else blocks

            settings_data = {
                'settings_mode': 'advanced',
                'pay_rate': pay_rate_per_minute,
                'time_unit': time_unit,
                'overtime_enabled': overtime_enabled,
                'overtime_threshold': overtime_threshold,
                'overtime_threshold_unit': overtime_unit if overtime_enabled else None,
                'overtime_threshold_period': overtime_period if overtime_enabled else None,
                'overtime_multiplier': overtime_multiplier if overtime_enabled else 1.0,
                'max_time_per_day': max_time_value,
                'max_time_per_day_unit': max_time_unit if max_time_value else None,
                'pay_schedule_type': pay_schedule,
                'pay_schedule_custom_value': int(custom_value) if pay_schedule == 'custom' and custom_value else None,
                'pay_schedule_custom_unit': custom_unit if pay_schedule == 'custom' else None,
                'payroll_frequency_days': payroll_frequency_days,
                'first_pay_date': first_pay_date,
                'rounding_mode': rounding,
                'is_active': True,
                # Reset simple fields
                'daily_limit_hours': None
            }

        # Apply settings to selected blocks or all
        if apply_to == 'all' or not selected_blocks:
            # Apply to all blocks + global
            target_blocks = [None] + blocks  # None = global
        else:
            # Apply to selected blocks only
            target_blocks = selected_blocks

        for block_value in target_blocks:
            setting = PayrollSettings.query.filter_by(block=block_value).first()
            if not setting:
                setting = PayrollSettings(block=block_value)

            # Update all fields
            for key, value in settings_data.items():
                setattr(setting, key, value)

            setting.updated_at = datetime.utcnow()
            db.session.add(setting)

        db.session.commit()

        if apply_to == 'all' or not selected_blocks:
            flash(f'Payroll settings ({settings_mode} mode) applied to all periods successfully!', 'success')
        else:
            flash(f'Payroll settings ({settings_mode} mode) applied to {len(selected_blocks)} period(s) successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving payroll settings: {e}")
        flash(f'Error saving payroll settings: {str(e)}', 'error')

    return redirect(url_for('admin.payroll'))


# -------------------- PAYROLL REWARDS & FINES --------------------

@admin_bp.route('/payroll/rewards/add', methods=['POST'])
@admin_required
def payroll_add_reward():
    """Add a new payroll reward."""
    form = PayrollRewardForm()

    if form.validate_on_submit():
        try:
            reward = PayrollReward(
                name=form.name.data,
                description=form.description.data,
                amount=form.amount.data,
                is_active=form.is_active.data
            )
            db.session.add(reward)
            db.session.commit()
            flash(f'Reward "{reward.name}" created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating reward: {e}")
            flash('Error creating reward. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/rewards/<int:reward_id>/delete', methods=['POST'])
@admin_required
def payroll_delete_reward(reward_id):
    """Delete a payroll reward."""
    try:
        reward = PayrollReward.query.get_or_404(reward_id)
        db.session.delete(reward)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reward deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting reward: {e}")
        return jsonify({'success': False, 'message': 'Error deleting reward'}), 500


@admin_bp.route('/payroll/fines/add', methods=['POST'])
@admin_required
def payroll_add_fine():
    """Add a new payroll fine."""
    form = PayrollFineForm()

    if form.validate_on_submit():
        try:
            fine = PayrollFine(
                name=form.name.data,
                description=form.description.data,
                amount=form.amount.data,
                is_active=form.is_active.data
            )
            db.session.add(fine)
            db.session.commit()
            flash(f'Fine "{fine.name}" created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating fine: {e}")
            flash('Error creating fine. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


@admin_bp.route('/payroll/fines/<int:fine_id>/delete', methods=['POST'])
@admin_required
def payroll_delete_fine(fine_id):
    """Delete a payroll fine."""
    try:
        fine = PayrollFine.query.get_or_404(fine_id)
        db.session.delete(fine)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine deleted successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting fine: {e}")
        return jsonify({'success': False, 'message': 'Error deleting fine'}), 500


@admin_bp.route('/payroll/rewards/<int:reward_id>/edit', methods=['POST'])
@admin_required
def payroll_edit_reward(reward_id):
    """Edit an existing reward."""
    try:
        reward = PayrollReward.query.get_or_404(reward_id)
        data = request.get_json()

        reward.name = data.get('name', reward.name)
        reward.description = data.get('description', reward.description)
        reward.amount = float(data.get('amount', reward.amount))
        reward.is_active = data.get('is_active', reward.is_active)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Reward updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing reward: {e}")
        return jsonify({'success': False, 'message': 'Error editing reward'}), 500


@admin_bp.route('/payroll/fines/<int:fine_id>/edit', methods=['POST'])
@admin_required
def payroll_edit_fine(fine_id):
    """Edit an existing fine."""
    try:
        fine = PayrollFine.query.get_or_404(fine_id)
        data = request.get_json()

        fine.name = data.get('name', fine.name)
        fine.description = data.get('description', fine.description)
        fine.amount = float(data.get('amount', fine.amount))
        fine.is_active = data.get('is_active', fine.is_active)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing fine: {e}")
        return jsonify({'success': False, 'message': 'Error editing fine'}), 500


@admin_bp.route('/payroll/transactions/<int:transaction_id>/void', methods=['POST'])
@admin_required
def void_payroll_transaction(transaction_id):
    """Void a single transaction from payroll interface."""
    try:
        transaction = (
            Transaction.query
            .join(Student, Transaction.student_id == Student.id)
            .filter(Transaction.id == transaction_id)
            .filter(Student.id.in_(_student_scope_subquery()))
            .first_or_404()
        )

        if transaction.is_void:
            return jsonify({'success': False, 'message': 'Transaction is already voided'}), 400

        transaction.is_void = True
        db.session.commit()

        return jsonify({'success': True, 'message': 'Transaction voided successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voiding transaction: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transaction'}), 500


@admin_bp.route('/payroll/transactions/void-bulk', methods=['POST'])
@admin_required
def void_transactions_bulk():
    """Void multiple transactions at once."""
    try:
        data = request.get_json()
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transactions selected'}), 400

        student_ids_subq = _student_scope_subquery()
        count = 0
        for tx_id in transaction_ids:
            transaction = (
                Transaction.query
                .join(Student, Transaction.student_id == Student.id)
                .filter(Transaction.id == int(tx_id))
                .filter(Student.id.in_(student_ids_subq))
                .first()
            )
            if transaction and not transaction.is_void:
                transaction.is_void = True
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'{count} transaction(s) voided successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voiding transactions in bulk: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transactions'}), 500


@admin_bp.route('/payroll/rewards/<int:reward_id>/apply', methods=['POST'])
@admin_required
def payroll_apply_reward(reward_id):
    """Apply a reward to selected students."""
    try:
        reward = PayrollReward.query.get_or_404(reward_id)
        student_ids = request.form.getlist('student_ids')

        if not student_ids:
            return jsonify({'success': False, 'message': 'Please select at least one student'}), 400

        count = 0
        for student_id in student_ids:
            student = _get_student_or_404(int(student_id))
            if student:
                transaction = Transaction(
                    student_id=student.id,
                    amount=reward.amount,
                    description=f"Reward: {reward.name}",
                    account_type='checking',
                    type='reward',
                    timestamp=datetime.utcnow()
                )
                db.session.add(transaction)
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'Reward "{reward.name}" applied to {count} student(s)!'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying reward: {e}")
        return jsonify({'success': False, 'message': 'Error applying reward'}), 500


@admin_bp.route('/payroll/fines/<int:fine_id>/apply', methods=['POST'])
@admin_required
def payroll_apply_fine(fine_id):
    """Apply a fine to selected students."""
    try:
        fine = PayrollFine.query.get_or_404(fine_id)
        student_ids = request.form.getlist('student_ids')

        if not student_ids:
            return jsonify({'success': False, 'message': 'Please select at least one student'}), 400

        count = 0
        for student_id in student_ids:
            student = _get_student_or_404(int(student_id))
            if student:
                transaction = Transaction(
                    student_id=student.id,
                    amount=-abs(fine.amount),  # Negative for fine
                    description=f"Fine: {fine.name}",
                    account_type='checking',
                    type='fine',
                    timestamp=datetime.utcnow()
                )
                db.session.add(transaction)
                count += 1

        db.session.commit()
        return jsonify({'success': True, 'message': f'Fine "{fine.name}" applied to {count} student(s)!'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying fine: {e}")
        return jsonify({'success': False, 'message': 'Error applying fine'}), 500


@admin_bp.route('/payroll/manual-payment', methods=['POST'])
@admin_required
def payroll_manual_payment():
    """Send manual payments to selected students."""
    form = ManualPaymentForm()

    if form.validate_on_submit():
        try:
            student_ids = request.form.getlist('student_ids')

            if not student_ids:
                flash('Please select at least one student.', 'warning')
                return redirect(url_for('admin.payroll'))

            description = form.description.data
            amount = form.amount.data
            account_type = form.account_type.data

            # Create transactions for each selected student
            count = 0
            for student_id in student_ids:
                student = _get_student_or_404(int(student_id))
                if student:
                    transaction = Transaction(
                        student_id=student.id,
                        amount=amount,
                        description=f"Manual Payment: {description}",
                        account_type=account_type,
                        type='manual_payment',
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(transaction)
                    count += 1

            db.session.commit()
            flash(f'Manual payment of ${amount:.2f} sent to {count} student(s)!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error sending manual payments: {e}")
            flash('Error sending manual payments. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin.payroll'))


# -------------------- ATTENDANCE --------------------

@admin_bp.route('/attendance-log')
@admin_required
def attendance_log():
    """View complete attendance log."""
    # Build student lookup for names and blocks, streaming in batches
    students = {s.id: {'name': s.full_name, 'block': s.block} for s in _scoped_students().yield_per(50)}
    # Fetch attendance events from TapEvent, streaming in batches
    raw_logs = TapEvent.query.order_by(TapEvent.timestamp.desc()).yield_per(100)
    attendance_logs = []
    for log in raw_logs:
        student_info = students.get(log.student_id, {'name': 'Unknown', 'block': 'Unknown'})
        attendance_logs.append({
            'student_id': log.student_id,
            'student_name': student_info['name'],
            'student_block': student_info['block'],
            'timestamp': log.timestamp,
            'period': log.period,
            'status': log.status,
            'reason': log.reason
        })
    return render_template(
        'admin_attendance_log.html',
        logs=attendance_logs,
        students=students,
        current_page="attendance"
    )


# -------------------- STUDENT DATA IMPORT/EXPORT --------------------

@admin_bp.route('/upload-students', methods=['POST'])
@admin_required
def upload_students():
    """
    Upload student roster from CSV file.

    Creates TeacherBlock seats (unclaimed accounts) with join codes.
    Students later claim their seat by providing the join code + credentials.
    """
    file = request.files.get('csv_file')
    if not file:
        flash("No file provided", "admin_error")
        return redirect(url_for('admin.students'))

    # Read file content and remove BOM if present
    content = file.stream.read().decode("UTF-8-sig")  # UTF-8-sig removes BOM
    stream = io.StringIO(content, newline=None)
    csv_input = csv.DictReader(stream)
    added_count = 0
    errors = 0
    duplicated = 0

    # Track join codes for each block
    from app.models import TeacherBlock
    from app.utils.join_code import generate_join_code
    teacher_id = session.get("admin_id")

    # Get or generate join codes for each block in this upload
    join_codes_by_block = {}

    for row in csv_input:
        try:
            # Handle both template column names and code-friendly names (case-insensitive)
            # Try template column names first, then fall back to lowercase versions
            first_name = (row.get('First Name') or row.get('first_name') or '').strip()
            last_name = (row.get('Last Name') or row.get('last_name') or '').strip()
            dob_str = (row.get('Date of Birth (MM/DD/YYYY)') or row.get('date_of_birth') or '').strip()
            block = (row.get('Period/Block') or row.get('block') or '').strip().upper()

            if not all([first_name, last_name, dob_str, block]):
                raise ValueError("Missing required fields.")

            # Generate last_initial
            last_initial = last_name[0].upper()

            # Get or generate join code for this teacher-block combination
            if block not in join_codes_by_block:
                # Check if this teacher already has a join code for this block
                existing_seat = TeacherBlock.query.filter_by(
                    teacher_id=teacher_id,
                    block=block
                ).first()

                if existing_seat:
                    # Reuse existing join code
                    join_codes_by_block[block] = existing_seat.join_code
                else:
                    # Generate new unique join code
                    while True:
                        new_code = generate_join_code()
                        # Ensure uniqueness across all teachers
                        if not TeacherBlock.query.filter_by(join_code=new_code).first():
                            join_codes_by_block[block] = new_code
                            break

            join_code = join_codes_by_block[block]

            # Check if this seat already exists for this teacher
            # Duplicate detection: same teacher + block + first_name + last_initial
            existing_seat = TeacherBlock.query.filter_by(
                teacher_id=teacher_id,
                block=block,
                first_name=first_name,
                last_initial=last_initial
            ).first()

            if existing_seat:
                current_app.logger.info(f"Seat for {first_name} {last_name} already exists in block {block}, skipping.")
                duplicated += 1
                continue

            # Generate dob_sum
            # Handle both mm/dd/yy and mm/dd/yyyy formats
            date_parts = dob_str.split('/')
            mm = int(date_parts[0])
            dd = int(date_parts[1])
            year = int(date_parts[2])

            # If year is 2 digits, convert to 4 digits by adding 2000
            if year < 100:
                yyyy = year + 2000
            else:
                yyyy = year

            dob_sum = mm + dd + yyyy

            # Generate salt
            salt = get_random_salt()

            # Compute first_half_hash: CONCAT(first_initial, DOB_sum)
            # Simpler credential: student just needs to know their initial and birthday
            credential = f"{last_initial}{dob_sum}"  # e.g., "S2025"
            first_half_hash = hash_hmac(credential.encode(), salt)

            # Compute last_name_hash_by_part for fuzzy matching
            from app.utils.name_utils import hash_last_name_parts
            last_name_parts = hash_last_name_parts(last_name, salt)

            # Create TeacherBlock seat (unclaimed account)
            seat = TeacherBlock(
                teacher_id=teacher_id,
                block=block,
                first_name=first_name,
                last_initial=last_initial,
                last_name_hash_by_part=last_name_parts,
                dob_sum=dob_sum,
                salt=salt,
                first_half_hash=first_half_hash,
                join_code=join_code,
                is_claimed=False,
            )
            db.session.add(seat)
            added_count += 1

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
            errors += 1

    try:
        db.session.commit()

        # Build success message with join codes
        success_msg = f"{added_count} roster seats created successfully"
        if errors > 0:
            success_msg += f"<br>{errors} rows could not be processed"
        if duplicated > 0:
            success_msg += f"<br>{duplicated} duplicate seats skipped"

        # Display join codes for each block
        if join_codes_by_block:
            success_msg += "<br><br><strong>Join Codes by Period:</strong><br>"
            for period, code in sorted(join_codes_by_block.items()):
                success_msg += f"Period {period}: <strong>{code}</strong><br>"
            success_msg += "<br>Share these codes with your students so they can claim their accounts."

        flash(success_msg, "admin_success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "admin_error")
        current_app.logger.error(f"Upload commit failed: {e}", exc_info=True)

    return redirect(url_for('admin.students'))


@admin_bp.route('/download-csv-template')
@admin_required
def download_csv_template():
    """
    Serves the updated student_upload_template.csv from the project root.
    """
    template_path = os.path.join(os.getcwd(), "student_upload_template.csv")
    return send_file(template_path, as_attachment=True, download_name="student_upload_template.csv", mimetype='text/csv')


@admin_bp.route('/export-students')
@admin_required
def export_students():
    """Export all student data to CSV."""
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'First Name', 'Last Initial', 'Block', 'Checking Balance',
        'Savings Balance', 'Total Earnings', 'Insurance Plan',
        'Rent Enabled', 'Has Completed Setup'
    ])

    # Write student data
    students = _scoped_students().order_by(Student.first_name, Student.last_initial).all()
    for student in students:
        # Get active insurance for this student
        active_insurance = StudentInsurance.query.filter_by(
            student_id=student.id,
            status='active'
        ).first()
        insurance_name = active_insurance.policy.title if active_insurance else 'None'

        writer.writerow([
            _sanitize_csv_field(student.first_name),
            _sanitize_csv_field(student.last_initial),
            _sanitize_csv_field(student.block),
            f"{student.checking_balance:.2f}",
            f"{student.savings_balance:.2f}",
            f"{student.total_earnings:.2f}",
            _sanitize_csv_field(insurance_name),
            'Yes' if student.is_rent_enabled else 'No',
            'Yes' if student.has_completed_setup else 'No'
        ])

    # Prepare response
    output.seek(0)
    filename = f"students_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# -------------------- ADMIN TAP OUT --------------------

@admin_bp.route('/enforce-daily-limits', methods=['POST'])
@admin_required
def enforce_daily_limits():
    """
    Manually trigger auto tap-out for all students who have exceeded their daily limit.
    Returns a report of students who were auto-tapped out.
    """
    from app.routes.api import check_and_auto_tapout_if_limit_reached
    import pytz
    from payroll import get_daily_limit_seconds

    students = _scoped_students().all()
    tapped_out = []
    checked = 0
    errors = []

    pacific = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)

    for student in students:
        try:
            # Get the student's current active sessions
            student_blocks = [b.strip() for b in student.block.split(',') if b.strip()]
            for block_original in student_blocks:
                period_upper = block_original.upper()
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period_upper)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                # If student is active, check their limit
                if latest_event and latest_event.status == "active":
                    checked += 1
                    daily_limit = get_daily_limit_seconds(block_original)

                    if daily_limit:
                        # Log the check for debugging
                        current_app.logger.info(
                            f"Checking student {student.id} ({student.full_name}) in period {period_upper} - limit: {daily_limit/3600:.1f}h"
                        )
                        check_and_auto_tapout_if_limit_reached(student)

                        # Check if they were tapped out (latest event changed)
                        new_latest = (
                            TapEvent.query
                            .filter_by(student_id=student.id, period=period_upper)
                            .order_by(TapEvent.timestamp.desc())
                            .first()
                        )
                        if new_latest and new_latest.status == "inactive" and new_latest.id != latest_event.id:
                            tapped_out.append(f"{student.full_name} (Period {period_upper})")
                    break  # Only check once per student
        except Exception as e:
            errors.append(f"{student.full_name}: {str(e)}")
            current_app.logger.error(f"Error enforcing limits for student {student.id}: {e}", exc_info=True)
            continue

    message = f"Checked {checked} active students. Auto-tapped out {len(tapped_out)} student(s)."

    return jsonify({
        "status": "success",
        "message": message,
        "checked": checked,
        "tapped_out": tapped_out,
        "errors": errors
    })


@admin_bp.route('/tap-out-students', methods=['POST'])
@admin_required
def tap_out_students():
    """
    Admin endpoint to tap out one or more students from a specific period.
    Supports single student, multiple students, or entire block tap-out.
    """
    data = request.get_json()

    # Get parameters
    student_ids = data.get('student_ids', [])  # List of student IDs, or 'all' for entire block
    period = data.get('period', '').strip().upper()
    reason = data.get('reason', 'Teacher tap-out')
    tap_out_all = data.get('tap_out_all', False)  # If true, tap out all active students in this period

    if not period:
        return jsonify({"status": "error", "message": "Period is required."}), 400

    if not tap_out_all and not student_ids:
        return jsonify({"status": "error", "message": "Either student_ids or tap_out_all must be provided."}), 400

    now_utc = datetime.now(timezone.utc)
    tapped_out = []
    already_inactive = []
    errors = []

    try:
        # If tap_out_all is true, get all students with this period who are currently active
        if tap_out_all:
            # Find all students in this block
            students = _scoped_students().all()
            for student in students:
                student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
                if period not in student_blocks:
                    continue

                # Check if student is currently active in this period
                latest_event = (
                    TapEvent.query
                    .filter_by(student_id=student.id, period=period)
                    .order_by(TapEvent.timestamp.desc())
                    .first()
                )

                if latest_event and latest_event.status == "active":
                    student_ids.append(student.id)

        # Process each student ID
        for student_id in student_ids:
            student = _get_student_or_404(student_id)

            if not student:
                errors.append(f"Student ID {student_id} not found")
                continue

            # Verify the student has this period in their block
            student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
            if period not in student_blocks:
                errors.append(f"{student.full_name} is not enrolled in period {period}")
                continue

            # Check if student is currently active in this period
            latest_event = (
                TapEvent.query
                .filter_by(student_id=student.id, period=period)
                .order_by(TapEvent.timestamp.desc())
                .first()
            )

            if not latest_event or latest_event.status != "active":
                already_inactive.append(student.full_name)
                continue

            # Create tap-out event
            tap_out_event = TapEvent(
                student_id=student.id,
                period=period,
                status="inactive",
                timestamp=now_utc,
                reason=reason
            )
            db.session.add(tap_out_event)
            tapped_out.append(student.full_name)

            current_app.logger.info(
                f"Admin tapped out student {student.id} ({student.full_name}) from period {period}"
            )

        # Commit all tap-outs
        db.session.commit()

        # Build response message
        message_parts = []
        if tapped_out:
            message_parts.append(f"Successfully tapped out {len(tapped_out)} student(s)")
        if already_inactive:
            message_parts.append(f"{len(already_inactive)} student(s) were already inactive")
        if errors:
            message_parts.append(f"{len(errors)} error(s) occurred")

        return jsonify({
            "status": "success",
            "message": ". ".join(message_parts),
            "tapped_out": tapped_out,
            "already_inactive": already_inactive,
            "errors": errors
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Admin tap-out failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Failed to tap out students: {str(e)}"
        }), 500


# -------------------- BANKING ROUTES --------------------

@admin_bp.route('/banking')
@admin_required
def banking():
    """Banking management page with transactions and settings."""
    # Get current banking settings
    settings = BankingSettings.query.first()

    # Create form and populate with existing data
    form = BankingSettingsForm()
    if settings:
        form.savings_apy.data = settings.savings_apy
        form.savings_monthly_rate.data = settings.savings_monthly_rate
        form.interest_calculation_type.data = settings.interest_calculation_type or 'simple'
        form.compound_frequency.data = settings.compound_frequency or 'monthly'
        form.interest_schedule_type.data = settings.interest_schedule_type
        form.interest_schedule_cycle_days.data = settings.interest_schedule_cycle_days
        form.interest_payout_start_date.data = settings.interest_payout_start_date
        form.overdraft_protection_enabled.data = settings.overdraft_protection_enabled
        form.overdraft_fee_enabled.data = settings.overdraft_fee_enabled
        form.overdraft_fee_type.data = settings.overdraft_fee_type
        form.overdraft_fee_flat_amount.data = settings.overdraft_fee_flat_amount
        form.overdraft_fee_progressive_1.data = settings.overdraft_fee_progressive_1
        form.overdraft_fee_progressive_2.data = settings.overdraft_fee_progressive_2
        form.overdraft_fee_progressive_3.data = settings.overdraft_fee_progressive_3
        form.overdraft_fee_progressive_cap.data = settings.overdraft_fee_progressive_cap

    # Get filter and pagination parameters
    student_q = request.args.get('student', '').strip()
    block_q = request.args.get('block', '')
    account_q = request.args.get('account', '')
    type_q = request.args.get('type', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = 50

    # Base query joining Transaction with Student
    query = db.session.query(Transaction, Student).join(Student, Transaction.student_id == Student.id)

    # Apply filters
    if student_q:
        # Since first_name is encrypted, we cannot use `ilike`.
        # We must fetch students, decrypt names, and filter in Python.
        matching_student_ids = []
        # Handle if the query is a student ID
        if student_q.isdigit():
            matching_student_ids.append(int(student_q))

        # Handle if the query is a name
        all_students = _scoped_students().all()
        for s in all_students:
            # The full_name property will decrypt the first_name
            if student_q.lower() in s.full_name.lower():
                matching_student_ids.append(s.id)

        # If there are any matches (by ID or name), filter the query
        if matching_student_ids:
            query = query.filter(Student.id.in_(matching_student_ids))
        else:
            # If no students match, return no results
            query = query.filter(sa.false())

    if block_q:
        query = query.filter(Student.block == block_q)
    if account_q:
        query = query.filter(Transaction.account_type == account_q)
    if type_q:
        query = query.filter(Transaction.type == type_q)
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Transaction.timestamp >= start_date_obj)
        except ValueError:
            flash("Invalid start date format. Please use YYYY-MM-DD.", "danger")
    if end_date:
        # P1-1 Fix: Prevent SQL injection by validating and parsing date in Python
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            # Add one day to include entire end_date (safe in Python, not SQL)
            end_date_inclusive = end_date_obj + timedelta(days=1)
            query = query.filter(Transaction.timestamp < end_date_inclusive)
        except ValueError:
            flash("Invalid end date format. Please use YYYY-MM-DD.", "danger")

    # Count total for pagination
    total_transactions = query.count()
    total_pages = math.ceil(total_transactions / per_page) if total_transactions else 1

    # Get paginated results
    recent_transactions = (
        query.order_by(Transaction.timestamp.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )

    # Build transaction list for template
    transactions = []
    for tx, student in recent_transactions:
        transactions.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'student_id': student.id,
            'student_name': student.full_name,
            'student_block': student.block,
            'amount': tx.amount,
            'account_type': tx.account_type,
            'description': tx.description,
            'type': tx.type,
            'is_void': tx.is_void
        })

    # Get all students for stats
    students = _scoped_students().all()

    # Calculate banking stats
    total_checking = sum(s.checking_balance for s in students)
    total_savings = sum(s.savings_balance for s in students)
    total_deposits = sum(s.checking_balance + s.savings_balance for s in students)

    # Count students with savings
    students_with_savings = sum(1 for s in students if s.savings_balance > 0)

    # Calculate average savings balance (across all students, including those with 0)
    average_savings_balance = total_savings / len(students) if len(students) > 0 else 0

    # Get all blocks for filter
    blocks = sorted(set(s.block for s in students))

    # Get transaction types for filter
    transaction_types = db.session.query(Transaction.type).distinct().filter(Transaction.type.isnot(None)).all()
    transaction_types = sorted([t[0] for t in transaction_types if t[0]])


    return render_template(
        'admin_banking.html',
        settings=settings,
        form=form,
        transactions=transactions,
        total_checking=total_checking,
        total_savings=total_savings,
        total_deposits=total_deposits,
        students_with_savings=students_with_savings,
        total_students=len(students),
        average_savings_balance=average_savings_balance,
        blocks=blocks,
        transaction_types=transaction_types,
        page=page,
        total_pages=total_pages,
        total_transactions=total_transactions,
        current_page="banking",
        format_utc_iso=format_utc_iso
    )


@admin_bp.route('/banking/settings', methods=['POST'])
@admin_required
def banking_settings_update():
    """Update banking settings."""
    form = BankingSettingsForm()

    if form.validate_on_submit():
        # Get or create settings
        settings = BankingSettings.query.first()
        if not settings:
            settings = BankingSettings()
            db.session.add(settings)

        # Update settings from form
        settings.savings_apy = form.savings_apy.data or 0.0
        settings.savings_monthly_rate = form.savings_monthly_rate.data or 0.0
        settings.interest_calculation_type = form.interest_calculation_type.data or 'simple'
        settings.compound_frequency = form.compound_frequency.data or 'monthly'
        settings.interest_schedule_type = form.interest_schedule_type.data
        settings.interest_schedule_cycle_days = form.interest_schedule_cycle_days.data or 30
        settings.interest_payout_start_date = form.interest_payout_start_date.data
        settings.overdraft_protection_enabled = form.overdraft_protection_enabled.data
        settings.overdraft_fee_enabled = form.overdraft_fee_enabled.data
        settings.overdraft_fee_type = form.overdraft_fee_type.data
        settings.overdraft_fee_flat_amount = form.overdraft_fee_flat_amount.data or 0.0
        settings.overdraft_fee_progressive_1 = form.overdraft_fee_progressive_1.data or 0.0
        settings.overdraft_fee_progressive_2 = form.overdraft_fee_progressive_2.data or 0.0
        settings.overdraft_fee_progressive_3 = form.overdraft_fee_progressive_3.data or 0.0
        settings.overdraft_fee_progressive_cap = form.overdraft_fee_progressive_cap.data
        settings.updated_at = datetime.utcnow()

        try:
            db.session.commit()
            flash('Banking settings updated successfully!', 'success')
            current_app.logger.info(f"Banking settings updated by admin")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to update banking settings: {e}", exc_info=True)
            flash('Error updating banking settings.', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')

    return redirect(url_for('admin.banking'))


# -------------------- DELETION REQUESTS --------------------

@admin_bp.route('/deletion-requests', methods=['GET', 'POST'])
@admin_required
def deletion_requests():
    """
    View and create deletion requests for periods/blocks or account.

    Teachers can request:
    1. Deletion of a specific period/block
    2. Deletion of their entire account

    System admins approve these requests to perform deletions.
    """
    admin_id = session.get('admin_id')

    if request.method == 'POST':
        request_type = request.form.get('request_type')  # 'period' or 'account'
        period = request.form.get('period') if request_type == 'period' else None
        reason = request.form.get('reason', '').strip()

        # Validate
        if request_type not in ['period', 'account']:
            flash('Invalid request type.', 'error')
            return redirect(url_for('admin.deletion_requests'))

        if request_type == 'period':
            if not period:
                flash('Period/block is required for period deletion requests.', 'error')
                return redirect(url_for('admin.deletion_requests'))
            # Validate period format and length
            # Allow spaces, hyphens, underscores since periods may be named like "Period 1A" or "Block-2"
            if not PERIOD_PATTERN.match(period) or len(period) > PERIOD_MAX_LENGTH:
                flash(f'Invalid period format. Use alphanumeric characters, spaces, hyphens, and underscores only. Max {PERIOD_MAX_LENGTH} characters.', 'error')
                return redirect(url_for('admin.deletion_requests'))

        # Check for duplicate pending requests
        # Convert string to enum (will raise ValueError if invalid)
        request_type_enum = DeletionRequestType.from_string(request_type)
        existing = DeletionRequest.query.filter_by(
            admin_id=admin_id,
            request_type=request_type_enum,
            period=period,
            status=DeletionRequestStatus.PENDING
        ).first()

        if existing:
            flash(
                f'You already have a pending {request_type} deletion request'
                + (f' for period {period}.' if period else '.'),
                'warning'
            )
            return redirect(url_for('admin.deletion_requests'))

        # Create the deletion request
        deletion_request = DeletionRequest(
            admin_id=admin_id,
            request_type=request_type_enum,
            period=period,
            reason=reason
        )
        db.session.add(deletion_request)

        try:
            db.session.commit()
            flash(
                f'✅ Deletion request submitted successfully. '
                f'A system administrator will review your {request_type} deletion request.',
                'success'
            )
            current_app.logger.info(
                f"Admin {admin_id} submitted {request_type} deletion request"
                + (f" for period {period}" if period else "")
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Error creating deletion request: {e}")
            flash('Error submitting deletion request.', 'error')

        return redirect(url_for('admin.deletion_requests'))

    # GET: Display existing deletion requests
    pending_requests = DeletionRequest.query.filter_by(
        admin_id=admin_id,
        status=DeletionRequestStatus.PENDING
    ).order_by(DeletionRequest.requested_at.desc()).all()

    resolved_requests = DeletionRequest.query.filter_by(
        admin_id=admin_id
    ).filter(
        DeletionRequest.status.in_([DeletionRequestStatus.APPROVED, DeletionRequestStatus.REJECTED])
    ).order_by(DeletionRequest.resolved_at.desc()).limit(10).all()

    # Get teacher's periods for the dropdown (from both student_teachers and legacy teacher_id)
    periods_via_link = db.session.query(Student.block).join(
        StudentTeacher, Student.id == StudentTeacher.student_id
    ).filter(StudentTeacher.admin_id == admin_id).distinct()

    # Get periods from legacy teacher_id
    periods_via_legacy = db.session.query(Student.block).filter(
        Student.teacher_id == admin_id
    ).distinct()

    # Union both queries
    periods = periods_via_link.union(periods_via_legacy).all()
    periods = [p[0] for p in periods]

    return render_template(
        'admin_deletion_requests.html',
        pending_requests=pending_requests,
        resolved_requests=resolved_requests,
        periods=periods
    )
