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

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response

from forms import AdminSignupForm, SystemAdminInviteForm
from forms import StudentClaimAccountForm, StudentCreateUsernameForm, StudentPinPassphraseForm
from forms import StudentLoginForm, AdminLoginForm
from forms import PayrollSettingsForm, PayrollRewardForm, PayrollFineForm, ManualPaymentForm

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from calendar import monthrange
from functools import wraps
import pytz
from sqlalchemy import or_, func, text
import sqlalchemy as sa
# local security helpers
from hash_utils import (
    get_random_salt,
    hash_hmac,
    hash_username,
)
import json
import math
import os
import urllib.parse
from dotenv import load_dotenv
load_dotenv()

from forms import AdminTOTPConfirmForm

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet

PACIFIC = pytz.timezone('America/Los_Angeles')
utc = pytz.utc
import pyotp

# -------------------- UTILITIES (Temporary - will move to app/utils in Stage 5) --------------------
# PIIEncryptedType is now defined in app/models.py


def format_utc_iso(dt):
    """Return a UTC ISO-8601 string (with trailing Z) for a datetime or ``None``."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# -------------------- APPLICATION FACTORY --------------------
# Import and create the Flask application using the factory pattern
from app import create_app
from app.extensions import db, migrate, csrf

app = create_app()



# -------------------- MODELS --------------------
# Models have been moved to app/models.py (Stage 2 of refactor)
# Import all models here for backward compatibility
from app.models import (
    PIIEncryptedType,  # Utility type, will move to app/utils in Stage 5
    Student,
    AdminInviteCode,
    SystemAdmin,
    Transaction,
    TapEvent,
    HallPassLog,
    StoreItem,
    StudentItem,
    RentSettings,
    RentPayment,
    InsurancePolicy,
    StudentInsurance,
    InsuranceClaim,
    ErrorLog,
    Admin,
    PayrollSettings,
    PayrollReward,
    PayrollFine
)
# -------------------- AUTH UTILITIES --------------------
# Auth decorators and helpers have been moved to app/auth.py (Stage 3 of refactor)
# Import them here for backward compatibility
from app.auth import (
    SESSION_TIMEOUT_MINUTES,
    login_required,
    admin_required,
    system_admin_required,
    get_logged_in_student
)


# -------------------- FLASK CLI AND HOOKS --------------------
# after your models are defined but before you start serving requests
from flask.cli import with_appcontext

# Future-proof: No default admin with password for TOTP-only flow.
def ensure_default_admin():


    """Placeholder: No default admin created for TOTP-only auth."""
    app.logger.info("🛡️ ensure_default_admin: TOTP-only mode, no default admin created.")




# ---- Flask CLI command to manually ensure default admin ----
@app.cli.command("ensure-admin")
@with_appcontext
def ensure_admin_command():
    """Create the default admin user if credentials are provided."""
    with app.app_context():
        ensure_default_admin()


# Automatically create the default admin before the application starts serving
# requests in case migrations ran but the CLI command was not executed
# (e.g. on Azure). Use ``before_serving`` when available (Flask >=2.3),
# otherwise fall back to ``before_first_request`` for older Flask versions.

_admin_checked = False

def _run_admin_check():
    """Ensure the default admin exists but only run once."""
    global _admin_checked
    if not _admin_checked:
        ensure_default_admin()
        _admin_checked = True

if hasattr(app, "before_serving"):
    @app.before_serving
    def create_default_admin_if_needed():
        _run_admin_check()
elif hasattr(app, "before_first_request"):
    @app.before_first_request
    def create_default_admin_if_needed():
        _run_admin_check()
else:
    @app.before_request
    def create_default_admin_if_needed():
        _run_admin_check()


@app.context_processor
def inject_payroll_status():
    """Make payroll settings status available in all templates."""
    has_payroll_settings = PayrollSettings.query.first() is not None
    return dict(has_payroll_settings=has_payroll_settings)


# -------------------- ERROR LOGGING UTILITIES --------------------
import traceback
import collections

def get_last_log_lines(num_lines=50):
    """
    Get the last N lines from the log file.
    Returns a string with the last N lines, or an error message if the log file cannot be read.
    """
    log_file_path = os.getenv("LOG_FILE", "app.log")

    # For non-production environments (no log file), return recent logs from memory
    if os.getenv("FLASK_ENV", app.config.get("ENV")) != "production":
        return "[Log file only available in production mode]"

    try:
        if not os.path.exists(log_file_path):
            return f"[Log file not found at {log_file_path}]"

        # Use deque for efficient tail operation
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            last_lines = collections.deque(f, maxlen=num_lines)

        return ''.join(last_lines)
    except Exception as e:
        return f"[Error reading log file: {str(e)}]"


def log_error_to_db(error_type=None, error_message=None, stack_trace=None, log_output=None):
    """
    Save error information to the database for later review.
    This function should not raise exceptions to avoid recursive error loops.
    """
    try:
        # Get request information if available
        request_path = request.path if request else None
        request_method = request.method if request else None
        user_agent = request.headers.get('User-Agent', None) if request else None
        ip_address = request.remote_addr if request else None

        # Get log output
        if log_output is None:
            log_output = get_last_log_lines(50)

        # Create error log entry
        error_log = ErrorLog(
            timestamp=datetime.utcnow(),
            error_type=error_type,
            error_message=error_message,
            request_path=request_path,
            request_method=request_method,
            user_agent=user_agent,
            ip_address=ip_address,
            log_output=log_output,
            stack_trace=stack_trace
        )

        db.session.add(error_log)
        db.session.commit()

        return error_log.id
    except Exception as e:
        # Log to app logger but don't raise - we don't want error logging to cause more errors
        app.logger.error(f"Failed to log error to database: {str(e)}")
        return None


@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 Internal Server Error.
    Logs the error to the database and displays a user-friendly error page.
    """
    # Get error details
    error_type = type(error).__name__
    error_message = str(error)
    stack_trace = traceback.format_exc()

    # Log to app logger
    app.logger.exception("500 Internal Server Error occurred")

    # Save to database
    error_id = log_error_to_db(
        error_type=error_type,
        error_message=error_message,
        stack_trace=stack_trace
    )

    # Rollback any pending database changes
    db.session.rollback()

    # Get log output for display
    log_output = get_last_log_lines(50)

    # Render error page
    return render_template(
        'error_500.html',
        error_id=error_id,
        error_type=error_type,
        error_message=error_message,
        log_output=log_output,
        support_email='timothy.cs.chang@gmail.com'
    ), 500


@app.errorhandler(404)
def not_found_error(error):
    """
    Handle 404 Not Found Error.
    Displays a user-friendly page with navigation help.
    Rate-limited database logging to prevent spam from bots/typos.
    """
    app.logger.warning(f"404 Not Found: {request.url}")

    # Rate-limited logging: only log unique 404s once per hour
    cache_key = f"404_{request.path}"
    if not hasattr(app, '_404_cache'):
        app._404_cache = {}

    # Clean old entries (older than 1 hour)
    current_time = datetime.utcnow()
    app._404_cache = {k: v for k, v in app._404_cache.items()
                      if (current_time - v).total_seconds() < 3600}

    # Log to database if not recently logged
    if cache_key not in app._404_cache:
        log_error_to_db(
            error_type='404 Not Found',
            error_message=f"Page not found: {request.path}",
            stack_trace=None
        )
        app._404_cache[cache_key] = current_time

    return render_template(
        'error_404.html',
        request_url=request.url
    ), 404


@app.errorhandler(403)
def forbidden_error(error):
    """
    Handle 403 Forbidden Error.
    Displays a user-friendly page with permission troubleshooting.
    Logs to database to track potential security issues.
    """
    app.logger.warning(f"403 Forbidden: {request.url}")

    # Log to database - permission errors could indicate security issues
    log_error_to_db(
        error_type='403 Forbidden',
        error_message=f"Access forbidden: {request.path}",
        stack_trace=None
    )

    return render_template('error_403.html'), 403


@app.errorhandler(401)
def unauthorized_error(error):
    """
    Handle 401 Unauthorized Error.
    Displays a user-friendly page with login guidance.
    Logs to database to track authentication issues.
    """
    app.logger.warning(f"401 Unauthorized: {request.url}")

    # Log to database - authentication errors help identify session/auth issues
    log_error_to_db(
        error_type='401 Unauthorized',
        error_message=f"Authentication required: {request.path}",
        stack_trace=None
    )

    return render_template('error_401.html'), 401


@app.errorhandler(400)
def bad_request_error(error):
    """
    Handle 400 Bad Request Error.
    Displays a user-friendly page with input validation help.
    Logs to database to identify UX/validation issues.
    """
    error_msg = str(error.description) if hasattr(error, 'description') else str(error)
    app.logger.warning(f"400 Bad Request: {request.url} - {error_msg}")

    # Log to database - validation errors help identify UX issues
    log_error_to_db(
        error_type='400 Bad Request',
        error_message=f"Bad request on {request.path}: {error_msg}",
        stack_trace=None
    )

    return render_template(
        'error_400.html',
        error_message=error_msg
    ), 400


@app.errorhandler(503)
def service_unavailable_error(error):
    """
    Handle 503 Service Unavailable Error.
    Displays a user-friendly page for maintenance/downtime.
    Logs to database for service availability tracking.
    """
    app.logger.error(f"503 Service Unavailable: {request.url}")

    # Log to database - service availability is critical to track
    log_error_to_db(
        error_type='503 Service Unavailable',
        error_message=f"Service unavailable: {request.path}",
        stack_trace=None
    )

    return render_template('error_503.html'), 503


# -------------------- STUDENT SETUP FLOW --------------------
@app.route('/')
def home():
    return redirect(url_for('student_login'))  # Or wherever you want to go

# --- PAGE 1: Claim Account ---
@app.route('/student/claim-account', methods=['GET', 'POST'])
def student_claim_account():
    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        first_half = form.first_half.data.strip().lower()
        second_half = form.second_half.data.strip()

        if not second_half.isdigit():
            flash("DOB sum must be a number.", "claim")
            return redirect(url_for('student_claim_account'))

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

                return redirect(url_for('student_create_username'))

        flash("No matching account found. Please check your info.", "claim")
        return redirect(url_for('student_claim_account'))

    return render_template('student_account_claim.html', form=form)

# --- PAGE 2: Create Username ---
@app.route('/student/create-username', methods=['GET', 'POST'])
def student_create_username():
    import random, re
    from hash_utils import hash_username
    # Only allow if claimed
    student_id = session.get('claimed_student_id')
    if not student_id:
        flash("Please claim your account first.", "setup")
        return redirect(url_for('student_claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student_login'))
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
            return redirect(url_for('student_create_username'))
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
        return redirect(url_for('student_setup_pin_passphrase'))
    return render_template('student_create_username.html', theme_prompt=session['theme_prompt'], form=form)

# --- PAGE 3: Setup PIN & Passphrase ---
@app.route('/student/setup-pin-passphrase', methods=['GET', 'POST'])
def student_setup_pin_passphrase():
    from werkzeug.security import generate_password_hash
    # Only allow if claimed and username generated
    student_id = session.get('claimed_student_id')
    username = session.get('generated_username')
    if not student_id or not username:
        flash("Please complete previous steps.", "setup")
        return redirect(url_for('student_claim_account'))
    student = Student.query.get(student_id)
    if not student or student.has_completed_setup:
        flash("Invalid or already setup account.", "setup")
        return redirect(url_for('student_login'))
    form = StudentPinPassphraseForm()
    if form.validate_on_submit():
        pin = form.pin.data
        passphrase = form.passphrase.data
        if not pin or not passphrase:
            flash("PIN and passphrase are required.", "setup")
            return redirect(url_for('student_setup_pin_passphrase'))
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

@app.route('/setup-complete')
@login_required
def setup_complete():
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html')

# -------------------- STUDENT DASHBOARD --------------------


from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds

@app.route('/student/dashboard')
@login_required
def student_dashboard():
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
    app.logger.info(f"📊 DASHBOARD DEBUG: Student {student.id} - Block states:")
    for blk in student_blocks:
        blk_state = period_states[blk]
        active = blk_state["active"]
        done = blk_state["done"]
        seconds = blk_state["duration"]
        app.logger.info(f"Block {blk} => DB Active={active}, Done={done}, Seconds (today)={seconds}, Total Unpaid Seconds={unpaid_seconds_per_block.get(blk, 0)}")


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

# -------------------- TRANSFER ROUTE --------------------
@app.route('/student/transfer', methods=['GET', 'POST'])
@login_required
def student_transfer():
    student = get_logged_in_student()

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        passphrase = request.form.get("passphrase")
        if not check_password_hash(student.passphrase_hash or '', passphrase):
            if is_json:
                return jsonify(status="error", message="Incorrect passphrase"), 400
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student_transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        amount = float(request.form.get('amount'))

        if from_account == to_account:
            if is_json:
                return jsonify(status="error", message="Cannot transfer to the same account."), 400
            flash("Cannot transfer to the same account.", "transfer_error")
            return redirect(url_for("student_transfer"))
        elif amount <= 0:
            if is_json:
                return jsonify(status="error", message="Amount must be greater than 0."), 400
            flash("Amount must be greater than 0.", "transfer_error")
            return redirect(url_for("student_transfer"))
        elif from_account == 'checking' and amount > student.checking_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient checking funds."), 400
            flash("Insufficient checking funds.", "transfer_error")
            return redirect(url_for("student_transfer"))
        elif from_account == 'savings' and amount > student.savings_balance:
            if is_json:
                return jsonify(status="error", message="Insufficient savings funds."), 400
            flash("Insufficient savings funds.", "transfer_error")
            return redirect(url_for("student_transfer"))
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
                app.logger.info(
                    f"Transfer {amount} from {from_account} to {to_account} for student {student.id}"
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(
                    f"Transfer failed for student {student.id}: {e}", exc_info=True
                )
                if is_json:
                    return jsonify(status="error", message="Transfer failed."), 500
                flash("Transfer failed due to a database error.", "transfer_error")
                return redirect(url_for("student_transfer"))
            if is_json:
                return jsonify(status="success", message="Transfer completed successfully!")
            flash("Transfer completed successfully!", "transfer_success")
            return redirect(url_for('student_dashboard'))

    return render_template('student_transfer.html', student=student)

# -------------------- INSURANCE ROUTE --------------------
@app.route('/student/insurance', endpoint='student_insurance')
@login_required
def student_insurance_marketplace():
    """Insurance marketplace - browse and manage policies"""
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

@app.route('/student/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def student_purchase_insurance(policy_id):
    """Purchase insurance policy"""
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
        return redirect(url_for('student_insurance'))

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
            return redirect(url_for('student_insurance'))

        # Check for cooldown period (temporary restriction)
        if policy.enable_repurchase_cooldown and cancelled.cancel_date:
            days_since_cancel = (datetime.utcnow() - cancelled.cancel_date).days
            if days_since_cancel < policy.repurchase_wait_days:
                flash(f"You must wait {policy.repurchase_wait_days - days_since_cancel} more days before repurchasing this policy.", "warning")
                return redirect(url_for('student_insurance'))

    # Check sufficient funds
    if student.checking_balance < policy.premium:
        flash("Insufficient funds to purchase this insurance policy.", "danger")
        return redirect(url_for('student_insurance'))

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
    return redirect(url_for('student_insurance'))

@app.route('/student/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
def student_cancel_insurance(enrollment_id):
    """Cancel insurance policy"""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student_insurance'))

    enrollment.status = 'cancelled'
    enrollment.cancel_date = datetime.utcnow()

    db.session.commit()
    flash(f"Insurance policy '{enrollment.policy.title}' has been cancelled.", "info")
    return redirect(url_for('student_insurance'))

@app.route('/student/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def student_file_claim(policy_id):
    """File insurance claim"""
    from forms import InsuranceClaimForm

    student = get_logged_in_student()

    # Get student's enrollment for this policy
    enrollment = StudentInsurance.query.filter_by(
        student_id=student.id,
        policy_id=policy_id,
        status='active'
    ).first()

    if not enrollment:
        flash("You are not enrolled in this policy.", "danger")
        return redirect(url_for('student_insurance'))

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
                return redirect(url_for('student_file_claim', policy_id=policy_id))

            # Check max claim amount
            if policy.max_claim_amount and form.claim_amount.data > policy.max_claim_amount:
                flash(f"Claim amount cannot exceed ${policy.max_claim_amount:.2f}.", "danger")
                return redirect(url_for('student_file_claim', policy_id=policy_id))
        else:
            if not form.claim_item.data:
                flash("Claim item is required for non-monetary policies.", "danger")
                return redirect(url_for('student_file_claim', policy_id=policy_id))

        # Check claim time limit
        days_since_incident = (datetime.utcnow() - form.incident_date.data).days
        if days_since_incident > policy.claim_time_limit_days:
            flash(f"Claims must be filed within {policy.claim_time_limit_days} days of the incident.", "danger")
            return redirect(url_for('student_file_claim', policy_id=policy_id))

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
        return redirect(url_for('student_insurance'))

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

@app.route('/student/insurance/policy/<int:enrollment_id>')
@login_required
def student_view_policy(enrollment_id):
    """View policy details and claims history"""
    student = get_logged_in_student()
    enrollment = StudentInsurance.query.get_or_404(enrollment_id)

    # Verify ownership
    if enrollment.student_id != student.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('student_insurance'))

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


# -------------------- STUDENT SHOP --------------------
@app.route('/student/shop')
@login_required
def student_shop():
    student = get_logged_in_student()
    # Fetch active items that haven't passed their auto-delist date
    now = datetime.now(timezone.utc)
    items = StoreItem.query.filter(
        StoreItem.is_active == True,
        or_(StoreItem.auto_delist_date == None, StoreItem.auto_delist_date > now)
    ).order_by(StoreItem.name).all()

    return render_template('student_shop.html', student=student, items=items)


# -------------------- PURCHASE & REDEMPTION API --------------------
@app.route('/api/purchase-item', methods=['POST'])
@login_required
def purchase_item():
    student = get_logged_in_student()
    data = request.get_json()
    item_id = data.get('item_id')
    passphrase = data.get('passphrase')

    if not all([item_id, passphrase]):
        return jsonify({"status": "error", "message": "Missing item ID or passphrase."}), 400

    # 1. Verify passphrase
    if not check_password_hash(student.passphrase_hash or '', passphrase):
        return jsonify({"status": "error", "message": "Incorrect passphrase."}), 403

    item = StoreItem.query.get(item_id)

    # 2. Validate item and purchase conditions
    if not item or not item.is_active:
        return jsonify({"status": "error", "message": "This item is not available."}), 404

    if student.checking_balance < item.price:
        return jsonify({"status": "error", "message": "Insufficient funds."}), 400

    if item.inventory is not None and item.inventory <= 0:
        return jsonify({"status": "error", "message": "This item is out of stock."}), 400

    if item.limit_per_student is not None:
        if item.item_type == 'hall_pass':
            # For hall passes, check transaction history since no StudentItem is created
            purchase_count = Transaction.query.filter_by(
                student_id=student.id,
                type='purchase',
                description=f"Purchase: {item.name}"
            ).count()
        else:
            purchase_count = StudentItem.query.filter_by(student_id=student.id, store_item_id=item.id).count()
        if purchase_count >= item.limit_per_student:
            return jsonify({"status": "error", "message": "You have reached the purchase limit for this item."}), 400

    # 3. Process the transaction
    try:
        # Deduct from checking account
        purchase_tx = Transaction(
            student_id=student.id,
            amount=-item.price,
            account_type='checking',
            type='purchase',
            description=f"Purchase: {item.name}"
        )
        db.session.add(purchase_tx)

        # Handle inventory
        if item.inventory is not None:
            item.inventory -= 1

        # --- Handle special item type: Hall Pass ---
        if item.item_type == 'hall_pass':
            student.hall_passes += 1
            db.session.commit()
            return jsonify({"status": "success", "message": f"You purchased a Hall Pass! Your new balance is {student.hall_passes}."})

        # --- Standard Item Logic ---
        # Create the student's item
        expiry_date = None
        if item.item_type == 'delayed' and item.auto_expiry_days:
            expiry_date = datetime.now(timezone.utc) + timedelta(days=item.auto_expiry_days)

        student_item_status = 'purchased'
        if item.item_type == 'immediate':
            student_item_status = 'redeemed' # Immediate use items are redeemed instantly
        elif item.item_type == 'collective':
            student_item_status = 'pending'
        else: # delayed
            student_item_status = 'purchased'

        new_student_item = StudentItem(
            student_id=student.id,
            store_item_id=item.id,
            purchase_date=datetime.now(timezone.utc),
            expiry_date=expiry_date,
            status=student_item_status
        )
        db.session.add(new_student_item)
        db.session.commit()

        # --- Collective Item Logic ---
        if item.item_type == 'collective':
            # Check if all students in the same block have purchased this item
            students_in_block = Student.query.filter_by(block=student.block).all()
            student_ids_in_block = {s.id for s in students_in_block}

            purchased_students_count = db.session.query(func.count(func.distinct(StudentItem.student_id))).filter(
                StudentItem.store_item_id == item.id,
                StudentItem.student_id.in_(student_ids_in_block)
            ).scalar()

            if purchased_students_count >= len(student_ids_in_block):
                # Threshold met, update all pending items for this collective goal to processing
                StudentItem.query.filter(
                    StudentItem.store_item_id == item.id,
                    StudentItem.status == 'pending'
                ).update({"status": "processing"})
                db.session.commit()
                # This flash won't be seen by the user due to the JSON response,
                # but it's good for logging/debugging. A more robust solution might use websockets.
                app.logger.info(f"Collective goal '{item.name}' for block {student.block} has been met!")

        return jsonify({"status": "success", "message": f"You purchased {item.name}!"})

    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Purchase failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred during purchase. Please try again."}), 500


@app.route('/api/use-item', methods=['POST'])
@login_required
def use_item():
    student = get_logged_in_student()
    data = request.get_json()
    student_item_id = data.get('student_item_id')
    details = data.get('redemption_details')

    if not all([student_item_id, details]):
        return jsonify({"status": "error", "message": "Missing item ID or usage details."}), 400

    student_item = StudentItem.query.get(student_item_id)

    # 1. Validate the item
    if not student_item:
        return jsonify({"status": "error", "message": "Item not found."}), 404

    if student_item.student_id != student.id:
        return jsonify({"status": "error", "message": "You do not own this item."}), 403

    if student_item.store_item.item_type != 'delayed':
         return jsonify({"status": "error", "message": "This item cannot be used this way."}), 400

    if student_item.status != 'purchased':
        return jsonify({"status": "error", "message": f"This item cannot be used (status: {student_item.status})."}), 400

    if student_item.expiry_date and datetime.now(timezone.utc) > student_item.expiry_date:
        student_item.status = 'expired'
        db.session.commit()
        return jsonify({"status": "error", "message": "This item has expired."}), 400

    # 2. Process the redemption request
    try:
        student_item.status = 'processing'
        student_item.redemption_details = details
        student_item.redemption_date = datetime.now(timezone.utc)

        redemption_tx = Transaction(
            student_id=student.id,
            amount=0,
            account_type='checking',
            type='redemption',
            description=f"Used: {student_item.store_item.name}"
        )
        db.session.add(redemption_tx)

        db.session.commit()
        return jsonify({"status": "success", "message": f"Your request to use {student_item.store_item.name} has been submitted for approval."})

    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Item use failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred. Please try again."}), 500


# -------------------- TRANSFER ROUTE SUPPORT FUNCTIONS --------------------
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

# -------------------- RENT HELPERS --------------------

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


# -------------------- STUDENT RENT ROUTES --------------------
@app.route('/student/rent')
@login_required
def student_rent():
    """View rent status and payment history (per period)"""
    student = get_logged_in_student()
    settings = RentSettings.query.first()

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "info")
        return redirect(url_for('student_dashboard'))

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


@app.route('/student/rent/pay/<period>', methods=['POST'])
@login_required
def student_rent_pay(period):
    """Process rent payment for a specific period"""
    student = get_logged_in_student()
    settings = RentSettings.query.first()

    if not settings or not settings.is_enabled:
        flash("Rent system is currently disabled.", "error")
        return redirect(url_for('student_dashboard'))

    if not student.is_rent_enabled:
        flash("Rent is not enabled for your account.", "error")
        return redirect(url_for('student_dashboard'))

    # Validate period
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
    period = period.upper()
    if period not in student_blocks:
        flash("Invalid period.", "error")
        return redirect(url_for('student_rent'))

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
        return redirect(url_for('student_rent'))

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
        return redirect(url_for('student_rent'))

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
    return redirect(url_for('student_rent'))


# -------------------- STUDENT LOGIN --------------------
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
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
                return redirect(url_for('student_login', next=request.args.get('next')))
        except Exception as e:
            app.logger.error(f"Error during student login authentication: {str(e)}")
            if is_json:
                return jsonify(status="error", message="An error occurred during login. Please try again."), 500
            flash("An error occurred during login. Please try again.", "error")
            return redirect(url_for('student_login'))

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
            return redirect(url_for('student_dashboard'))
        return redirect(next_url or url_for('student_dashboard'))

    # Always display CTA to claim/create account for first-time users
    setup_cta = True
    return render_template('student_login.html', setup_cta=setup_cta, form=form)

# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    from payroll import calculate_payroll
    from attendance import get_last_payroll_time

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

@app.route('/api/approve-redemption', methods=['POST'])
@admin_required
def approve_redemption():
    data = request.get_json()
    student_item_id = data.get('student_item_id')

    student_item = StudentItem.query.get(student_item_id)
    if not student_item or student_item.status != 'processing':
        return jsonify({"status": "error", "message": "Invalid or already processed item."}), 404

    try:
        student_item.status = 'completed'

        # Find the corresponding 'redemption' transaction and update its description
        redemption_tx = Transaction.query.filter_by(
            student_id=student_item.student_id,
            type='redemption',
            description=f"Used: {student_item.store_item.name}"
        ).order_by(Transaction.timestamp.desc()).first()

        if redemption_tx:
            redemption_tx.description = f"Redeemed: {student_item.store_item.name}"

        db.session.commit()
        return jsonify({"status": "success", "message": "Redemption approved."})
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Redemption approval failed for student_item {student_item_id}: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An error occurred."}), 500


@app.route('/admin/bonuses', methods=['POST'])
@admin_required
def give_bonus_all():
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
    return redirect(url_for('admin_dashboard'))

# -------------------- ADMIN LOGIN (TOTP-ONLY) --------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
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
                app.logger.info(f"✅ Admin login success for {username}")
                flash("Admin login successful.")
                next_url = request.args.get("next")
                if not is_safe_url(next_url):
                    return redirect(url_for("admin_dashboard"))
                return redirect(next_url or url_for("admin_dashboard"))
        app.logger.warning(f"🔑 Admin login failed for {username}")
        flash("Invalid credentials or TOTP code.", "error")
        return redirect(url_for("admin_login", next=request.args.get("next")))
    return render_template("admin_login.html", form=form)

# -------------------- ADMIN SIGNUP (TOTP-ONLY) --------------------
@app.route('/admin/signup', methods=['GET', 'POST'])
def admin_signup():
    """
    TOTP-only admin registration. Requires valid invite code.
    Uses AdminSignupForm for CSRF and validation.
    """
    import io, base64, qrcode
    from sqlalchemy import text
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
            app.logger.warning(f"🛑 Admin signup failed: invalid invite code")
            msg = "Invalid invite code."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin_signup'))
        if code_row.used:
            app.logger.warning(f"🛑 Admin signup failed: invite code already used")
            msg = "Invite code already used."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin_signup'))
        if code_row.expires_at and code_row.expires_at < datetime.utcnow():
            app.logger.warning(f"🛑 Admin signup failed: invite code expired")
            msg = "Invite code expired."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin_signup'))
        # Step 2: Check username uniqueness
        if Admin.query.filter_by(username=username).first():
            app.logger.warning(f"🛑 Admin signup failed: username already exists")
            msg = "Username already exists."
            if is_json:
                return jsonify(status="error", message=msg), 400
            flash(msg, "error")
            return redirect(url_for('admin_signup'))
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
            app.logger.info(f"🔐 Admin signup: showing QR for {username}")
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
            app.logger.warning(f"🛑 Admin signup failed: invalid TOTP code for {username}")
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
        app.logger.info(f"🎯 Admin signup: TOTP secret being saved for {username}")
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
        app.logger.info(f"🎉 Admin signup: {username} created successfully via invite")
        msg = "Admin account created successfully! Please log in using your authenticator app."
        if is_json:
            return jsonify(status="success", message=msg)
        flash(msg, "success")
        return redirect(url_for("admin_login"))
    # GET or invalid POST: render signup form with form instance (for CSRF)
    return render_template("admin_signup.html", form=form)

@app.route('/admin/logout')
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.")
    return redirect(url_for("admin_login"))


@app.route('/admin/students')
@admin_required
def admin_students():
    students = Student.query.order_by(Student.block, Student.first_name).all()
    # Remove deprecated last_tap_in/last_tap_out logic; templates should not reference them.
    return render_template('admin_students.html', students=students, current_page="students")


# -------------------- ADMIN STORE MANAGEMENT --------------------
from forms import StoreItemForm
@app.route('/admin/store', methods=['GET', 'POST'])
@admin_required
def admin_store_management():
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
        return redirect(url_for('admin_store_management'))

    items = StoreItem.query.order_by(StoreItem.name).all()
    return render_template('admin_store.html', form=form, items=items, current_page="store")


@app.route('/admin/store/edit/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_store_item(item_id):
    item = StoreItem.query.get_or_404(item_id)
    form = StoreItemForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        db.session.commit()
        flash(f"'{item.name}' has been updated.", "success")
        return redirect(url_for('admin_store_management'))
    return render_template('admin_edit_item.html', form=form, item=item, current_page="store")

@app.route('/admin/store/delete/<int:item_id>', methods=['POST'])
@admin_required
def admin_delete_store_item(item_id):
    item = StoreItem.query.get_or_404(item_id)
    # To preserve history, we'll just deactivate it instead of a hard delete
    # A hard delete would be: db.session.delete(item)
    item.is_active = False
    db.session.commit()
    flash(f"'{item.name}' has been deactivated and removed from the store.", "success")
    return redirect(url_for('admin_store_management'))

# -------------------- RENT SETTINGS ROUTES --------------------
@app.route('/admin/rent-settings', methods=['GET', 'POST'])
@admin_required
def admin_rent_settings():
    """Configure rent settings"""
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
        return redirect(url_for('admin_rent_settings'))

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

# -------------------- INSURANCE ROUTES --------------------

@app.route('/admin/insurance', methods=['GET', 'POST'])
@admin_required
def admin_insurance_management():
    """Main insurance management dashboard"""
    from forms import InsurancePolicyForm

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
        return redirect(url_for('admin_insurance_management'))

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

@app.route('/admin/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_insurance_policy(policy_id):
    """Edit existing insurance policy"""
    from forms import InsurancePolicyForm

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
        return redirect(url_for('admin_insurance_management'))

    # Get other active policies for bundle selection (excluding current policy)
    available_policies = InsurancePolicy.query.filter(
        InsurancePolicy.is_active == True,
        InsurancePolicy.id != policy_id
    ).all()

    return render_template('admin_edit_insurance_policy.html', form=form, policy=policy, available_policies=available_policies)

@app.route('/admin/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
def admin_deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy"""
    policy = InsurancePolicy.query.get_or_404(policy_id)
    policy.is_active = False
    db.session.commit()
    flash(f"Insurance policy '{policy.title}' has been deactivated.", "success")
    return redirect(url_for('admin_insurance_management'))

@app.route('/admin/insurance/student-policy/<int:enrollment_id>')
@admin_required
def admin_view_student_policy(enrollment_id):
    """View student's policy enrollment details and claims history"""
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

@app.route('/admin/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def admin_process_claim(claim_id):
    """Process insurance claim with auto-deposit for monetary claims"""
    from forms import AdminClaimProcessForm

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
        return redirect(url_for('admin_insurance_management'))

    return render_template('admin_process_claim.html',
                          claim=claim,
                          form=form,
                          enrollment=enrollment,
                          validation_errors=validation_errors,
                          claims_stats=claims_stats)

@app.route('/admin/transactions')
@admin_required
def admin_transactions():
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


@app.route('/admin/students/<int:student_id>')
@admin_required
def student_detail(student_id):
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


@app.route('/admin/void-transaction/<int:transaction_id>', methods=['POST'])
@admin_required
def void_transaction(transaction_id):
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    tx = Transaction.query.get_or_404(transaction_id)
    tx.is_void = True
    try:
        db.session.commit()
        app.logger.info(f"Transaction {transaction_id} voided")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Failed to void transaction {transaction_id}: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Failed to void transaction"), 500
        flash("Error voiding transaction.", "error")
        return redirect(request.referrer or url_for('admin_dashboard'))
    if is_json:
        return jsonify(status="success", message="Transaction voided.")
    flash("✅ Transaction voided.", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))


# -------------------- ADMIN HALL PASS MANAGEMENT --------------------
@app.route('/admin/hall-pass')
@admin_required
def admin_hall_pass():
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

@app.route('/api/hall-pass/<int:pass_id>/<string:action>', methods=['POST'])
@admin_required
def handle_hall_pass_action(pass_id, action):
    log_entry = HallPassLog.query.get_or_404(pass_id)
    student = log_entry.student
    now = datetime.now(timezone.utc)

    if action == 'approve':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        # Check if hall pass deduction is needed (not for Office/Summons/Done for the day)
        should_deduct = log_entry.reason.lower() not in ['office', 'summons', 'done for the day']

        if should_deduct and student.hall_passes <= 0:
            return jsonify({"status": "error", "message": "Student has no hall passes left."}), 400

        # Generate unique pass number (letter + 2 digits)
        import random
        import string
        while True:
            letter = random.choice(string.ascii_uppercase)
            digits = random.randint(10, 99)
            pass_number = f"{letter}{digits}"
            # Check if this pass number already exists
            existing = HallPassLog.query.filter_by(pass_number=pass_number).first()
            if not existing:
                break

        log_entry.status = 'approved'
        log_entry.decision_time = now
        log_entry.pass_number = pass_number

        # Only deduct hall pass for regular reasons (not Office/Summons/Done for the day)
        if should_deduct:
            student.hall_passes -= 1

        db.session.commit()
        return jsonify({"status": "success", "message": "Pass approved.", "pass_number": pass_number})

    elif action == 'reject':
        if log_entry.status != 'pending':
            return jsonify({"status": "error", "message": "Pass is not pending."}), 400

        log_entry.status = 'rejected'
        log_entry.decision_time = now
        db.session.commit()
        return jsonify({"status": "success", "message": "Pass rejected."})

    elif action == 'leave':
        if log_entry.status != 'approved':
            return jsonify({"status": "error", "message": "Pass is not approved."}), 400

        # Create a tap-out event for attendance tracking
        tap_out_event = TapEvent(
            student_id=student.id,
            period="HALLPASS", # Use a special period for hall pass events
            status='inactive',
            timestamp=now,
            reason=log_entry.reason
        )
        log_entry.status = 'left'
        log_entry.left_time = now
        db.session.add(tap_out_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has left the class."})

    elif action == 'return':
        if log_entry.status != 'left':
            return jsonify({"status": "error", "message": "Student is not out of class."}), 400

        # Create a tap-in event to close the loop
        tap_in_event = TapEvent(
            student_id=student.id,
            period="HALLPASS",
            status='active',
            timestamp=now,
            reason="Return from hall pass"
        )
        log_entry.status = 'returned'
        log_entry.return_time = now
        db.session.add(tap_in_event)
        db.session.commit()
        return jsonify({"status": "success", "message": "Student has returned."})

    return jsonify({"status": "error", "message": "Invalid action."}), 400

@app.route('/admin/student/<int:student_id>/set-hall-passes', methods=['POST'])
@admin_required
def set_hall_passes(student_id):
    student = Student.query.get_or_404(student_id)
    new_balance = request.form.get('hall_passes', type=int)

    if new_balance is not None and new_balance >= 0:
        student.hall_passes = new_balance
        db.session.commit()
        flash(f"Successfully updated {student.full_name}'s hall pass balance to {new_balance}.", "success")
    else:
        flash("Invalid hall pass balance provided.", "error")

    return redirect(url_for('student_detail', student_id=student_id))

# -------------------- HALL PASS TERMINAL & VERIFICATION PAGES --------------------
@app.route('/hall-pass/terminal')
def hall_pass_terminal():
    """Hall Pass Check in/out terminal page (no login required)"""
    return render_template('hall_pass_terminal.html')

@app.route('/hall-pass/verification')
def hall_pass_verification():
    """Hall Pass Verification page for display (no login required)"""
    return render_template('hall_pass_verification.html')

@app.route('/api/hall-pass/verification/active', methods=['GET'])
def get_active_hall_passes():
    """Get last 10 students who used hall passes for verification display"""
    # Get the last 10 students who have left class (both currently out and recently returned)
    # Ordered by left_time descending (most recent first)
    recent_passes = HallPassLog.query.filter(
        HallPassLog.status.in_(['left', 'returned']),
        HallPassLog.left_time.isnot(None)
    ).order_by(HallPassLog.left_time.desc()).limit(10).all()

    # Helper function to ensure times are marked as UTC
    def format_utc_time(dt):
        if not dt:
            return None
        # Ensure datetime is treated as UTC
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    passes_data = []
    for log_entry in recent_passes:
        student = log_entry.student
        passes_data.append({
            "student_name": student.full_name,
            "period": log_entry.period,
            "destination": log_entry.reason,
            "left_time": format_utc_time(log_entry.left_time),
            "return_time": format_utc_time(log_entry.return_time),
            "pass_number": log_entry.pass_number,
            "status": log_entry.status
        })

    return jsonify({
        "status": "success",
        "passes": passes_data
    })

# -------------------- HALL PASS TERMINAL API --------------------
# These endpoints are used by the hall pass terminal (no login required)

@app.route('/api/hall-pass/lookup/<string:pass_number>', methods=['GET'])
def lookup_hall_pass(pass_number):
    """Look up a hall pass by its pass number (for terminal use)"""
    # Find the hall pass log entry by pass number
    log_entry = HallPassLog.query.filter_by(pass_number=pass_number.upper()).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Pass number not found."}), 404

    student = log_entry.student

    # Return the pass information (ensure times are marked as UTC)
    def format_utc_time(dt):
        if not dt:
            return None
        # Ensure datetime is treated as UTC
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return jsonify({
        "status": "success",
        "pass_id": log_entry.id,
        "student_name": student.full_name,
        "period": log_entry.period,
        "destination": log_entry.reason,
        "request_time": format_utc_time(log_entry.request_time),
        "pass_status": log_entry.status,
        "left_time": format_utc_time(log_entry.left_time),
        "return_time": format_utc_time(log_entry.return_time)
    })

@app.route('/api/hall-pass/terminal/use', methods=['POST'])
def terminal_use_hall_pass():
    """Student uses hall pass at terminal (check-in to leave class)"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    # Find the hall pass log entry
    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Pass number not found."}), 404

    # Check if pass is approved
    if log_entry.status != 'approved':
        return jsonify({
            "status": "error",
            "message": f"Pass is not approved. Current status: {log_entry.status}"
        }), 400

    student = log_entry.student
    now = datetime.now(timezone.utc)

    # Update status to "left"
    log_entry.status = 'left'
    log_entry.left_time = now

    # Create a tap-out event to stop time counting
    tap_out_event = TapEvent(
        student_id=student.id,
        period=log_entry.period,
        status='inactive',
        timestamp=now,
        reason=f"Hall pass: {log_entry.reason}"
    )
    db.session.add(tap_out_event)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Hall pass activated. Student has left the class.",
        "student_name": student.full_name,
        "destination": log_entry.reason
    })

@app.route('/api/hall-pass/terminal/return', methods=['POST'])
def terminal_return_hall_pass():
    """Student returns from hall pass at terminal (check-out when returning)"""
    data = request.get_json()
    pass_number = data.get('pass_number', '').upper()

    if not pass_number:
        return jsonify({"status": "error", "message": "Pass number is required."}), 400

    # Find the hall pass log entry
    log_entry = HallPassLog.query.filter_by(pass_number=pass_number).first()

    if not log_entry:
        return jsonify({"status": "error", "message": "Pass number not found."}), 404

    # Check if student has left
    if log_entry.status != 'left':
        return jsonify({
            "status": "error",
            "message": f"Cannot return - pass status is {log_entry.status}, not 'left'."
        }), 400

    student = log_entry.student
    now = datetime.now(timezone.utc)

    # Update status to "returned"
    log_entry.status = 'returned'
    log_entry.return_time = now

    # Create a tap-in event to start time counting again
    tap_in_event = TapEvent(
        student_id=student.id,
        period=log_entry.period,
        status='active',
        timestamp=now,
        reason="Return from hall pass"
    )
    db.session.add(tap_in_event)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Student has returned to class.",
        "student_name": student.full_name
    })


# -------------------- ADMIN PAYROLL HISTORY --------------------
@app.route('/admin/payroll-history')
@admin_required
def admin_payroll_history():
    app.logger.info("🧭 Entered admin_payroll_history route")
    from sqlalchemy import desc
    from datetime import datetime, timedelta

    block = request.args.get("block")
    app.logger.info(f"📊 Block filter: {block}")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    app.logger.info(f"📅 Date filters: start={start_date_str}, end={end_date_str}")

    query = Transaction.query.filter_by(type="payroll")

    if block:
        # Stream students in batches for this block
        student_ids = [s.id for s in Student.query.filter_by(block=block).yield_per(50).all()]
        app.logger.info(f"👥 Student IDs in block '{block}': {student_ids}")
        query = query.filter(Transaction.student_id.in_(student_ids))

    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        query = query.filter(Transaction.timestamp >= start_date)

    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)

    payroll_transactions = query.order_by(desc(Transaction.timestamp)).all()
    app.logger.info(f"🔎 Payroll transactions found: {len(payroll_transactions)}")

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

    app.logger.info(f"📄 Payroll records prepared: {len(payroll_records)}")

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


from payroll import calculate_payroll

# -------------------- ADMIN RUN PAYROLL MANUALLY --------------------
@app.route('/admin/run-payroll', methods=['POST'])
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
        app.logger.info(f"🧮 RUN PAYROLL: Last payroll at {last_payroll_time}")

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
        app.logger.info(f"✅ Payroll complete. Paid {len(summary)} students.")
        if is_json:
            return jsonify(status="success", message=f"Payroll complete. Paid {len(summary)} students.")
        flash(f"✅ Payroll complete. Paid {len(summary)} students.", "admin_success")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"❌ Payroll error: {e}", exc_info=True)
        if is_json:
            return jsonify(status="error", message="Payroll error occurred. Check logs."), 500
        flash("Payroll error occurred. Check logs.", "admin_error")
    if not is_json:
        return redirect(url_for('admin_dashboard'))

# -------------------- ADMIN PAYROLL PAGE --------------------
@app.route('/admin/payroll')
@admin_required
def admin_payroll():
    """
    Enhanced payroll page with tabs for settings, students, rewards, fines, and manual payments.
    """
    from sqlalchemy import desc
    from datetime import datetime, timedelta, timezone
    import pytz
    from payroll import calculate_payroll
    from attendance import calculate_unpaid_attendance_seconds

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


# -------------------- PAYROLL SETTINGS --------------------
@app.route('/admin/payroll/settings', methods=['POST'])
@admin_required
def admin_payroll_settings():
    """Save payroll settings for a block or globally (Simple or Advanced mode)."""
    from datetime import datetime, timezone, timedelta

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
        app.logger.error(f"Error saving payroll settings: {e}")
        flash(f'Error saving payroll settings: {str(e)}', 'error')

    return redirect(url_for('admin_payroll'))


# -------------------- PAYROLL REWARDS --------------------
@app.route('/admin/payroll/rewards/add', methods=['POST'])
@admin_required
def admin_payroll_add_reward():
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
            app.logger.error(f"Error creating reward: {e}")
            flash('Error creating reward. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin_payroll'))


@app.route('/admin/payroll/rewards/<int:reward_id>/delete', methods=['POST'])
@admin_required
def admin_payroll_delete_reward(reward_id):
    """Delete a payroll reward."""
    try:
        reward = PayrollReward.query.get_or_404(reward_id)
        db.session.delete(reward)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reward deleted successfully'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting reward: {e}")
        return jsonify({'success': False, 'message': 'Error deleting reward'}), 500


# -------------------- PAYROLL FINES --------------------
@app.route('/admin/payroll/fines/add', methods=['POST'])
@admin_required
def admin_payroll_add_fine():
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
            app.logger.error(f"Error creating fine: {e}")
            flash('Error creating fine. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin_payroll'))


@app.route('/admin/payroll/fines/<int:fine_id>/delete', methods=['POST'])
@admin_required
def admin_payroll_delete_fine(fine_id):
    """Delete a payroll fine."""
    try:
        fine = PayrollFine.query.get_or_404(fine_id)
        db.session.delete(fine)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine deleted successfully'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting fine: {e}")
        return jsonify({'success': False, 'message': 'Error deleting fine'}), 500


# -------------------- EDIT REWARDS & FINES --------------------
@app.route('/admin/payroll/rewards/<int:reward_id>/edit', methods=['POST'])
@admin_required
def admin_payroll_edit_reward(reward_id):
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
        app.logger.error(f"Error editing reward: {e}")
        return jsonify({'success': False, 'message': 'Error editing reward'}), 500


@app.route('/admin/payroll/fines/<int:fine_id>/edit', methods=['POST'])
@admin_required
def admin_payroll_edit_fine(fine_id):
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
        app.logger.error(f"Error editing fine: {e}")
        return jsonify({'success': False, 'message': 'Error editing fine'}), 500


# -------------------- VOID TRANSACTIONS --------------------
@app.route('/admin/payroll/transactions/<int:transaction_id>/void', methods=['POST'])
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
        app.logger.error(f"Error voiding transaction: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transaction'}), 500


@app.route('/admin/payroll/transactions/void-bulk', methods=['POST'])
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
        app.logger.error(f"Error voiding transactions in bulk: {e}")
        return jsonify({'success': False, 'message': 'Error voiding transactions'}), 500


# -------------------- APPLY REWARDS & FINES --------------------
@app.route('/admin/payroll/rewards/<int:reward_id>/apply', methods=['POST'])
@admin_required
def admin_payroll_apply_reward(reward_id):
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
        app.logger.error(f"Error applying reward: {e}")
        return jsonify({'success': False, 'message': 'Error applying reward'}), 500


@app.route('/admin/payroll/fines/<int:fine_id>/apply', methods=['POST'])
@admin_required
def admin_payroll_apply_fine(fine_id):
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
        app.logger.error(f"Error applying fine: {e}")
        return jsonify({'success': False, 'message': 'Error applying fine'}), 500


# -------------------- MANUAL PAYMENTS --------------------
@app.route('/admin/payroll/manual-payment', methods=['POST'])
@admin_required
def admin_payroll_manual_payment():
    """Send manual payments to selected students."""
    form = ManualPaymentForm()

    if form.validate_on_submit():
        try:
            student_ids = request.form.getlist('student_ids')

            if not student_ids:
                flash('Please select at least one student.', 'warning')
                return redirect(url_for('admin_payroll'))

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
            app.logger.error(f"Error sending manual payments: {e}")
            flash('Error sending manual payments. Please try again.', 'error')
    else:
        flash('Invalid form data. Please check your inputs.', 'error')

    return redirect(url_for('admin_payroll'))


@app.route('/student/logout')
@login_required
def student_logout():
    session.pop('student_id', None)
    flash("You've been logged out.")
    return redirect(url_for('student_login'))


# -------------------- ADMIN FULL ATTENDANCE LOG --------------------
@app.route('/admin/attendance-log')
@admin_required
def admin_attendance_log():
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

@app.route('/admin/upload-students', methods=['POST'])
@admin_required
def admin_upload_students():
    import csv, io, os, re
    from datetime import datetime

    file = request.files.get('csv_file')
    if not file:
        flash("No file provided", "admin_error")
        return redirect(url_for('admin_students'))

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
                app.logger.info(f"Duplicate detected: {first_name} {last_initial} in block {block}, skipping.")
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
            app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
            errors += 1

    try:
        db.session.commit()
        flash(f"{added_count} students added successfully<br>{errors} students cannot be added<br>{duplicated} duplicated students skipped.", "admin_success")
    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {e}", "admin_error")
        app.logger.error(f"Upload commit failed: {e}", exc_info=True)

    return redirect(url_for('admin_students'))

@app.route('/admin/download-csv-template')
@admin_required
def download_csv_template():
    """
    Serves the updated student_upload_template.csv from the project root.
    """
    from flask import send_file
    import os

    template_path = os.path.join(os.getcwd(), "student_upload_template.csv")
    return send_file(template_path, as_attachment=True, download_name="student_upload_template.csv", mimetype='text/csv')


@app.route('/admin/export-students')
@admin_required
def export_students():
    """Export all student data to CSV"""
    import csv
    import io

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


# --- Append-only TapEvent API route ---
@app.route('/api/tap', methods=['POST'])
def handle_tap():
    print("🛠️ TAP ROUTE HIT")
    data = request.get_json()
    safe_data = {k: ('***' if k == 'pin' else v) for k, v in data.items()}
    app.logger.info(f"TAP DEBUG: Received data {safe_data}")

    student = get_logged_in_student()

    if not student:
        app.logger.warning("TAP ERROR: Unauthenticated tap attempt.")
        return jsonify({"error": "User not logged in or session expired"}), 401

    pin = data.get("pin", "").strip()


    if not check_password_hash(student.pin_hash or '', pin):
        app.logger.warning(f"TAP ERROR: Invalid PIN for student {student.id}")
        return jsonify({"error": "Invalid PIN"}), 403


    valid_periods = [b.strip().upper() for b in student.block.split(',') if b.strip()] if student and isinstance(student.block, str) else []
    period = data.get("period", "").upper()
    action = data.get("action")

    app.logger.info(f"TAP DEBUG: student_id={getattr(student, 'id', None)}, valid_periods={valid_periods}, period={period}, action={action}")

    if period not in valid_periods or action not in ["tap_in", "tap_out"]:
        app.logger.warning(f"TAP ERROR: Invalid period or action: period={period}, valid_periods={valid_periods}, action={action}")
        return jsonify({"error": "Invalid period or action"}), 400

    now = datetime.now(timezone.utc)


    # --- Hall Pass Logic for Tap Out ---
    if action == 'tap_out':
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "A reason is required for a hall pass."}), 400

        # Special case for "Done for the day" - this is the old "tap out" behavior
        if reason.lower() in ['done', 'done for the day']:
            # Fall through to the standard TapEvent creation logic below
            pass
        else:
            # All other reasons go through the hall pass approval flow
            # Check if hall pass is required (not for Office/Summons/Done for the day)
            should_require_pass = reason.lower() not in ['office', 'summons', 'done for the day']

            if should_require_pass and student.hall_passes <= 0:
                return jsonify({"error": "Insufficient hall passes."}), 400

            # Create a hall pass log entry
            hall_pass_log = HallPassLog(
                student_id=student.id,
                reason=reason,
                period=period,
                status='pending',
                request_time=now
            )
            db.session.add(hall_pass_log)
            db.session.commit()

            # Since the student is just requesting, they are still 'active'.
            # We need to return the current state to the UI.
            is_active = True
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)
            RATE_PER_SECOND = 0.25 / 60
            projected_pay = duration * RATE_PER_SECOND

            return jsonify({
                "status": "ok",
                "message": "Hall pass requested.",
                "active": is_active,
                "duration": duration,
                "projected_pay": projected_pay
            })

    # --- Standard Tap In/Out Logic ---
    try:
        status = "active" if action == "tap_in" else "inactive"
        reason = data.get("reason") if action == "tap_out" else None

        # Prevent duplicate tap-in or tap-out
        latest_event = (
            TapEvent.query
            .filter_by(student_id=student.id, period=period)
            .order_by(TapEvent.timestamp.desc())
            .first()
        )
        if latest_event and latest_event.status == status:
            app.logger.info(f"Duplicate {action} ignored for student {student.id} in period {period}")
            last_payroll_time = get_last_payroll_time()
            duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)
            return jsonify({
                "status": "ok",
                "active": latest_event.status == "active",
                "duration": duration
            })

        # When tapping in, automatically return any active hall pass
        if action == "tap_in":
            active_hall_pass = HallPassLog.query.filter_by(
                student_id=student.id,
                period=period,
                status='left'
            ).order_by(HallPassLog.request_time.desc()).first()

            if active_hall_pass:
                active_hall_pass.status = 'returned'
                active_hall_pass.return_time = now
                app.logger.info(f"Auto-returned hall pass {active_hall_pass.id} for student {student.id}")

        event = TapEvent(
            student_id=student.id,
            period=period,
            status=status,
            timestamp=now,  # UTC-aware
            reason=reason
        )
        db.session.add(event)
        db.session.commit()
        app.logger.info(f"TAP success - student {student.id} {period} {action}")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"TAP failed for student {student.id}: {e}", exc_info=True)
        return jsonify({"error": "Database error"}), 500

    # Fetch latest status and unpaid duration for the tapped period
    latest_event = (
        TapEvent.query
        .filter_by(student_id=student.id, period=period)
        .order_by(TapEvent.timestamp.desc())
        .first()
    )
    is_active = latest_event.status == "active" if latest_event else False
    last_payroll_time = get_last_payroll_time()
    duration = calculate_unpaid_attendance_seconds(student.id, period, last_payroll_time)

    RATE_PER_SECOND = 0.25 / 60
    projected_pay = duration * RATE_PER_SECOND

    return jsonify({
        "status": "ok",
        "active": is_active,
        "duration": duration,
        "projected_pay": projected_pay
    })


from attendance import get_all_block_statuses

# --- Live student status API route ---
@app.route('/api/student-status', methods=['GET'])
@login_required
def student_status():
    student = get_logged_in_student()
    period_states = get_all_block_statuses(student)

    # Add hall pass information for each period
    for period in period_states:
        # Find pending or approved hall passes for this period
        hall_pass = HallPassLog.query.filter_by(
            student_id=student.id,
            period=period
        ).filter(
            HallPassLog.status.in_(['pending', 'approved', 'left'])
        ).order_by(HallPassLog.request_time.desc()).first()

        if hall_pass:
            period_states[period]['hall_pass'] = {
                'id': hall_pass.id,
                'status': hall_pass.status,
                'reason': hall_pass.reason,
                'pass_number': hall_pass.pass_number,
                'request_time': hall_pass.request_time.isoformat() if hall_pass.request_time else None
            }
        else:
            period_states[period]['hall_pass'] = None

    return jsonify(period_states)

@app.route('/api/hall-pass/cancel/<int:pass_id>', methods=['POST'])
@login_required
def cancel_hall_pass(pass_id):
    """Cancel a pending hall pass request (student)"""
    student = get_logged_in_student()
    hall_pass = HallPassLog.query.get_or_404(pass_id)

    # Verify this hall pass belongs to the student
    if hall_pass.student_id != student.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    # Only pending passes can be cancelled
    if hall_pass.status != 'pending':
        return jsonify({"status": "error", "message": "Only pending requests can be cancelled."}), 400

    # Delete the hall pass request
    db.session.delete(hall_pass)
    db.session.commit()

    return jsonify({"status": "success", "message": "Hall pass request cancelled."})


@app.route('/api/set-timezone', methods=['POST'])
@csrf.exempt
def set_timezone():
    data = request.get_json()
    if not data or 'timezone' not in data:
        return jsonify(status="error", message="Timezone not provided"), 400

    tz_name = data['timezone']
    if tz_name not in pytz.all_timezones:
        app.logger.warning(f"Invalid timezone submitted: {tz_name}")
        return jsonify(status="error", message="Invalid timezone"), 400

    session['timezone'] = tz_name
    app.logger.info(f"🌐 Timezone set to {tz_name} for session")
    return jsonify(status="success", message=f"Timezone set to {tz_name}")



@app.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500

# ---- DO TOS and Privacy routes ----
@app.route('/privacy')
def privacy():
    """Render the Privacy & Data Handling Policy page."""
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    """Render the Terms of Service page."""
    return render_template('tos.html')


@app.route('/debug/filters')
def debug_filters():
    return jsonify(list(app.jinja_env.filters.keys()))


# -------------------- DEBUG: ADMIN DB TEST ROUTE --------------------
# Temporary route to confirm admin and invite codes tables are accessible.
@app.route('/debug/admin-db-test')
def debug_admin_db_test():
    try:
        admins = Admin.query.all()
        invite_codes_count = db.session.execute(text('SELECT COUNT(*) FROM admin_invite_codes')).scalar()
        return jsonify({
            "admin_count": len(admins),
            "invite_codes_count": invite_codes_count,
            "status": "success"
        }), 200
    except Exception as e:
        app.logger.exception("Admin DB test failed")
        return jsonify({"status": "error", "error": str(e)}), 500

# --- Ensure admin creation on startup, even on platforms like Azure ---

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)

# -------------------- SYSTEM ADMIN LOGIN --------------------
from forms import SystemAdminLoginForm

@app.route('/sysadmin/login', methods=['GET', 'POST'])
def system_admin_login():
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
                    return redirect(url_for("system_admin_dashboard"))
                return redirect(next_url or url_for("system_admin_dashboard"))
        flash("Invalid credentials or TOTP.", "error")
        return redirect(url_for("system_admin_login"))
    return render_template("system_admin_login.html", form=form)

# -------------------- SYSTEM ADMIN DASHBOARD (UNIFIED INVITE MANAGEMENT) --------------------
@app.route('/sysadmin/dashboard', methods=['GET', 'POST'])
@system_admin_required
def system_admin_dashboard():
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



@app.route('/sysadmin/logout')
def system_admin_logout():
    session.pop("is_system_admin", None)
    flash("Logged out.")
    return redirect(url_for("system_admin_login"))

# -------------------- SYSTEM ADMIN SEED COMMAND --------------------
@app.cli.command("create-sysadmin")
@with_appcontext
def create_sysadmin():
    """Create initial system admin account interactively."""
    import getpass
    import pyotp
    username = input("Enter system admin username: ").strip()
    if not username:
        print("Username is required.")
        return
    existing = SystemAdmin.query.filter_by(username=username).first()
    if existing:
        print(f"System admin '{username}' already exists.")
        return
    totp_secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username=username, totp_secret=totp_secret)
    db.session.add(sysadmin)
    db.session.commit()
    print(f"✅ System admin '{username}' created successfully.")
    print(f"🔑 TOTP secret for authenticator app: {totp_secret}")
    uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(name=username, issuer_name="Classroom Economy SysAdmin")
    print(f"📱 QR Code URI: {uri}")
@app.route('/sysadmin/logs')
@system_admin_required
def system_admin_logs():
    import os, re
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


@app.route('/sysadmin/error-logs')
@system_admin_required
def system_admin_error_logs():
    """
    View error logs from the database.
    Shows all errors captured by the error logging system.
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

    error_logs = pagination.items

    # Get distinct error types for filter dropdown
    error_types = db.session.query(ErrorLog.error_type).distinct().all()
    error_types = [et[0] for et in error_types if et[0]]

    return render_template(
        "system_admin_error_logs.html",
        error_logs=error_logs,
        pagination=pagination,
        error_types=error_types,
        current_error_type=error_type_filter,
        current_page="sysadmin_error_logs"
    )


# -------------------- ERROR TESTING ROUTES (SYSADMIN ONLY) --------------------
@app.route('/sysadmin/test-errors/400')
@system_admin_required
def test_error_400():
    """Trigger a 400 Bad Request error for testing."""
    from werkzeug.exceptions import BadRequest
    raise BadRequest("This is a test 400 error triggered by system admin for testing purposes.")


@app.route('/sysadmin/test-errors/401')
@system_admin_required
def test_error_401():
    """Trigger a 401 Unauthorized error for testing."""
    from werkzeug.exceptions import Unauthorized
    raise Unauthorized("This is a test 401 error triggered by system admin for testing purposes.")


@app.route('/sysadmin/test-errors/403')
@system_admin_required
def test_error_403():
    """Trigger a 403 Forbidden error for testing."""
    from werkzeug.exceptions import Forbidden
    raise Forbidden("This is a test 403 error triggered by system admin for testing purposes.")


@app.route('/sysadmin/test-errors/404')
@system_admin_required
def test_error_404():
    """Trigger a 404 Not Found error for testing."""
    from werkzeug.exceptions import NotFound
    raise NotFound("This is a test 404 error triggered by system admin for testing purposes.")


@app.route('/sysadmin/test-errors/500')
@system_admin_required
def test_error_500():
    """Trigger a 500 Internal Server Error for testing."""
    # Intentionally cause a division by zero error
    x = 1 / 0
    return "This should never be reached"


@app.route('/sysadmin/test-errors/503')
@system_admin_required
def test_error_503():
    """Trigger a 503 Service Unavailable error for testing."""
    from werkzeug.exceptions import ServiceUnavailable
    raise ServiceUnavailable("This is a test 503 error triggered by system admin for testing purposes.")


# -------------------- ADMIN (TEACHER) MANAGEMENT --------------------
@app.route('/sysadmin/admins')
@system_admin_required
def system_admin_manage_admins():
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


@app.route('/sysadmin/admins/<int:admin_id>/delete', methods=['POST'])
@system_admin_required
def system_admin_delete_admin(admin_id):
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
            from sqlalchemy import delete
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
        app.logger.exception(f"Error deleting admin {admin_id}")
        flash(f"Error deleting admin: {str(e)}", "error")

    return redirect(url_for('system_admin_manage_admins'))


@app.route('/sysadmin/manage-teachers', methods=['GET', 'POST'])
@system_admin_required
def system_admin_manage_teachers():
    """
    Combined page for teacher management and invite codes.
    """
    import secrets
    from datetime import datetime, timedelta

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
        return redirect(url_for("system_admin_manage_teachers") + "#invite-codes")

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


@app.route('/sysadmin/manage-teachers/delete/<int:admin_id>', methods=['POST'])
@system_admin_required
def system_admin_delete_teacher(admin_id):
    """
    Delete a teacher and all their associated data.
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
            from sqlalchemy import delete
            db.session.execute(delete(StudentInsurance).where(StudentInsurance.student_id == student.id))
            InsuranceClaim.query.filter_by(student_id=student.id).delete()

        Student.query.delete()  # TODO: Filter by teacher_id

        admin_username = admin.username
        db.session.delete(admin)
        db.session.commit()

        flash(f"✅ Teacher '{admin_username}' and {student_count} students deleted successfully.", "success")

    except Exception as e:
        db.session.rollback()
        app.logger.exception(f"Error deleting teacher {admin_id}")
        flash(f"❌ Error deleting teacher: {str(e)}", "error")

    return redirect(url_for('system_admin_manage_teachers'))


@app.route('/sysadmin/logs-testing')
@system_admin_required
def system_admin_logs_testing():
    """
    Combined page for viewing error logs and testing error pages.
    """
    # Get recent error logs
    recent_errors = ErrorLog.query.order_by(ErrorLog.timestamp.desc()).limit(50).all()

    # Get system logs URL
    logs_url = url_for("system_admin_logs")

    return render_template(
        "system_admin_logs_testing.html",
        recent_errors=recent_errors,
        logs_url=logs_url
    )