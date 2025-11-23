"""
Student routes for Classroom Token Hub.

Contains all student-facing functionality including account setup, dashboard,
financial transactions, shopping, insurance, and rent payment.
"""

import json
import random
import re
import hashlib
import hmac
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
    RentSettings, RentPayment, InsurancePolicy, StudentInsurance, InsuranceClaim,
    BankingSettings, UserReport
)
from app.auth import admin_required, login_required, get_logged_in_student, SESSION_TIMEOUT_MINUTES
from forms import (
    StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm,
    StudentLoginForm, InsuranceClaimForm
)

# Import utility functions
from app.utils.helpers import is_safe_url
from app.utils.constants import THEME_PROMPTS
from app.utils.turnstile import verify_turnstile_token
from app.utils.demo_sessions import cleanup_demo_student_data
from hash_utils import hash_hmac, hash_username, hash_username_lookup
from attendance import get_all_block_statuses

# Create blueprint
student_bp = Blueprint('student', __name__, url_prefix='/student')


# -------------------- PERIOD SELECTION HELPERS --------------------

def get_current_teacher_id():
    """Get the currently selected teacher ID from session.

    Returns the teacher_id for the period/class the student is currently viewing.
    If no period is selected, defaults to the student's primary teacher.
    """
    student = get_logged_in_student()
    if not student:
        return None

    # Check if a period is already selected in session
    current_teacher_id = session.get('current_teacher_id')

    # Get all linked teachers
    all_teachers = student.get_all_teachers()
    if not all_teachers:
        return None

    # If no period selected, default to first linked teacher
    if not current_teacher_id:
        current_teacher_id = all_teachers[0].id
        # Store in session for future requests
        session['current_teacher_id'] = current_teacher_id

    # Verify student still has access to this teacher
    teacher_ids = [t.id for t in all_teachers]
    if current_teacher_id not in teacher_ids:
        # Teacher no longer accessible, reset to first available
        current_teacher_id = all_teachers[0].id
        session['current_teacher_id'] = current_teacher_id

    return current_teacher_id


def _generate_anonymous_code(user_identifier: str) -> str:
    """Return an HMAC-based anonymous code for the given user identifier."""

    secret = current_app.config.get("USER_REPORT_SECRET") or current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("USER_REPORT_SECRET or SECRET_KEY must be configured for anonymous reporting")

    secret_bytes = secret if isinstance(secret, (bytes, bytearray)) else str(secret).encode()
    return hmac.new(secret_bytes, user_identifier.encode(), hashlib.sha256).hexdigest()


# -------------------- STUDENT ONBOARDING --------------------

@student_bp.route('/claim-account', methods=['GET', 'POST'])
def claim_account():
    """
    PAGE 1: Claim Account - Verify identity using join code to begin setup.

    New join code-based flow:
    1. Student enters join code (identifies their teacher-period)
    2. Student enters name code + DOB sum
    3. System finds matching unclaimed seat in TeacherBlock
    4. Creates Student record (or finds existing if student has other classes)
    5. Links TeacherBlock seat to Student
    6. Creates StudentTeacher link
    """
    from app.models import TeacherBlock, StudentTeacher
    from app.utils.join_code import format_join_code

    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        join_code = format_join_code(form.join_code.data)
        first_initial = form.first_initial.data.strip().upper()
        last_name = form.last_name.data.strip()
        dob_sum_str = form.dob_sum.data.strip()

        if not dob_sum_str.isdigit():
            flash("DOB sum must be a number.", "claim")
            return redirect(url_for('student.claim_account'))

        # Find all unclaimed seats with this join code
        unclaimed_seats = TeacherBlock.query.filter_by(
            join_code=join_code,
            is_claimed=False
        ).all()

        if not unclaimed_seats:
            flash("Invalid join code or all seats already claimed. Check with your teacher.", "claim")
            return redirect(url_for('student.claim_account'))

        # Try to find a matching seat
        from app.utils.name_utils import verify_last_name_parts

        matched_seat = None
        for seat in unclaimed_seats:
            # Check credential: CONCAT(first_initial, DOB_sum)
            credential = f"{first_initial}{dob_sum_str}"
            credential_matches = seat.first_half_hash == hash_hmac(credential.encode(), seat.salt)

            # Check last name with fuzzy matching
            last_name_matches = verify_last_name_parts(
                last_name,
                seat.last_name_hash_by_part,
                seat.salt
            )

            if credential_matches and last_name_matches and str(seat.dob_sum) == dob_sum_str:
                matched_seat = seat
                break

        if not matched_seat:
            flash("No matching account found. Please check your join code and credentials.", "claim")
            return redirect(url_for('student.claim_account'))

        # Check if this student already has an account (claiming from another teacher)
        # Look for existing students with same credentials across all teachers
        existing_student = None
        all_students = Student.query.filter_by(
            last_initial=first_initial,
            dob_sum=int(dob_sum_str)
        ).all()

        for student in all_students:
            if student.first_name == matched_seat.first_name:
                # Verify credential matches
                credential = f"{first_initial}{dob_sum_str}"
                if student.first_half_hash == hash_hmac(credential.encode(), student.salt):
                    existing_student = student
                    break

        if existing_student:
            # Student already exists - link this seat to existing student
            matched_seat.student_id = existing_student.id
            matched_seat.is_claimed = True
            matched_seat.claimed_at = datetime.utcnow()

            # Create StudentTeacher link
            existing_link = StudentTeacher.query.filter_by(
                student_id=existing_student.id,
                admin_id=matched_seat.teacher_id
            ).first()

            if not existing_link:
                link = StudentTeacher(
                    student_id=existing_student.id,
                    admin_id=matched_seat.teacher_id
                )
                db.session.add(link)

            db.session.commit()

            # Student already completed setup in another class, redirect to login
            if existing_student.has_completed_setup:
                flash("This seat has been linked to your existing account. Please log in.", "claim")
                return redirect(url_for('student.login'))
            else:
                # Continue setup process
                session['claimed_student_id'] = existing_student.id
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)
                return redirect(url_for('student.create_username'))

        # New student - create Student record
        # Generate second_half_hash (DOB hash) for backward compatibility
        second_half_hash = hash_hmac(dob_sum_str.encode(), matched_seat.salt)

        new_student = Student(
            first_name=matched_seat.first_name,
            last_initial=matched_seat.last_initial,
            block=matched_seat.block,
            salt=matched_seat.salt,
            first_half_hash=matched_seat.first_half_hash,
            second_half_hash=second_half_hash,
            dob_sum=matched_seat.dob_sum,
            last_name_hash_by_part=matched_seat.last_name_hash_by_part,
            has_completed_setup=False,
            teacher_id=None,  # DEPRECATED - no longer used
        )
        db.session.add(new_student)
        db.session.flush()  # Get student ID

        # Link seat to student
        matched_seat.student_id = new_student.id
        matched_seat.is_claimed = True
        matched_seat.claimed_at = datetime.utcnow()

        # Create StudentTeacher link
        link = StudentTeacher(
            student_id=new_student.id,
            admin_id=matched_seat.teacher_id
        )
        db.session.add(link)
        db.session.commit()

        # Start setup flow
        session['claimed_student_id'] = new_student.id
        session.pop('generated_username', None)
        session.pop('theme_prompt', None)
        session.pop('theme_slug', None)

        return redirect(url_for('student.create_username'))

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
        student.username_lookup_hash = hash_username_lookup(username)
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
        return redirect(url_for('student.setup_complete'))
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
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired'])
    ).order_by(StudentItem.purchase_date.desc()).all()

    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']

    forecast_interest = round(student.savings_balance * (0.045 / 12), 2)

    period_states = get_all_block_statuses(student)
    student_blocks = list(period_states.keys())
    period_states_json = json.dumps(period_states, separators=(',', ':'))

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: state.get("projected_pay", 0)
        for blk, state in period_states.items()
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

    # Get student's active insurance policies
    active_insurance = StudentInsurance.query.filter_by(
        student_id=student.id,
        status='active'
    ).first()  # Get first active policy for dashboard display

    rent_status = None
    rent_settings = RentSettings.query.first()
    if rent_settings and rent_settings.is_enabled and student.is_rent_enabled:
        now = datetime.now()
        due_date, grace_end_date = _calculate_rent_deadlines(rent_settings, now)

        preview_start_date = None
        if rent_settings.bill_preview_enabled and rent_settings.bill_preview_days:
            preview_start_date = due_date - timedelta(days=rent_settings.bill_preview_days)

        rent_is_active = True
        is_preview_period = False
        if rent_settings.first_rent_due_date and now < rent_settings.first_rent_due_date:
            if preview_start_date and now >= preview_start_date:
                rent_is_active = True
                is_preview_period = True
            else:
                rent_is_active = False
        elif preview_start_date and preview_start_date <= now < due_date:
            is_preview_period = True

        student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
        current_month = now.month
        current_year = now.year

        all_paid = True
        for period in student_blocks:
            all_payments_for_period = RentPayment.query.filter_by(
                student_id=student.id,
                period=period,
                period_month=current_month,
                period_year=current_year
            ).all()

            payments = []
            for payment in all_payments_for_period:
                txn = Transaction.query.filter(
                    Transaction.student_id == student.id,
                    Transaction.type == 'Rent Payment',
                    Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
                    Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
                    Transaction.amount == -payment.amount_paid
                ).first()

                if txn and not txn.is_void:
                    payments.append(payment)

            total_paid = sum(p.amount_paid for p in payments) if payments else 0.0
            late_fee = rent_settings.late_fee if rent_is_active and now > grace_end_date else 0.0
            total_due = rent_settings.rent_amount + late_fee if rent_is_active else 0.0
            is_paid = total_paid >= total_due if rent_is_active else False

            if rent_is_active and not is_paid:
                all_paid = False
                break

        rent_status = {
            'is_active': rent_is_active,
            'is_paid': all_paid if rent_is_active else False,
            'is_preview': is_preview_period
        }

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
        recent_transactions=transactions[:5],  # Most recent 5 transactions
        now=local_now,
        forecast_interest=forecast_interest,
        recent_deposit=recent_deposit,
        active_insurance=active_insurance,
        rent_status=rent_status,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        student_name=student_name,
        total_unpaid_elapsed=total_unpaid_elapsed,
    )


@student_bp.route('/payroll')
@login_required
def payroll():
    """Student payroll page with attendance record, productivity stats, and projected pay."""
    student = get_logged_in_student()

    period_states = get_all_block_statuses(student)
    student_blocks = list(period_states.keys())

    unpaid_seconds_per_block = {
        blk: state.get("duration", 0)
        for blk, state in period_states.items()
    }

    projected_pay_per_block = {
        blk: round(state.get("projected_pay", 0), 2)
        for blk, state in period_states.items()
    }

    # Get all tap events grouped by block
    all_tap_events = TapEvent.query.filter_by(student_id=student.id).order_by(TapEvent.timestamp.desc()).all()
    tap_events_by_block = {}
    for event in all_tap_events:
        # Normalize to the action labels used by the template
        event.action = 'tap_in' if event.status == 'active' else 'tap_out'
        if event.period not in tap_events_by_block:
            tap_events_by_block[event.period] = []
        tap_events_by_block[event.period].append(event)

    return render_template(
        'student_payroll.html',
        student=student,
        student_blocks=student_blocks,
        unpaid_seconds_per_block=unpaid_seconds_per_block,
        projected_pay_per_block=projected_pay_per_block,
        period_states=period_states,
        all_tap_events=all_tap_events,
        tap_events_by_block=tap_events_by_block,
        now=datetime.now(timezone.utc)
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

    # Get transactions for display
    transactions = Transaction.query.filter_by(student_id=student.id, is_void=False).order_by(Transaction.timestamp.desc()).all()
    checking_transactions = [t for t in transactions if t.account_type == 'checking']
    savings_transactions = [t for t in transactions if t.account_type == 'savings']

    # Get banking settings for interest rate display
    from app.models import BankingSettings
    settings = BankingSettings.query.first()
    annual_rate = settings.savings_apy / 100 if settings else 0.045
    calculation_type = settings.interest_calculation_type if settings else 'simple'
    compound_frequency = settings.compound_frequency if settings else 'monthly'

    # Calculate forecast interest based on settings
    if calculation_type == 'compound':
        if compound_frequency == 'daily':
            periods_per_month = 30
            rate_per_period = annual_rate / 365
            forecast_interest = student.savings_balance * ((1 + rate_per_period) ** periods_per_month - 1)
        elif compound_frequency == 'weekly':
            periods_per_month = 4.33
            rate_per_period = annual_rate / 52
            forecast_interest = student.savings_balance * ((1 + rate_per_period) ** periods_per_month - 1)
        else:  # monthly
            forecast_interest = student.savings_balance * (annual_rate / 12)
    else:
        # Simple interest: calculate only on principal (excluding interest earnings)
        principal = sum(tx.amount for tx in savings_transactions if tx.type != 'Interest' and 'Interest' not in (tx.description or ''))
        forecast_interest = principal * (annual_rate / 12)

    return render_template('student_transfer.html',
                         student=student,
                         transactions=transactions,
                         checking_transactions=checking_transactions,
                         savings_transactions=savings_transactions,
                         forecast_interest=forecast_interest,
                         settings=settings,
                         calculation_type=calculation_type,
                         compound_frequency=compound_frequency)


def apply_savings_interest(student, annual_rate=0.045):
    """
    Apply savings interest for a student based on banking settings.
    Supports both simple and compound interest with configurable frequency.
    All time calculations are in UTC.
    """
    from app.models import BankingSettings

    now = datetime.now(timezone.utc)
    this_month = now.month
    this_year = now.year

    def _as_utc(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # Get banking settings
    settings = BankingSettings.query.first()
    if not settings:
        # Use default simple interest if no settings
        calculation_type = 'simple'
        compound_frequency = 'monthly'
    else:
        calculation_type = settings.interest_calculation_type or 'simple'
        compound_frequency = settings.compound_frequency or 'monthly'

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

    # Calculate interest based on type
    if calculation_type == 'compound':
        # For compound interest, use current total balance (including previous interest)
        balance = student.savings_balance

        # Determine the rate based on compound frequency
        if compound_frequency == 'daily':
            # Daily compounding: rate = (1 + annual_rate/365)^365 - 1 ≈ annual_rate for small rates
            # For monthly payout with daily compounding: (1 + annual_rate/365)^30
            periods_per_year = 365
            periods_per_month = 30
            rate_per_period = annual_rate / periods_per_year
            interest = round(balance * ((1 + rate_per_period) ** periods_per_month - 1), 2)
        elif compound_frequency == 'weekly':
            # Weekly compounding: (1 + annual_rate/52)^4.33 (approx weeks per month)
            periods_per_year = 52
            periods_per_month = 4.33
            rate_per_period = annual_rate / periods_per_year
            interest = round(balance * ((1 + rate_per_period) ** periods_per_month - 1), 2)
        else:  # monthly
            # Monthly compounding
            monthly_rate = annual_rate / 12
            interest = round(balance * monthly_rate, 2)
    else:
        # Simple interest: only calculate on original deposits (not including previous interest)
        eligible_balance = 0
        for tx in student.transactions:
            if tx.account_type != 'savings' or tx.is_void or tx.amount <= 0:
                continue
            # Exclude interest transactions from principal calculation
            if tx.type == 'Interest' or 'Interest' in (tx.description or ''):
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

    # Get teacher IDs associated with this student
    teacher_ids = [teacher.id for teacher in student.teachers]

    # Get available policies (only from student's teachers)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.teacher_id.in_(teacher_ids)
    ).all() if teacher_ids else []

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

    # Group policies by tier for display
    tier_groups = {}
    ungrouped_policies = []
    for policy in available_policies:
        if policy.tier_category_id:
            if policy.tier_category_id not in tier_groups:
                tier_groups[policy.tier_category_id] = {
                    'name': policy.tier_name or f"Tier {policy.tier_category_id}",
                    'color': policy.tier_color or 'primary',
                    'policies': []
                }
            tier_groups[policy.tier_category_id]['policies'].append(policy)
        else:
            ungrouped_policies.append(policy)

    # Check which tier the student has already selected from
    enrolled_tiers = set()
    for enrollment in my_policies:
        if enrollment.policy.tier_category_id:
            enrolled_tiers.add(enrollment.policy.tier_category_id)

    return render_template('student_insurance_marketplace.html',
                          student=student,
                          my_policies=my_policies,
                          available_policies=ungrouped_policies,
                          tier_groups=tier_groups,
                          enrolled_tiers=enrolled_tiers,
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

    # Verify policy belongs to one of student's teachers
    teacher_ids = [teacher.id for teacher in student.teachers]
    if policy.teacher_id not in teacher_ids:
        flash("This insurance policy is not available to you.", "danger")
        return redirect(url_for('student.student_insurance'))

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

    # Check tier restrictions - can only have one policy per tier
    if policy.tier_category_id:
        existing_tier_enrollment = StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id == student.id,
            StudentInsurance.status == 'active',
            InsurancePolicy.tier_category_id == policy.tier_category_id
        ).first()

        if existing_tier_enrollment:
            flash(f"You already have a policy from the '{policy.tier_name or 'this'}' tier. You can only have one policy per tier.", "warning")
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

    # Fetch student's purchased items
    student_items = student.items.filter(
        StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired'])
    ).order_by(StudentItem.purchase_date.desc()).all()

    return render_template('student_shop.html', student=student, items=items, student_items=student_items)


# -------------------- RENT --------------------

def _charge_overdraft_fee_if_needed(student, banking_settings):
    """
    Check if student's checking balance is negative and charge overdraft fee if enabled.
    Returns (fee_charged, fee_amount) tuple.
    """
    if not banking_settings or not banking_settings.overdraft_fee_enabled:
        return False, 0.0

    # Only charge if balance is negative
    if student.checking_balance >= 0:
        return False, 0.0

    fee_amount = 0.0

    if banking_settings.overdraft_fee_type == 'flat':
        fee_amount = banking_settings.overdraft_fee_flat_amount
    elif banking_settings.overdraft_fee_type == 'progressive':
        # Count how many overdraft fees charged this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        overdraft_fee_count = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.type == 'overdraft_fee',
            Transaction.timestamp >= month_start
        ).count()

        # Determine which tier to use (1st, 2nd, 3rd, or cap)
        if overdraft_fee_count == 0:
            fee_amount = banking_settings.overdraft_fee_progressive_1 or 0.0
        elif overdraft_fee_count == 1:
            fee_amount = banking_settings.overdraft_fee_progressive_2 or 0.0
        elif overdraft_fee_count >= 2:
            fee_amount = banking_settings.overdraft_fee_progressive_3 or 0.0

        # Check if cap is exceeded
        if banking_settings.overdraft_fee_progressive_cap:
            total_fees_this_month = db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.student_id == student.id,
                Transaction.type == 'overdraft_fee',
                Transaction.timestamp >= month_start
            ).scalar() or 0.0

            # total_fees_this_month is negative, so we negate it
            if abs(total_fees_this_month) + fee_amount > banking_settings.overdraft_fee_progressive_cap:
                # Don't charge more than the cap
                fee_amount = max(0, banking_settings.overdraft_fee_progressive_cap - abs(total_fees_this_month))

    if fee_amount > 0:
        # Charge the fee
        overdraft_fee_tx = Transaction(
            student_id=student.id,
            amount=-fee_amount,
            account_type='checking',
            type='overdraft_fee',
            description=f'Overdraft fee (balance: ${student.checking_balance:.2f})'
        )
        db.session.add(overdraft_fee_tx)
        db.session.flush()  # Update the balance calculation
        return True, fee_amount

    return False, 0.0


def _calculate_rent_deadlines(settings, reference_date=None):
    """Return the due date and grace end date for the active month."""
    reference_date = reference_date or datetime.now()

    # If first_rent_due_date is set and we haven't reached it yet, return it
    if settings.first_rent_due_date:
        first_due = settings.first_rent_due_date
        # If we're before the first due date, return the first due date
        if reference_date < first_due:
            grace_end_date = first_due + timedelta(days=settings.grace_period_days)
            return first_due, grace_end_date

        # Calculate due date based on frequency from first_rent_due_date
        if settings.frequency_type == 'monthly':
            # Calculate how many months have passed since first due date
            months_diff = (reference_date.year - first_due.year) * 12 + (reference_date.month - first_due.month)
            # Calculate the due date for the current period
            target_year = first_due.year + (first_due.month + months_diff - 1) // 12
            target_month = (first_due.month + months_diff - 1) % 12 + 1
            last_day_of_month = monthrange(target_year, target_month)[1]
            due_day = min(first_due.day, last_day_of_month)
            due_date = datetime(target_year, target_month, due_day)
        else:
            # For non-monthly frequencies, fall back to current logic
            # TODO: Implement weekly, daily, and custom frequencies properly
            current_year = reference_date.year
            current_month = reference_date.month
            last_day_of_month = monthrange(current_year, current_month)[1]
            due_day = min(settings.due_day_of_month, last_day_of_month)
            due_date = datetime(current_year, current_month, due_day)
    else:
        # No first_rent_due_date set, use traditional monthly logic
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

    # Calculate due dates
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)

    # Calculate preview start date if preview is enabled
    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = due_date - timedelta(days=settings.bill_preview_days)

    # Check if rent is active (due date has arrived or preview period has started)
    rent_is_active = True
    is_preview_period = False
    if settings.first_rent_due_date and now < settings.first_rent_due_date:
        # Check if we're in preview period before first due date
        if preview_start_date and now >= preview_start_date:
            rent_is_active = True
            is_preview_period = True
        else:
            rent_is_active = False
    elif preview_start_date and now >= preview_start_date and now < due_date:
        is_preview_period = True
    current_month = now.month
    current_year = now.year

    period_status = {}
    for period in student_blocks:
        # Get all payments for this period this month (supports incremental payments)
        all_payments_for_period = RentPayment.query.filter_by(
            student_id=student.id,
            period=period,
            period_month=current_month,
            period_year=current_year
        ).all()

        # Filter out payments where the corresponding transaction was voided
        payments = []
        for payment in all_payments_for_period:
            # Find the transaction for this payment
            txn = Transaction.query.filter(
                Transaction.student_id == student.id,
                Transaction.type == 'Rent Payment',
                Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
                Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
                Transaction.amount == -payment.amount_paid
            ).first()

            # Only include if transaction exists and is not voided
            if txn and not txn.is_void:
                payments.append(payment)

        # Calculate total paid (sum of all non-voided payments)
        total_paid = sum(p.amount_paid for p in payments) if payments else 0.0

        # Calculate late fee if applicable (only if rent is active)
        late_fee = 0.0
        if rent_is_active and now > grace_end_date:
            late_fee = settings.late_fee

        # Total amount due (rent + late fee if applicable)
        total_due = settings.rent_amount + late_fee if rent_is_active else 0.0

        # Check if fully paid
        is_paid = total_paid >= total_due if rent_is_active else False
        is_late = now > grace_end_date and not is_paid if rent_is_active else False
        remaining_amount = max(0, total_due - total_paid) if rent_is_active else 0.0

        period_status[period] = {
            'is_paid': is_paid,
            'is_late': is_late,
            'payments': payments,
            'total_paid': total_paid,
            'total_due': total_due,
            'remaining_amount': remaining_amount,
            'late_fee': late_fee,
            'rent_is_active': rent_is_active,
            'is_preview_period': is_preview_period
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
                          preview_start_date=preview_start_date,
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

    # Calculate due dates and preview period
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    preview_start_date = None
    if settings.bill_preview_enabled and settings.bill_preview_days:
        preview_start_date = due_date - timedelta(days=settings.bill_preview_days)

    # Check if rent is even due yet (if first_rent_due_date is in the future and not in preview period)
    if settings.first_rent_due_date and now < settings.first_rent_due_date:
        # Allow payment if we're in the preview period
        if not (preview_start_date and now >= preview_start_date):
            flash(f"Rent is not due yet. First payment due on {settings.first_rent_due_date.strftime('%B %d, %Y')}.", "info")
            return redirect(url_for('student.rent'))

    current_month = now.month
    current_year = now.year

    # Get all existing payments for this period this month
    all_payments = RentPayment.query.filter_by(
        student_id=student.id,
        period=period,
        period_month=current_month,
        period_year=current_year
    ).all()

    # Filter out payments where the corresponding transaction was voided
    existing_payments = []
    for payment in all_payments:
        # Find the transaction for this payment
        txn = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.type == 'Rent Payment',
            Transaction.timestamp >= payment.payment_date - timedelta(seconds=5),
            Transaction.timestamp <= payment.payment_date + timedelta(seconds=5),
            Transaction.amount == -payment.amount_paid
        ).first()

        # Only include if transaction exists and is not voided
        if txn and not txn.is_void:
            existing_payments.append(payment)

    total_paid_so_far = sum(p.amount_paid for p in existing_payments) if existing_payments else 0.0

    # Calculate if late and total amount due
    due_date, grace_end_date = _calculate_rent_deadlines(settings, now)
    is_late = now > grace_end_date

    # Calculate late fee if applicable
    late_fee = 0.0
    if is_late:
        late_fee = settings.late_fee

    # Total amount due (rent + late fee if applicable)
    total_due = settings.rent_amount + late_fee

    # Calculate remaining amount to pay
    remaining_amount = total_due - total_paid_so_far

    # Check if already fully paid
    if remaining_amount <= 0:
        flash(f"You have already paid rent for Period {period} this month!", "info")
        return redirect(url_for('student.rent'))

    # Get payment amount from form (supports incremental payments)
    payment_amount_input = request.form.get('amount', '').strip()

    # Determine payment amount based on incremental setting
    if settings.allow_incremental_payment and payment_amount_input:
        try:
            payment_amount = float(payment_amount_input)
            # Validate payment amount
            if payment_amount <= 0:
                flash("Payment amount must be greater than 0.", "error")
                return redirect(url_for('student.rent'))
            if payment_amount > remaining_amount:
                flash(f"Payment amount (${payment_amount:.2f}) exceeds remaining balance (${remaining_amount:.2f}). Paying exact remaining amount.", "info")
                payment_amount = remaining_amount
        except ValueError:
            flash("Invalid payment amount.", "error")
            return redirect(url_for('student.rent'))
    else:
        # Full payment required (or no amount specified with incremental disabled)
        payment_amount = remaining_amount

    # Get banking settings for overdraft handling
    banking_settings = BankingSettings.query.first()

    # Check if student has enough funds for this payment
    if student.checking_balance < payment_amount:
        # Check if overdraft protection is enabled (savings can cover the difference)
        if banking_settings and banking_settings.overdraft_protection_enabled:
            shortfall = payment_amount - student.checking_balance
            if student.savings_balance >= shortfall:
                # Allow transaction - overdraft protection will transfer from savings
                pass
            else:
                flash(f"Insufficient funds in both checking and savings. You need ${payment_amount:.2f} but have ${student.checking_balance + student.savings_balance:.2f}.", "error")
                return redirect(url_for('student.rent'))
        # Check if overdraft fees are enabled (allows negative balance)
        elif banking_settings and banking_settings.overdraft_fee_enabled:
            # Allow transaction - will charge overdraft fee after transaction
            pass
        else:
            # No overdraft options - reject transaction
            flash(f"Insufficient funds. You need ${payment_amount:.2f} but only have ${student.checking_balance:.2f}.", "error")
            return redirect(url_for('student.rent'))

    # Process payment
    # Deduct from checking account
    is_partial = payment_amount < remaining_amount
    payment_description = f'Rent for Period {period} - {now.strftime("%B %Y")}'
    if is_partial and settings.allow_incremental_payment:
        payment_description += f' (Partial: ${payment_amount:.2f} of ${remaining_amount:.2f})'
    elif late_fee > 0:
        payment_description += f' (includes ${late_fee:.2f} late fee)'

    transaction = Transaction(
        student_id=student.id,
        amount=-payment_amount,
        account_type='checking',
        type='Rent Payment',
        description=payment_description
    )
    db.session.add(transaction)

    # Calculate late fee portion for this payment (proportional if partial payment)
    late_fee_for_this_payment = 0.0
    if is_late and late_fee > 0:
        # If this is a partial payment, allocate late fee proportionally
        if is_partial:
            late_fee_for_this_payment = (payment_amount / total_due) * late_fee
        else:
            late_fee_for_this_payment = late_fee

    # Record rent payment
    payment = RentPayment(
        student_id=student.id,
        period=period,
        amount_paid=payment_amount,
        period_month=current_month,
        period_year=current_year,
        was_late=is_late,
        late_fee_charged=late_fee_for_this_payment
    )
    db.session.add(payment)

    db.session.flush()  # Flush to update balances without committing yet

    # Handle overdraft protection and fees
    # Check if overdraft protection should transfer funds from savings
    if banking_settings and banking_settings.overdraft_protection_enabled and student.checking_balance < 0:
        shortfall = abs(student.checking_balance)
        if student.savings_balance >= shortfall:
            # Transfer from savings to checking
            transfer_tx_withdraw = Transaction(
                student_id=student.id,
                amount=-shortfall,
                account_type='savings',
                type='Withdrawal',
                description='Overdraft protection transfer to checking'
            )
            transfer_tx_deposit = Transaction(
                student_id=student.id,
                amount=shortfall,
                account_type='checking',
                type='Deposit',
                description='Overdraft protection transfer from savings'
            )
            db.session.add(transfer_tx_withdraw)
            db.session.add(transfer_tx_deposit)
            db.session.flush()  # Flush to update balances

    # Check if overdraft fee should be charged (after overdraft protection)
    fee_charged, fee_amount = _charge_overdraft_fee_if_needed(student, banking_settings)

    # Commit all transactions together
    db.session.commit()

    # Calculate new totals after this payment
    new_total_paid = total_paid_so_far + payment_amount
    new_remaining = total_due - new_total_paid

    # Success message
    if is_partial and settings.allow_incremental_payment:
        if new_remaining > 0:
            flash(f"Partial payment of ${payment_amount:.2f} successful! Remaining balance: ${new_remaining:.2f}", "success")
        else:
            flash(f"Final payment of ${payment_amount:.2f} successful! Rent for Period {period} is now fully paid.", "success")
    else:
        flash(f"Rent payment for Period {period} (${payment_amount:.2f}) successful!", "success")

    return redirect(url_for('student.rent'))


# -------------------- AUTHENTICATION --------------------

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Student login with username and PIN."""
    form = StudentLoginForm()
    if form.validate_on_submit():
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Verify Turnstile token
        turnstile_token = request.form.get('cf-turnstile-response')
        if not verify_turnstile_token(turnstile_token, request.remote_addr):
            current_app.logger.warning(f"Turnstile verification failed for student login attempt")
            if is_json:
                return jsonify(status="error", message="CAPTCHA verification failed. Please try again."), 403
            flash("CAPTCHA verification failed. Please try again.", "error")
            return redirect(url_for('student.login', next=request.args.get('next')))

        username = form.username.data.strip()
        pin = form.pin.data.strip()
        lookup_hash = hash_username_lookup(username)
        student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()

        try:
            # Fallback for legacy accounts without deterministic lookup hashes
            if not student:
                students_with_matching_username_structure = Student.query.filter(
                    Student.username_hash.isnot(None)
                ).yield_per(50)

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

            if not student.username_lookup_hash:
                student.username_lookup_hash = lookup_hash
                db.session.commit()
        except Exception as e:
            db.session.rollback()
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


@student_bp.route('/demo-login/<string:session_id>')
@admin_required
def demo_login(session_id):
    """Auto-login for demo student sessions created by admins.

    SECURITY: This route requires the user to already be logged in as the admin
    who created the demo session. Demo links cannot be used by anonymous users
    or other admins.
    """
    from app.models import DemoStudent, Admin

    try:
        # Find the demo session
        demo_session = DemoStudent.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()

        if not demo_session:
            flash("Demo session not found or has expired.", "error")
            return redirect(url_for('admin.dashboard'))

        # Check if session has expired
        now = datetime.now(timezone.utc)
        if now > demo_session.expires_at:
            # Mark as inactive and cleanup
            cleanup_demo_student_data(demo_session)
            db.session.commit()
            flash("Demo session has expired (10 minute limit).", "error")
            return redirect(url_for('admin.dashboard'))

        # SECURITY: Verify the user is logged in as the admin who created this demo
        # This prevents privilege escalation via demo links
        if not session.get('is_admin') or session.get('admin_id') != demo_session.admin_id:
            current_app.logger.warning(
                f"Unauthorized demo login attempt for session {session_id}. "
                f"Current admin_id={session.get('admin_id')}, required={demo_session.admin_id}"
            )
            flash("You must be logged in as the admin who created this demo session.", "error")
            return redirect(url_for('admin.login'))

        # Set up student session (preserving admin authentication)
        student = demo_session.student

        # Clear student-specific keys only, preserve admin session
        session.pop('student_id', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        session.pop('is_demo', None)
        session.pop('demo_session_id', None)

        # Set student session variables
        session['student_id'] = student.id
        session['login_time'] = datetime.now(timezone.utc).isoformat()
        session['last_activity'] = session['login_time']
        session['is_demo'] = True
        session['demo_session_id'] = session_id
        session['view_as_student'] = True

        current_app.logger.info(
            f"Admin {demo_session.admin_id} accessed demo session {session_id} "
            f"(student_id={student.id})"
        )

        flash("Demo session started! Session will expire in 10 minutes.", "success")
        return redirect(url_for('student.dashboard'))

    except Exception as e:
        current_app.logger.error(f"Error during demo login: {e}", exc_info=True)
        flash("An error occurred starting the demo session.", "error")
        return redirect(url_for('student.login'))


@student_bp.route('/logout')
@login_required
def logout():
    """Student logout."""
    # Check if this is a demo session
    is_demo = session.get('is_demo', False)
    demo_session_id = session.get('demo_session_id')

    if is_demo and demo_session_id:
        # Clean up demo session
        from app.models import DemoStudent
        try:
            demo_session = DemoStudent.query.filter_by(session_id=demo_session_id).first()
            if demo_session:
                demo_session.is_active = False
                demo_session.ended_at = datetime.now(timezone.utc)

                cleanup_demo_student_data(demo_session)

                db.session.commit()
                current_app.logger.info(f"Demo session {demo_session_id} ended and cleaned up")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cleaning up demo session: {e}", exc_info=True)

    session.clear()
    flash("You've been logged out.")
    return redirect(url_for('student.login'))


@student_bp.route('/switch-period/<int:teacher_id>', methods=['POST'])
@login_required
def switch_period(teacher_id):
    """Switch to a different period/teacher's class economy."""
    student = get_logged_in_student()

    # Verify student has access to this teacher
    teacher_ids = [t.id for t in student.get_all_teachers()]
    if teacher_id not in teacher_ids:
        flash("You don't have access to that class.", "error")
        return redirect(url_for('student.dashboard'))

    # Update session with new teacher
    session['current_teacher_id'] = teacher_id

    # Get teacher name for flash message
    from app.models import Admin
    teacher = Admin.query.get(teacher_id)
    if teacher:
        flash(f"Switched to {teacher.username}'s class")

    return redirect(url_for('student.dashboard'))


# -------------------- SETUP COMPLETE --------------------
# Note: This route is not prefixed with /student for backward compatibility

@student_bp.route('/setup-complete')
@login_required
def setup_complete():
    """Setup completion confirmation page."""
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html', student_name=student.first_name)


# -------------------- HELP AND SUPPORT --------------------

@student_bp.route('/help-support', methods=['GET', 'POST'])
@login_required
def help_support():
    """Help and Support page with bug reporting, suggestions, and documentation."""
    student = get_logged_in_student()

    if request.method == 'POST':
        # Handle bug report submission
        report_type = request.form.get('report_type', 'bug')
        error_code = request.form.get('error_code', '')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        steps_to_reproduce = request.form.get('steps_to_reproduce', '').strip()
        expected_behavior = request.form.get('expected_behavior', '').strip()
        page_url = request.form.get('page_url', '').strip()

        # Validation
        if not title or not description:
            flash("Please provide both a title and description for your report.", "error")
            return redirect(url_for('student.help_support'))

        # Generate anonymous code derived from a secret to prevent reversal by admins
        anonymous_code = _generate_anonymous_code(f"student:{student.id}")

        # Create report
        try:
            report = UserReport(
                anonymous_code=anonymous_code,
                user_type='student',
                report_type=report_type,
                error_code=error_code if error_code else None,
                title=title,
                description=description,
                steps_to_reproduce=steps_to_reproduce if steps_to_reproduce else None,
                expected_behavior=expected_behavior if expected_behavior else None,
                page_url=page_url if page_url else None,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                _student_id=student.id,  # Hidden from sysadmin, used only for rewards
                status='new'
            )
            db.session.add(report)
            db.session.commit()

            flash("Thank you for your report! If it's a legitimate bug, you may receive a reward.", "success")
            return redirect(url_for('student.help_support'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error submitting report: {str(e)}")
            flash("An error occurred while submitting your report. Please try again.", "error")
            return redirect(url_for('student.help_support'))

    # Get student's previous reports (last 10)
    my_reports = UserReport.query.filter_by(_student_id=student.id).order_by(UserReport.submitted_at.desc()).limit(10).all()

    return render_template('student_help_support.html',
                         current_page='help',
                         page_title='Help & Support',
                         my_reports=my_reports)
