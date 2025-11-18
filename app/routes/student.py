"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import re
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, current_app
from sqlalchemy import or_, func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash, check_password_hash
import pytz

from app.extensions import db
from app.models import (
    Student, Transaction, TapEvent, StoreItem, StudentItem,
    RentSettings, RentPayment, InsurancePolicy, StudentInsurance, InsuranceClaim
)
from app.auth import login_required, get_logged_in_student, SESSION_TIMEOUT_MINUTES
from forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, InsuranceClaimForm
)

# Import utility functions
from app import is_safe_url
from hash_utils import hash_hmac, hash_username
from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds

# Theme prompts for username generation
THEME_PROMPTS = [
    {"slug": "animal", "prompt": "Write in your favorite animal."},
    {"slug": "color", "prompt": "Write in your favorite color."},
    {"slug": "space", "prompt": "Write in something related to outer space."},
    {"slug": "nature", "prompt": "Write in a nature word (tree, river, etc.)."},
    {"slug": "food", "prompt": "Write in your favorite fruit or food."},
    {"slug": "trait", "prompt": "Write in a positive character trait (bravery, kindness, etc.)."},
    {"slug": "place", "prompt": "Write in a place you want to visit."},
    {"slug": "science", "prompt": "Write in a science word you like."},
    {"slug": "hobby", "prompt": "Write in your favorite hobby or sport."},
    {"slug": "happy", "prompt": "Write in something that makes you happy."},
]

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')


# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
def claim_account():
    """PAGE 1: Claim Account - Verify identity to begin setup."""
    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        first_half = form.first_half.data.strip().lower()
        second_half = form.second_half.data.strip()

        if not second_half.isdigit():
            flash("DOB sum must be a number.", "claim")
            return redirect(url_for('student.claim_account'))

        for s in Student.query.filter_by(has_completed_setup=False).all():
            name_code = first_half

            if (
                s.first_half_hash == hash_hmac(name_code.encode(), s.salt)
                and s.second_half_hash == hash_hmac(second_half.encode(), s.salt)
                and str(s.dob_sum) == second_half
            ):
                session['claimed_student_id'] = s.id
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)

                return redirect(url_for('student.create_username'))

        flash("No matching account found. Please check your info.", "claim")
        return redirect(url_for('student.claim_account'))

    return render_template('student_account_claim.html', form=form)


@student_bp.route('/create-username', methods=['GET', 'POST'])
def create_username():
    """PAGE 2: Create Username - Generate themed username."""
    # Only allow if claimed
    student_id = session.get('claimed_student_id')
    if not student_id:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student.claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    # Assign a random theme prompt if not yet in session
    if 'theme_prompt' not in session:
        selected_theme = random.choice(THEME_PROMPTS)
        session['theme_slug'] = selected_theme['slug']
        session['theme_prompt'] = selected_theme['prompt']
    form = StudentCreateUsernameForm()
    if form.validate_on_submit():
        write_in_word = form.write_in_word.data.strip().lower()
        if not write_in_word.isalpha() or len(write_in_word) < 3 or len(write_in_word) > 12:
            flash("Please enter a valid word (3-12 letters, no numbers or spaces).", "setup")
            return redirect(url_for('student.create_username'))
        adjectives = [
            "brave", "clever", "curious", "daring", "eager", "fancy", "gentle", "honest", "jolly", "kind",
            "lucky", "mighty", "noble", "quick", "proud", "silly", "witty", "zesty", "sunny", "chill"
        ]
        adjective = random.choice(adjectives)
        dob_sum = student.dob_sum if student.dob_sum is not None else 0
        initials = f"{student.first_name[0].upper()}{student.last_initial.upper()}"
        username = f"{adjective}{write_in_word}{dob_sum}{initials}"
        # Save username plaintext in session for display
        session['generated_username'] = username
        # Hash and store in DB
        student.username_hash = hash_username(username, student.salt)
        db.session.commit()
        # Clear theme prompt from session
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)
        return redirect(url_for('student.setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)


@student_bp.route('/setup-pin-passphrase', methods=['GET', 'POST'])
def setup_pin_passphrase():
    """PAGE 3: Setup PIN & Passphrase - Secure the account."""
    # Only allow if claimed and username generated
    student_id = session.get('claimed_student_id')
    username = session.get('generated_username')
    if not student_id or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student.claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student.login'))
    form = StudentPinPassphraseForm()
    if form.validate_on_submit():
        pin = form.pin.data
        passphrase = form.passphrase.data
        if not pin or not passphrase:
            flash("PIN and passphrase are required.", "setup")
            return redirect(url_for('student.setup_pin_passphrase'))
        # Save credentials (store passphrase as hash)
        student.pin_hash = generate_password_hash(pin)
        student.passphrase_hash = generate_password_hash(passphrase)
        student.has_completed_setup = True
        db.session.commit()
        # Clear session onboarding keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('setup_complete'))
    return render_template('student_pin_setup.html', username=username, form=form)


# -------------------- STUDENT DASHBOARD --------------------

@student_bp.route('/dashboard')
@login_required
def dashboard():
    """Student dashboard with balance, attendance, transactions, and quick actions."""
    student = get_logged_in_student()
    apply_savings_interest(student)  # Apply savings interest if not already applied
    transactions = Transaction.query.filter_by(student_id=student.id).order_by(Transaction.timestamp.desc()).all()
    student_items = student.items.filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing'])
    ).order_by(StudentItem.purchase_date.desc()).all()

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    forecast_interest = round(student.savings_balance * (0.045 / 12), 2)

    # --- Refactored logic to use unpaid seconds since last payroll ---
    last_payroll_time = get_last_payroll_time()
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]

    unpaid_seconds_per_block = {
        blk: calculate_unpaid_attendance_seconds(student.id, blk, last_payroll_time)
        for blk in student_blocks
    }

    # Simplified status logic, removing dependency on get_session_status
    period_states = {}
    for blk in student_blocks:
        latest_event = TapEvent.query.filter_by(student_id=student.id, period=blk).order_by(TapEvent.timestamp.desc()).first()
        is_active = latest_event.status == 'active' if latest_event else False

        # Correctly check if the student has finished for *today* by looking for
        # any tap-out event with a reason on the current date.
        today = datetime.now(timezone.utc).date()
        is_done = db.session.query(TapEvent.id).filter(
            TapEvent.student_id == student.id,
            TapEvent.period == blk,
            func.date(TapEvent.timestamp) == today,
            TapEvent.reason.isnot(None)
        ).first() is not None

        period_states[blk] = {
            "active": is_active,
            "done": is_done,
            "duration": unpaid_seconds_per_block.get(blk, 0)  # Use the correct unpaid seconds
        }

    period_states_json = json.dumps(period_states, separators=(',', ':'))

    # Calculate projected pay based on unpaid seconds
    RATE_PER_SECOND = 0.25 / 60
    projected_pay_per_block = {
        blk: unpaid_seconds_per_block.get(blk, 0) * RATE_PER_SECOND
        for blk in student_blocks
    }

    # Compute total unpaid seconds and format as HH:MM:SS for display
    total_unpaid_seconds = sum(unpaid_seconds_per_block.values())
    hours, remainder = divmod(total_unpaid_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    total_unpaid_elapsed = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    student_name = student.full_name

    # Compute most recent deposit and insurance paid flag
    recent_deposit = student.recent_deposits[0] if student.recent_deposits else None

    # Track seen deposits in session to show notification only once
    if 'seen_deposit_ids' not in session:
        session['seen_deposit_ids'] = []

    # Only show deposit if it hasn't been seen yet
    if recent_deposit and recent_deposit.id not in session['seen_deposit_ids']:
        # Mark as seen
        session['seen_deposit_ids'].append(recent_deposit.id)
        session.modified = True
        # Keep only last 10 seen deposit IDs to prevent session bloat
        session['seen_deposit_ids'] = session['seen_deposit_ids'][-10:]
    else:
        # Don't show if already seen
        recent_deposit = None

    insurance_paid = bool(student.insurance_last_paid)

    tz = pytz.timezone('America/Los_Angeles')
    local_now = datetime.now(tz)
    # --- DASHBOARD DEBUG LOGGING ---
    current_app.logger.info(f"📊 DASHBOARD DEBUG: Student {student.id} - Block states:")
    for blk in student_blocks:
        blk_state = period_states[blk]
        active = blk_state["active"]
        done = blk_state["done"]
        seconds = blk_state["duration"]
        current_app.logger.info(f"Block {blk} => DB Active={active}, Done={done}, Seconds (today)={seconds}, Total Unpaid Seconds={unpaid_seconds_per_block.get(blk, 0)}")


    # --- Calculate remaining session time for frontend timer ---
    login_time = datetime.fromisoformat(session['login_time'])
    expiry_time = login_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    session_remaining_seconds = max(0, int((expiry_time - datetime.now(timezone.utc)).total_seconds()))


    return render_template(
        'student_dashboard.html',
        student=student,
        session_remaining_seconds=session_remaining_seconds,
        student_blocks=student_blocks,
        period_states=period_states,
        period_states_json=period_states_json,
        checking_transactions=checking_transactions,
        savings_transactions=savings_transactions,
        student_items=student_items,
        now=local_now,
        forecast_interest=forecast_interest,
        recent_deposit=recent_deposit,
        insurance_paid=insurance_paid,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        student_name=student_name,
        total_unpaid_elapsed=total_unpaid_elapsed,
    )


# -------------------- FINANCIAL TRANSACTIONS --------------------

@student_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """Transfer funds between checking and savings accounts."""
    student = get_logged_in_student()

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        passphrase = request.form.get("passphrase")
        if not check_password_hash(student.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student.transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        amount = float(request.form.get('amount'))

        if from_account == to_account:
            if is_json:
                return jsonify(status="error", message="Cannot transfer to the same account."), 400
            flash("Cannot transfer to the same account.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif amount <= 0:
            if is_json:
                return jsonify(status="error", message="Amount must be greater than 0."), 400
            flash("Amount must be greater than 0.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'checking' and amount > student.checking_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient checking funds."), 400
            flash("Insufficient checking funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        elif from_account == 'savings' and amount > student.savings_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient savings funds."), 400
            flash("Insufficient savings funds.", "transfer_error")
            return redirect(url_for("student.transfer"))
        else:
            # Record the withdrawal side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                amount=-amount,
                account_type=from_account,
                type='Withdrawal',
                description=f'Transfer to {to_account}'
            ))
            # Record the deposit side of the transfer
            db.session.add(Transaction(
                student_id=student.id,
                amount=amount,
                account_type=to_account,
                type='Deposit',
                description=f'Transfer from {from_account}'
            ))
            try:
                db.session.commit()
                current_app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for student {student.id}"
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(
                    f"Transfer failed for student {student.id}: {e}", exc_info=True
                )
                if is_json:
                    return jsonify(status="error", message="Transfer failed."), 500
                flash("Transfer failed due to a database error.", "transfer_error")
                return redirect(url_for("student.transfer"))
            if is_json:
                return jsonify(status="success", message="Transfer completed successfully!")
            flash("Transfer completed successfully!", "transfer_success")
            return redirect(url_for('student.dashboard'))

    return render_template('student_transfer.html', student=student)


def apply_savings_interest(student, annual_rate=0.045):
    """
    Apply monthly savings interest for a student.
    All time calculations are in UTC.
    """
    now = datetime.now(timezone.utc)
    this_month = now.month
    this_year = now.year

    def _as_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Check if interest was already applied this month
    for tx in student.transactions:
        tx_timestamp = _as_utc(tx.timestamp)
        if (
            tx.account_type == 'savings'
            and tx.description == "Monthly Savings Interest"
            and tx_timestamp
            and tx_timestamp.month == this_month
            and tx_timestamp.year == this_year
        ):
            return  # Interest already applied this month

    for tx in student.transactions:
        if tx.account_type != 'savings' or "Transfer" not in (tx.description or ""):
            continue
        tx_timestamp = _as_utc(tx.timestamp)
        if tx_timestamp and tx_timestamp.date() == now.date():
            return

    eligible_balance = 0
    for tx in student.transactions:
        if tx.account_type != 'savings' or tx.is_void or tx.amount <= 0:
            continue
        available_at = _as_utc(tx.date_funds_available)
        if available_at and (now - available_at).days >= 30:
            eligible_balance += tx.amount
    monthly_rate = annual_rate / 12
    interest = round((eligible_balance or 0.0) * monthly_rate, 2)

    if interest > 0:
        interest_tx = Transaction(
            student_id=student.id,
            amount=interest,
            account_type='savings',
            type='Interest',
            description="Monthly Savings Interest"
        )
        db.session.add(interest_tx)
        db.session.commit()


# -------------------- INSURANCE --------------------

@student_bp.route('/insurance', endpoint='student_insurance')
@login_required
def insurance_marketplace():
    """Insurance marketplace - browse and manage policies."""
    student = get_logged_in_student()

    # Get student's active policies
    my_policies = StudentInsurance.query.filter_by(
        student_id=student.id,
        status='active'
    ).all()

    # Get available policies
    available_policies = InsurancePolicy.query.filter_by(is_active=True).all()

    # Check which policies can be purchased
    can_purchase = {}
    repurchase_blocks = {}

    for policy in available_policies:
        # Check if already enrolled
        existing = StudentInsurance.query.filter_by(
            student_id=student.id,
            policy_id=policy.id,
            status='active'
        ).first()

        if existing:
            can_purchase[policy.id] = False
            continue

        # Check repurchase restrictions
        if policy.no_repurchase_after_cancel:
            cancelled = StudentInsurance.query.filter_by(
                student_id=student.id,
                policy_id=policy.id,
                status='cancelled'
            ).order_by(StudentInsurance.cancel_date.desc()).first()

            if cancelled and cancelled.cancel_date:
                days_since_cancel = (datetime.utcnow() - cancelled.cancel_date).days
                if days_since_cancel < policy.repurchase_wait_days:
                    can_purchase[policy.id] = False
                    repurchase_blocks[policy.id] = policy.repurchase_wait_days - days_since_cancel
                    continue

        can_purchase[policy.id] = True

    # Get claims for my policies
    my_claims = InsuranceClaim.query.filter_by(student_id=student.id).all()

    return render_template('student_insurance_marketplace.html',
                          student=student,
                          my_policies=my_policies,
                          available_policies=available_policies,
                          can_purchase=can_purchase,
                          repurchase_blocks=repurchase_blocks,
                          my_claims=my_claims,
                          now=datetime.utcnow())


@student_bp.route('/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def purchase_insurance(policy_id):
    """Purchase insurance policy."""
    student = get_logged_in_student()
    policy = InsurancePolicy.query.get_or_404(policy_id)

    # Check if already enrolled
    existing = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='active'
    ).first()

    if existing:
        flash("You are already enrolled in this policy.", "warning")
        return redirect(url_for('student.student_insurance'))

    # Check repurchase restrictions
    cancelled = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy.id,
        status='cancelled'
    ).order_by(StudentInsurance.cancel_date.desc()).first()

    if cancelled:
        # Check for permanent block (no repurchase allowed EVER)
        if policy.no_repurchase_after_cancel:
            flash("This policy cannot be repurchased after cancellation.", "danger")
            return redirect(url_for('student.student_insurance'))

        # Check for cooldown period (temporary restriction)
        if policy.enable_repurchase_cooldown and cancelled.cancel_date:
            days_since_cancel = (datetime.utcnow() - cancelled.cancel_date).days
            if days_since_cancel < policy.repurchase_wait_days:
                flash(f"You must wait {policy.repurchase_wait_days - days_since_cancel} more days before repurchasing this policy.", "warning")
                return redirect(url_for('student.student_insurance'))

    # Check sufficient funds
    if student.checking_balance < policy.premium:
        flash("Insufficient funds to purchase this insurance policy.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Create enrollment
    enrollment = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        status='active',
        purchase_date=datetime.utcnow(),
        last_payment_date=datetime.utcnow(),
        next_payment_due=datetime.utcnow() + timedelta(days=30),  # Simplified
        coverage_start_date=datetime.utcnow() + timedelta(days=policy.waiting_period_days),
        payment_current=True
    )
    db.session.add(enrollment)

    # Create transaction to charge premium
    transaction = Transaction(
        student_id=student.id,
        amount=-policy.premium,
        account_type='checking',
        type='insurance_premium',
        description=f"Insurance premium: {policy.title}"
    )
    db.session.add(transaction)

    db.session.commit()
    flash(f"Successfully purchased {policy.title}! Coverage starts after {policy.waiting_period_days} day waiting period.", "success")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
def cancel_insurance(enrollment_id):
    """Cancel insurance policy."""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    enrollment.status = 'cancelled'
    enrollment.cancel_date = datetime.utcnow()

    db.session.commit()
    flash(f"Insurance policy '{enrollment.policy.title}' has been cancelled.", "info")
    return redirect(url_for('student.student_insurance'))


@student_bp.route('/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def file_claim(policy_id):
    """File insurance claim."""
    student = get_logged_in_student()

    # Get student's enrollment for this policy
    enrollment = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy_id,
        status='active'
    ).first()

    if not enrollment:
        flash("You are not enrolled in this policy.", "danger")
        return redirect(url_for('student.student_insurance'))

    policy = enrollment.policy
    form = InsuranceClaimForm()

    # Validation errors
    errors = []

    # Check if coverage has started
    if not enrollment.coverage_start_date or enrollment.coverage_start_date > datetime.utcnow():
        errors.append(f"Coverage has not started yet. Please wait until {enrollment.coverage_start_date.strftime('%B %d, %Y') if enrollment.coverage_start_date else 'coverage starts'}.")

    # Check if payment is current
    if not enrollment.payment_current:
        errors.append("Your premium payments are not current. Please contact the teacher.")

    # Check max claims
    if policy.max_claims_count:
        claims_count = InsuranceClaim.query.filter(
            InsuranceClaim.student_insurance_id == enrollment.id,
            InsuranceClaim.status.in_(['approved', 'paid'])
        ).count()

        if claims_count >= policy.max_claims_count:
            errors.append(f"You have reached the maximum number of claims ({policy.max_claims_count}) for this {policy.max_claims_period}.")

    if request.method == 'POST' and form.validate_on_submit():
        # Additional validation for monetary vs non-monetary
        if policy.is_monetary:
            if not form.claim_amount.data:
                flash("Claim amount is required for monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

            # Check max claim amount
            if policy.max_claim_amount and form.claim_amount.data > policy.max_claim_amount:
                flash(f"Claim amount cannot exceed ${policy.max_claim_amount:.2f}.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))
        else:
            if not form.claim_item.data:
                flash("Claim item is required for non-monetary policies.", "danger")
                return redirect(url_for('student.file_claim', policy_id=policy_id))

        # Check claim time limit
        days_since_incident = (datetime.utcnow() - form.incident_date.data).days
        if days_since_incident > policy.claim_time_limit_days:
            flash(f"Claims must be filed within {policy.claim_time_limit_days} days of the incident.", "danger")
            return redirect(url_for('student.file_claim', policy_id=policy_id))

        # Create claim
        claim = InsuranceClaim(
            student_insurance_id=enrollment.id,
            policy_id=policy.id,
            student_id=student.id,
            incident_date=form.incident_date.data,
            description=form.description.data,
            claim_amount=form.claim_amount.data if policy.is_monetary else None,
            claim_item=form.claim_item.data if not policy.is_monetary else None,
            comments=form.comments.data,
            status='pending'
        )
        db.session.add(claim)
        db.session.commit()

        flash("Claim submitted successfully! It will be reviewed by your teacher.", "success")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this period
    claims_this_period = InsuranceClaim.query.filter_by(
        student_insurance_id=enrollment.id
    ).all()

    return render_template('student_file_claim.html',
                          student=student,
                          policy=policy,
                          enrollment=enrollment,
                          form=form,
                          errors=errors,
                          claims_this_period=claims_this_period)


@student_bp.route('/insurance/policy/<int:enrollment_id>')
@login_required
def view_policy(enrollment_id):
    """View policy details and claims history."""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student.student_insurance'))

    # Get claims for this policy
    claims = InsuranceClaim.query.filter_by(student_insurance_id=enrollment.id).order_by(
        InsuranceClaim.filed_date.desc()
    ).all()

    return render_template('student_view_policy.html',
                          student=student,
                          enrollment=enrollment,
                          policy=enrollment.policy,
                          claims=claims,
                          now=datetime.utcnow())


# -------------------- SHOPPING --------------------

@student_bp.route('/shop')
@login_required
def shop():
    """Student shop - browse and purchase items."""
    student = get_logged_in_student()
    # Fetch active items that haven't passed their auto-delist date
    now = datetime.now(timezone.utc)
    items = StoreItem.query.filter(
        StoreItem.is_active == True,
        or_(StoreItem.auto_delist_date == None, StoreItem.auto_delist_date > now)
    ).order_by(StoreItem.name).all()

    return render_template('student_shop.html', student=student, items=items)


# -------------------- RENT --------------------

def _calculate_rent_deadlines(settings, reference_date=None):
    """Return the due date and grace end date for the active month."""
    reference_date = reference_date or datetime.now()
    current_year = reference_date.year
    current_month = reference_date.month
    last_day_of_month = monthrange(current_year, current_month)[1]
    due_day = min(settings.due_day_of_month, last_day_of_month)
    due_date = datetime(current_year, current_month, due_day)
    grace_end_date = due_date + timedelta(days=settings.grace_period_days)
    return due_date, grace_end_date


@student_bp.route('/rent')
@login_required
def rent():
    """View rent status and payment history (per period)."""
    student = get_logged_in_student()
    settings = RentSettings.query.first()

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "info")
        return redirect(url_for('student.dashboard'))

    # Get student's periods
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]

    # Calculate rent status for each period
    now = datetime.now()
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    current_month = now.month
    current_year = now.year

    period_status = {}
    for period in student_blocks:
        # Check if already paid this month for this period
        payment = RentPayment.query.filter_by(
            student_id=student.id,
            period=period,
            period_month=current_month,
            period_year=current_year
        ).first()

        is_paid = payment is not None
        is_late = now > grace_end_date and not is_paid

        period_status[period] = {
            'is_paid': is_paid,
            'is_late': is_late,
            'payment': payment
        }

    # Get payment history (all periods)
    payment_history = RentPayment.query.filter_by(student_id=student.id).order_by(
        RentPayment.payment_date.desc()
    ).limit(24).all()  # Increased to show more history with multiple periods

    return render_template('student_rent.html',
                          student=student,
                          settings=settings,
                          student_blocks=student_blocks,
                          period_status=period_status,
                          due_date=due_date,
                          grace_end_date=grace_end_date,
                          payment_history=payment_history)


@student_bp.route('/rent/pay/<period>', methods=['POST'])
@login_required
def rent_pay(period):
    """Process rent payment for a specific period."""
    student = get_logged_in_student()
    settings = RentSettings.query.first()

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student.dashboard'))

    if not student.is_rent_enabled:
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student.dashboard'))

    # Validate period
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
    period = period.upper()
    if period not in student_blocks:
        flash("Invalid period.", "error")
        return redirect(url_for('student.rent'))

    now = datetime.now()
    current_month = now.month
    current_year = now.year

    # Check if already paid this month for this period
    existing_payment = RentPayment.query.filter_by(
        student_id=student.id,
        period=period,
        period_month=current_month,
        period_year=current_year
    ).first()

    if existing_payment:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    # Calculate if late and total amount
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    is_late = now > grace_end_date

    total_amount = settings.rent_amount
    late_fee = 0.0

    if is_late:
        late_fee = settings.late_fee
        total_amount += late_fee

    # Check if student has enough funds
    if student.checking_balance < total_amount:
        flash(f"Insufficient funds. You need ${total_amount:.2f} but only have ${student.checking_balance:.2f}.", "error")
        return redirect(url_for('student.rent'))

    # Process payment
    # Deduct from checking account
    transaction = Transaction(
        student_id=student.id,
        amount=-total_amount,
        account_type='checking',
        type='Rent Payment',
        description=f'Rent for Period {period} - {now.strftime("%B %Y")}' + (f' (includes ${late_fee:.2f} late fee)' if is_late else '')
    )
    db.session.add(transaction)

    # Record rent payment
    payment = RentPayment(
        student_id=student.id,
        period=period,
        amount_paid=total_amount,
        period_month=current_month,
        period_year=current_year,
        was_late=is_late,
        late_fee_charged=late_fee
    )
    db.session.add(payment)

    db.session.commit()

    flash(f"Rent payment for Period {period} (${total_amount:.2f}) successful!", "success")
    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Student login with username and PIN."""
    form = StudentLoginForm()
    if form.validate_on_submit():
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        username = form.username.data.strip()
        pin = form.pin.data.strip()
        # Efficiently find the student by querying for the hash of all possible salts.
        # This is still not ideal, but better than loading all students.
        # A better long-term solution is a dedicated username table or a different auth method.
        student = None
        students_with_matching_username_structure = Student.query.filter(
            Student.username_hash.isnot(None)
        ).all()

        try:
            for s in students_with_matching_username_structure:
                candidate_hash = hash_username(username, s.salt)
                if candidate_hash == s.username_hash:
                    student = s
                    break

            if not student or not check_password_hash(student.pin_hash or '', pin):
                if is_json:
                    return jsonify(status="error", message="Invalid credentials"), 401
                flash("Invalid credentials", "error")
                return redirect(url_for('student.login', next=request.args.get('next')))
        except Exception as e:
            current_app.logger.error(f"Error during student login authentication: {str(e)}")
            if is_json:
                return jsonify(status="error", message="An error occurred during login. Please try again."), 500
            flash("An error occurred during login. Please try again.", "error")
            return redirect(url_for('student.login'))

        # --- Set session timeout ---
        # Clear old student-specific session keys without wiping the CSRF token
        session.pop('student_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        # Explicitly clear other potential student-related session keys
        session.pop('claimed_student_id', None)
        session.pop('generated_username', None)


        session['student_id'] = student.id
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['last_activity'] = session['login_time']


        # Removed redirect to student_setup for has_completed_setup; new onboarding flow uses claim → username → pin/passphrase.

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if not is_safe_url(next_url):
            return redirect(url_for('student.dashboard'))
        return redirect(next_url or url_for('student.dashboard'))

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)


@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    session.pop('student_id', None)
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


# -------------------- SETUP COMPLETE --------------------
# Note: This route is not prefixed with /student for backward compatibility

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html')
