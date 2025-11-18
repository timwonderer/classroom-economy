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
import qrcode
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, session,
    jsonify, Response, send_file, current_app
)
from sqlalchemy import desc, text, or_, func
from sqlalchemy.exc import SQLAlchemyError
import sqlalchemy as sa
import pyotp
import pytz

from app.extensions import db
from app.models import (
    Student, Admin, AdminInviteCode, Transaction, TapEvent, StoreItem, StudentItem,
    RentSettings, RentPayment, InsurancePolicy, StudentInsurance, InsuranceClaim,
    HallPassLog, PayrollSettings, PayrollReward, PayrollFine
)
from app.auth import admin_required
from forms import (
    AdminLoginForm, AdminSignupForm, AdminTOTPConfirmForm, StoreItemForm,
    InsurancePolicyForm, AdminClaimProcessForm, PayrollSettingsForm,
    PayrollRewardForm, PayrollFineForm, ManualPaymentForm
)

# Import utility functions
from app import is_safe_url, format_utc_iso
from hash_utils import get_random_salt, hash_hmac
from payroll import calculate_payroll
from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds

# Timezone
PACIFIC = pytz.timezone('America/Los_Angeles')

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# -------------------- DASHBOARD & QUICK ACTIONS --------------------

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with statistics, pending actions, and recent activity."""
    # Get all students for calculations
    students = Student.query.order_by(Student.first_name).all()
    student_lookup = {s.id: s for s in students}

    # Quick Stats
    total_students = len(students)
    total_balance = sum(s.checking_balance + s.savings_balance for s in students)
    avg_balance = total_balance / total_students if total_students > 0 else 0

    # Pending actions - count all types of pending approvals
    pending_redemptions_count = StudentItem.query.filter_by(status='processing').count()
    pending_hall_passes_count = HallPassLog.query.filter_by(status='pending').count()
    pending_insurance_claims_count = InsuranceClaim.query.filter_by(status='pending').count()
    total_pending_actions = pending_redemptions_count + pending_hall_passes_count + pending_insurance_claims_count

    # Get recent items for each pending type (limited for display)
    recent_redemptions = StudentItem.query.filter_by(status='processing').order_by(StudentItem.redemption_date.desc()).limit(5).all()
    recent_hall_passes = HallPassLog.query.filter_by(status='pending').order_by(HallPassLog.request_time.desc()).limit(5).all()
    recent_insurance_claims = InsuranceClaim.query.filter_by(status='pending').order_by(InsuranceClaim.filed_date.desc()).limit(5).all()

    # Recent transactions (limited to 5 for display)
    recent_transactions = Transaction.query.filter_by(is_void=False).order_by(Transaction.timestamp.desc()).limit(5).all()
    total_transactions_today = Transaction.query.filter(
        Transaction.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
        Transaction.is_void == False
    ).count()

    # Recent attendance logs (limited to 5 for display)
    raw_logs = (
        db.session.query(
            TapEvent,
            Student.first_name,
            Student.last_initial
        )
        .join(Student, TapEvent.student_id == Student.id)
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

    pacific = pytz.timezone('America/Los_Angeles')
    if last_payroll_time:
        next_pay_date_utc = last_payroll_time + timedelta(days=14)
    else:
        now_utc = datetime.now(timezone.utc)
        days_until_friday = (4 - now_utc.weekday() + 7) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_pay_date_utc = now_utc + timedelta(days=days_until_friday)
    next_payroll_date = next_pay_date_utc.astimezone(pacific)

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
    students = Student.query.yield_per(50)
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
    flash("Logged out.")
    return redirect(url_for("admin.login"))


# -------------------- STUDENT MANAGEMENT --------------------

@admin_bp.route('/students')
@admin_required
def students():
    """View all students with basic information."""
    students = Student.query.order_by(Student.block, Student.first_name).all()
    # Remove deprecated last_tap_in/last_tap_out logic; templates should not reference them.
    return render_template('admin_students.html', students=students, current_page="students")


@admin_bp.route('/students/<int:student_id>')
@admin_required
def student_detail(student_id):
    """View detailed information for a specific student."""
    student = Student.query.get_or_404(student_id)
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
    return render_template('student_detail.html', student=student, transactions=transactions, student_items=student_items, latest_tap_event=latest_tap_event)


@admin_bp.route('/student/<int:student_id>/set-hall-passes', methods=['POST'])
@admin_required
def set_hall_passes(student_id):
    """Set hall pass balance for a student."""
    student = Student.query.get_or_404(student_id)
    new_balance = request.form.get('hall_passes', type=int)

    if new_balance is not None and new_balance >= 0:
        student.hall_passes = new_balance
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s hall pass balance to {new_balance}.", "success")
    else:
        flash("Invalid hall pass balance provided.", "error")

    return redirect(url_for('admin.student_detail', student_id=student_id))


# -------------------- STORE MANAGEMENT --------------------

@admin_bp.route('/store', methods=['GET', 'POST'])
@admin_required
def store_management():
    """Manage store items - view, create, edit, delete."""
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
            is_active=form.is_active.data
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"'{new_item.name}' has been added to the store.", "success")
        return redirect(url_for('admin.store_management'))

    items = StoreItem.query.order_by(StoreItem.name).all()
    return render_template('admin_store.html', form=form, items=items, current_page="store")


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


# -------------------- RENT SETTINGS --------------------

@admin_bp.route('/rent-settings', methods=['GET', 'POST'])
@admin_required
def rent_settings():
    """Configure rent settings."""
    # Get or create rent settings (singleton)
    settings = RentSettings.query.first()
    if not settings:
        settings = RentSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.rent_amount = float(request.form.get('rent_amount'))
        settings.due_day_of_month = int(request.form.get('due_day_of_month'))
        settings.late_fee = float(request.form.get('late_fee'))
        settings.grace_period_days = int(request.form.get('grace_period_days'))
        settings.is_enabled = request.form.get('is_enabled') == 'on'

        db.session.commit()
        flash("Rent settings updated successfully!", "success")
        return redirect(url_for('admin.rent_settings'))

    # Get statistics
    total_students = Student.query.filter_by(is_rent_enabled=True).count()
    current_month = datetime.now().month
    current_year = datetime.now().year
    paid_this_month = RentPayment.query.filter_by(
        period_month=current_month,
        period_year=current_year
    ).count()

    return render_template('admin_rent_settings.html',
                          settings=settings,
                          total_students=total_students,
                          paid_this_month=paid_this_month)


# -------------------- INSURANCE MANAGEMENT --------------------

@admin_bp.route('/insurance', methods=['GET', 'POST'])
@admin_required
def insurance_management():
    """Main insurance management dashboard."""
    form = InsurancePolicyForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Create new insurance policy
        policy = InsurancePolicy(
            title=form.title.data,
            description=form.description.data,
            premium=form.premium.data,
            charge_frequency=form.charge_frequency.data,
            autopay=form.autopay.data,
            waiting_period_days=form.waiting_period_days.data,
            max_claims_count=form.max_claims_count.data,
            max_claims_period=form.max_claims_period.data,
            max_claim_amount=form.max_claim_amount.data,
            is_monetary=form.is_monetary.data,
            no_repurchase_after_cancel=form.no_repurchase_after_cancel.data,
            repurchase_wait_days=form.repurchase_wait_days.data,
            auto_cancel_nonpay_days=form.auto_cancel_nonpay_days.data,
            claim_time_limit_days=form.claim_time_limit_days.data,
            bundle_discount_percent=form.bundle_discount_percent.data,
            is_active=form.is_active.data
        )
        db.session.add(policy)
        db.session.commit()
        flash(f"Insurance policy '{policy.title}' created successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get all policies
    policies = InsurancePolicy.query.all()

    # Get all student enrollments
    active_enrollments = StudentInsurance.query.filter_by(status='active').all()
    cancelled_enrollments = StudentInsurance.query.filter_by(status='cancelled').all()

    # Get all claims
    claims = InsuranceClaim.query.order_by(InsuranceClaim.filed_date.desc()).all()
    pending_claims_count = InsuranceClaim.query.filter_by(status='pending').count()

    return render_template('admin_insurance.html',
                          form=form,
                          policies=policies,
                          active_enrollments=active_enrollments,
                          cancelled_enrollments=cancelled_enrollments,
                          claims=claims,
                          pending_claims_count=pending_claims_count)


@admin_bp.route('/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def edit_insurance_policy(policy_id):
    """Edit existing insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)
    form = InsurancePolicyForm(obj=policy)

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
        policy.is_monetary = form.is_monetary.data
        policy.no_repurchase_after_cancel = form.no_repurchase_after_cancel.data
        policy.enable_repurchase_cooldown = form.enable_repurchase_cooldown.data
        policy.repurchase_wait_days = form.repurchase_wait_days.data
        policy.auto_cancel_nonpay_days = form.auto_cancel_nonpay_days.data
        policy.claim_time_limit_days = form.claim_time_limit_days.data
        policy.bundle_with_policy_ids = form.bundle_with_policy_ids.data
        policy.bundle_discount_percent = form.bundle_discount_percent.data
        policy.bundle_discount_amount = form.bundle_discount_amount.data
        policy.is_active = form.is_active.data

        db.session.commit()
        flash(f"Insurance policy '{policy.title}' updated successfully!", "success")
        return redirect(url_for('admin.insurance_management'))

    # Get other active policies for bundle selection (excluding current policy)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.id != policy_id
    ).all()

    return render_template('admin_edit_insurance_policy.html', form=form, policy=policy, available_policies=available_policies)


@admin_bp.route('/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
def deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy."""
    policy = InsurancePolicy.query.get_or_404(policy_id)
    policy.is_active = False
    db.session.commit()
    flash(f"Insurance policy '{policy.title}' has been deactivated.", "success")
    return redirect(url_for('admin.insurance_management'))


@admin_bp.route('/insurance/student-policy/<int:enrollment_id>')
@admin_required
def view_student_policy(enrollment_id):
    """View student's policy enrollment details and claims history."""
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

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
    claim = InsuranceClaim.query.get_or_404(claim_id)
    form = AdminClaimProcessForm(obj=claim)

    # Get enrollment details
    enrollment = StudentInsurance.query.get(claim.student_insurance_id)

    # Validate claim
    validation_errors = []

    # Check if coverage has started (past waiting period)
    if not enrollment.coverage_start_date or enrollment.coverage_start_date > datetime.utcnow():
        validation_errors.append("Coverage has not started yet (still in waiting period)")

    # Check if payment is current
    if not enrollment.payment_current:
        validation_errors.append("Premium payments are not current")

    # Check claim time limit
    days_since_incident = (datetime.utcnow() - claim.incident_date).days
    if days_since_incident > claim.policy.claim_time_limit_days:
        validation_errors.append(f"Claim filed too late ({days_since_incident} days after incident, limit is {claim.policy.claim_time_limit_days} days)")

    # Check max claims count
    if claim.policy.max_claims_count:
        # Count approved/paid claims in current period
        # Simplified: count all approved/paid claims for this enrollment
        approved_claims = InsuranceClaim.query.filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid'])
        ).count()
        if approved_claims >= claim.policy.max_claims_count:
            validation_errors.append(f"Maximum claims limit reached ({claim.policy.max_claims_count} per {claim.policy.max_claims_period})")

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

        claim.status = new_status
        claim.admin_notes = form.admin_notes.data
        claim.rejection_reason = form.rejection_reason.data if new_status == 'rejected' else None
        claim.processed_date = datetime.utcnow()
        claim.processed_by_admin_id = session.get('admin_id')

        # Handle monetary claims - auto-deposit when approved
        if claim.policy.is_monetary and new_status == 'approved' and old_status != 'approved':
            # Use approved amount or requested amount
            deposit_amount = form.approved_amount.data if form.approved_amount.data else claim.claim_amount
            claim.approved_amount = deposit_amount

            # Auto-deposit to student's checking account via transaction
            student = claim.student

            # Create transaction record
            transaction = Transaction(
                student_id=student.id,
                amount=deposit_amount,
                account_type='checking',
                type='insurance_claim',
                description=f"Insurance claim approved: {claim.policy.title}"
            )
            db.session.add(transaction)

            flash(f"Monetary claim approved! ${deposit_amount:.2f} deposited to {student.full_name}'s checking account.", "success")
        elif not claim.policy.is_monetary and new_status == 'approved':
            # Non-monetary claim - just mark as approved
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
                          claims_stats=claims_stats)


# -------------------- TRANSACTIONS --------------------

@admin_bp.route('/transactions')
@admin_required
def transactions():
    """View and filter all transactions."""
    # Read filter and pagination parameters
    student_q = request.args.get('student', '').strip()
    block_q = request.args.get('block', '')
    type_q = request.args.get('type', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = int(request.args.get('page', 1))
    per_page = 20

    # Base query joining Transaction with Student
    query = db.session.query(
        Transaction,
        Student.first_name.label('student_name'),
        Student.block.label('student_block')
    ).join(Student, Transaction.student_id == Student.id)

    # Apply filters
    if student_q:
        # Since first_name is encrypted, we cannot use `ilike`.
        # We must fetch students, decrypt names, and filter in Python.
        matching_student_ids = []
        # Handle if the query is a student ID
        if student_q.isdigit():
            matching_student_ids.append(int(student_q))

        # Handle if the query is a name
        all_students = Student.query.all()
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
    if type_q:
        query = query.filter(Transaction.type == type_q)
    if start_date:
        query = query.filter(Transaction.timestamp >= start_date)
    if end_date:
        # include entire end_date
        query = query.filter(Transaction.timestamp < text(f"'{end_date}'::date + interval '1 day'"))

    # Count and paginate
    total = query.count()
    total_pages = math.ceil(total / per_page) if total else 1

    raw = query.order_by(Transaction.timestamp.desc()) \
               .limit(per_page).offset((page - 1) * per_page).all()

    # Build list of dicts for template
    transactions = []
    for tx, name, block in raw:
        transactions.append({
            'id': tx.id,
            'timestamp': tx.timestamp,
            'student_name': name,
            'student_block': block,
            'type': tx.type,
            'amount': tx.amount,
            'reason': tx.description,
            'is_void': tx.is_void
        })

    return render_template(
        'admin_transactions.html',
        transactions=transactions,
        page=page,
        total_pages=total_pages,
        current_page="transactions"
    )


@admin_bp.route('/void-transaction/<int:transaction_id>', methods=['POST'])
@admin_required
def void_transaction(transaction_id):
    """Void a transaction."""
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    tx = Transaction.query.get_or_404(transaction_id)
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
    pending_requests = HallPassLog.query.filter_by(status='pending').order_by(HallPassLog.request_time.asc()).all()
    approved_queue = HallPassLog.query.filter_by(status='approved').order_by(HallPassLog.decision_time.asc()).all()
    out_of_class = HallPassLog.query.filter_by(status='left').order_by(HallPassLog.left_time.asc()).all()

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

    block = request.args.get("block")
    current_app.logger.info(f"📊 Block filter: {block}")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    current_app.logger.info(f"📅 Date filters: start={start_date_str}, end={end_date_str}")

    query = Transaction.query.filter_by(type="payroll")

    if block:
        # Stream students in batches for this block
        student_ids = [s.id for s in Student.query.filter_by(block=block).yield_per(50).all()]
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
    student_lookup = {s.id: s for s in Student.query.yield_per(50)}
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

        students = Student.query.all()
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

    # Get all students
    students = Student.query.all()

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
    recent_payrolls = Transaction.query.filter_by(type='payroll').order_by(Transaction.timestamp.desc()).limit(20).all()

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
    payroll_history_transactions = Transaction.query.filter(
        Transaction.type.in_(['payroll', 'reward', 'fine', 'manual_payment'])
    ).order_by(Transaction.timestamp.desc()).limit(100).all()
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
        students = Student.query.all()
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
        transaction = Transaction.query.get_or_404(transaction_id)

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

        count = 0
        for tx_id in transaction_ids:
            transaction = Transaction.query.get(int(tx_id))
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
            student = Student.query.get(int(student_id))
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
            student = Student.query.get(int(student_id))
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
                student = Student.query.get(int(student_id))
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
    students = {s.id: {'name': s.full_name, 'block': s.block} for s in Student.query.yield_per(50)}
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
    """Upload students from CSV file."""
    file = request.files.get('csv_file')
    if not file:
        flash("No file provided", "admin_error")
        return redirect(url_for('admin.students'))

    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.DictReader(stream)
    added_count = 0
    errors = 0
    duplicated = 0

    for row in csv_input:
        try:
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            dob_str = row.get('date_of_birth', '').strip()
            block = row.get('block', '').strip().upper()

            if not all([first_name, last_name, dob_str, block]):
                raise ValueError("Missing required fields.")

            # Generate last_initial
            last_initial = last_name[0].upper()

            # Efficiently check for duplicates.
            # 1. Filter by unencrypted fields (`last_initial`, `block`) to get a small candidate pool.
            potential_matches = Student.query.filter_by(last_initial=last_initial, block=block).all()

            # 2. Iterate through the small pool and compare the decrypted first name.
            is_duplicate = False
            for student in potential_matches:
                if student.first_name == first_name:
                    is_duplicate = True
                    break

            if is_duplicate:
                current_app.logger.info(f"Duplicate detected: {first_name} {last_initial} in block {block}, skipping.")
                duplicated += 1
                continue  # skip this duplicate

            # Generate name_code (vowels from first_name + consonants from last_name)
            vowels = re.findall(r'[AEIOUaeiou]', first_name)
            consonants = re.findall(r'[^AEIOUaeiou\W\d_]', last_name)
            name_code = ''.join(vowels + consonants).lower()

            # Generate dob_sum
            mm, dd, yyyy = map(int, dob_str.split('/'))
            dob_sum = mm + dd + yyyy

            # Generate salt
            salt = get_random_salt()

            # Compute first_half_hash and second_half_hash using HMAC
            first_half_hash = hash_hmac(name_code.encode(), salt)
            second_half_hash = hash_hmac(str(dob_sum).encode(), salt)

            student = Student(
                first_name=first_name,
                last_initial=last_initial,
                block=block,
                salt=salt,
                first_half_hash=first_half_hash,
                second_half_hash=second_half_hash,
                dob_sum=dob_sum,
                has_completed_setup=False
            )
            db.session.add(student)
            added_count += 1

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
            errors += 1

    try:
        db.session.commit()
        flash(f"{added_count} students added successfully<br>{errors} students cannot be added<br>{duplicated} duplicated students skipped.", "admin_success")
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
    students = Student.query.order_by(Student.first_name, Student.last_initial).all()
    for student in students:
        writer.writerow([
            student.first_name,
            student.last_initial,
            student.block,
            f"{student.checking_balance:.2f}",
            f"{student.savings_balance:.2f}",
            f"{student.total_earnings:.2f}",
            student.insurance_plan if student.insurance_plan != 'none' else 'None',
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
