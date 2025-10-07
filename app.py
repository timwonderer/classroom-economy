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

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from functools import wraps
import pytz
from sqlalchemy import or_, func, text
import sqlalchemy as sa
# local security helpers
from hash_utils import (
    get_all_peppers,
    get_primary_pepper,
    hash_hmac,
    hash_username,
    iter_username_hashes,
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

# --- CSRF Protection ---
from flask_wtf import CSRFProtect

required_env_vars = ["SECRET_KEY", "DATABASE_URL", "FLASK_ENV", "ENCRYPTION_KEY", "PEPPER_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_vars)
    )

# Custom AES encryption for PII fields using Fernet
class PIIEncryptedType(TypeDecorator):
    impl = LargeBinary

    def __init__(self, key_env_var, *args, **kwargs):
        key = os.getenv(key_env_var)
        if not key:
            raise RuntimeError(f"Missing required environment variable: {key_env_var}")
        self.fernet = Fernet(key)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode('utf-8')
        return self.fernet.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self.fernet.decrypt(value)
        return decrypted.decode('utf-8')

app = Flask(__name__)
app.config.from_mapping(
    DEBUG=False,
    ENV=os.environ["FLASK_ENV"],
    SECRET_KEY=os.environ["SECRET_KEY"],
    SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Enable Jinja2 template hot reloading without server restart
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# --- Enable CSRF protection ---
csrf = CSRFProtect(app)


# --- URL Safety Checker ---
from urllib.parse import urlparse, urljoin
def is_safe_url(target):
    """
    Ensure a redirect URL is safe by checking if it's on the same domain.
    """
    # Allow empty targets
    if not target:
        return True
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def url_encode_filter(s):
    return urllib.parse.quote_plus(s)

app.jinja_env.filters['url_encode'] = url_encode_filter
app.jinja_env.filters['urlencode'] = url_encode_filter

import logging
from logging.handlers import RotatingFileHandler

# ----- Logging Configuration -----
log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
log_format = os.getenv(
    "LOG_FORMAT",
    "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(log_level)
stream_handler.setFormatter(logging.Formatter(log_format))

app.logger.setLevel(log_level)
# Prevent duplicate log entries by clearing handlers first
app.logger.handlers.clear()
app.logger.addHandler(stream_handler)

if os.getenv("FLASK_ENV", app.config.get("ENV")) == "production":
    log_file = os.getenv("LOG_FILE", "app.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    app.logger.addHandler(file_handler)

# ---- Jinja2 filter: Format UTC datetime to user's local time ----
import pytz
def format_datetime(value, fmt='%Y-%m-%d %I:%M %p'):
    """
    Convert a UTC datetime to the user's timezone (from session) and format it.
    Defaults to Pacific Time if no timezone is set in the session.
    """
    if not value:
        return ''

    # Get user's timezone from session, default to Los Angeles
    tz_name = session.get('timezone', 'America/Los_Angeles')
    try:
        target_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        app.logger.warning(f"Invalid timezone '{tz_name}' in session, defaulting to LA.")
        target_tz = pytz.timezone('America/Los_Angeles')

    utc = pytz.utc

    # Localize naive datetimes as UTC before converting
    dt = value if getattr(value, 'tzinfo', None) else utc.localize(value)

    local_dt = dt.astimezone(target_tz)
    return local_dt.strftime(fmt)

app.jinja_env.filters['format_datetime'] = format_datetime


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)
from flask_migrate import Migrate

migrate = Migrate(app, db)



# -------------------- MODELS --------------------
class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_initial = db.Column(db.String(1), nullable=False)
    block = db.Column(db.String(10), nullable=False)

    # Hash and credential fields
    salt = db.Column(db.LargeBinary(16), nullable=False)
    first_half_hash = db.Column(db.String(64), unique=True, nullable=True)
    second_half_hash = db.Column(db.String(64), unique=True, nullable=True)
    username_hash = db.Column(db.String(64), unique=True, nullable=True)

    pin_hash = db.Column(db.Text, nullable=True)
    passphrase_hash = db.Column(db.Text, nullable=True)

    passes_left = db.Column(db.Integer, default=3)
    
    is_rent_enabled = db.Column(db.Boolean, default=True)
    is_property_tax_enabled = db.Column(db.Boolean, default=False)
    owns_seat = db.Column(db.Boolean, default=False)
    insurance_plan = db.Column(db.String, default="none")
    insurance_last_paid = db.Column(db.DateTime, nullable=True)
    second_factor_type = db.Column(db.String, nullable=True)
    second_factor_enabled = db.Column(db.Boolean, default=False)
    has_completed_setup = db.Column(db.Boolean, default=False)
    # Privacy-aligned DOB sum for username generation (non-reversible)
    dob_sum = db.Column(db.Integer, nullable=True)
    cumulative_daily_sec = db.Column(db.Integer, default=0, nullable=False)
    cumulative_payroll_sec = db.Column(db.Integer, default=0, nullable=False)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_initial}."

    transactions = db.relationship('Transaction', backref='student', lazy=True)


    @property
    def checking_balance(self):
        return round(sum(tx.amount for tx in self.transactions if tx.account_type == 'checking' and not tx.is_void), 2)

    @property
    def savings_balance(self):
        return round(sum(tx.amount for tx in self.transactions if tx.account_type == 'savings' and not tx.is_void), 2)

    @property
    def total_earnings(self):
        return round(sum(tx.amount for tx in self.transactions if tx.amount > 0 and not tx.is_void and not tx.description.startswith("Transfer")), 2)

    @property
    def recent_deposits(self):
        now = datetime.now(timezone.utc)
        recent_timeframe = now - timedelta(days=2)

        def _as_utc(dt):
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        deposits = []
        for tx in self.transactions:
            if tx.amount <= 0 or tx.is_void:
                continue
            if (tx.description or "").lower().startswith("transfer"):
                continue
            tx_time = _as_utc(tx.timestamp)
            if not tx_time or tx_time < recent_timeframe:
                continue
            deposits.append(tx)
        return deposits

    @property
    def amount_needed_to_cover_bills(self):
        total_due = 0
        if self.is_rent_enabled:
            total_due += 800
        if self.is_property_tax_enabled and self.owns_seat:
            total_due += 120
        if self.insurance_plan != "none":
            total_due += 200  # Estimated insurance cost
        return max(0, total_due - self.checking_balance)

    # Removed deprecated last_tap_in/last_tap_out properties; backend is source of truth.

class AdminInviteCode(db.Model):
    __tablename__ = 'admin_invite_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    used = db.Column(db.Boolean, default=False)
    # All times stored as UTC (see header note)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -------------------- SYSTEM ADMIN MODEL --------------------
class SystemAdmin(db.Model):
    __tablename__ = 'system_admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    totp_secret = db.Column(db.String(32), nullable=False)
# -------------------- SYSTEM ADMIN AUTH HELPERS --------------------
def system_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_system_admin"):
            flash("System administrator access required.")
            return redirect(url_for('system_admin_login', next=request.path))
        last_activity = session.get('last_activity')
        now = datetime.now(timezone.utc)
        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_system_admin", None)
                flash("Session expired. Please log in again.")
                return redirect(url_for('system_admin_login', next=request.path))
        session['last_activity'] = now.strftime("%Y-%m-%d %H:%M:%S")
        return f(*args, **kwargs)
    return decorated_function



class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    # All times stored as UTC (see header note)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    account_type = db.Column(db.String(20), default='checking')
    description = db.Column(db.String(255))
    is_void = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50))  # optional field to describe the transaction type
    # All times stored as UTC
    date_funds_available = db.Column(db.DateTime, default=datetime.utcnow)

# ---- TapEvent Model (append-only) ----
class TapEvent(db.Model):
    __tablename__ = 'tap_events'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    period = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'active' or 'inactive'
    # All times stored as UTC (see header note)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(50), nullable=True)

    student = db.relationship("Student", backref="tap_events")


# -------------------- STORE MODELS --------------------
class StoreItem(db.Model):
    __tablename__ = 'store_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    item_type = db.Column(db.String(20), nullable=False, default='delayed') # immediate, delayed, collective
    inventory = db.Column(db.Integer, nullable=True) # null for unlimited
    limit_per_student = db.Column(db.Integer, nullable=True) # null for no limit
    auto_delist_date = db.Column(db.DateTime, nullable=True)
    auto_expiry_days = db.Column(db.Integer, nullable=True) # days student has to use the item
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationship to student items
    student_items = db.relationship('StudentItem', backref='store_item', lazy=True)

class StudentItem(db.Model):
    __tablename__ = 'student_items'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id'), nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    # purchased, pending (for collective), processing, completed, expired, redeemed
    status = db.Column(db.String(20), default='purchased', nullable=False)
    redemption_details = db.Column(db.Text, nullable=True) # For student notes on usage
    redemption_date = db.Column(db.DateTime, nullable=True) # When student used it

    # Relationships
    student = db.relationship('Student', backref=db.backref('items', lazy='dynamic'))


# ---- Admin Model ----
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # TOTP-only: store secret, remove password_hash
    totp_secret = db.Column(db.String(32), nullable=False)

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






# -------------------- AUTH HELPERS --------------------
SESSION_TIMEOUT_MINUTES = 10

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('student_login')}?next={encoded_next}")

        # Enforce strict 10-minute timeout from login time
        login_time_str = session.get('login_time')
        if not login_time_str:
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            flash("Session is invalid. Please log in again.")
            return redirect(url_for('student_login'))

        login_time = datetime.fromisoformat(login_time_str)
        if (datetime.now(timezone.utc) - login_time) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Clear student-specific keys but preserve CSRF token
            session.pop('student_id', None)
            session.pop('login_time', None)
            session.pop('last_activity', None)
            flash("Session expired. Please log in again.")
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('student_login')}?next={encoded_next}")

        # Continue to update last_activity for other potential uses, but it no longer controls the timeout
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        return f(*args, **kwargs)
    return decorated_function

def get_logged_in_student():
    return Student.query.get(session['student_id']) if 'student_id' in session else None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app.logger.info(f"🧪 Admin access attempt: session = {dict(session)}")
        if not session.get("is_admin"):
            flash("You must be an admin to view this page.")
            encoded_next = urllib.parse.quote(request.path, safe="")
            return redirect(f"{url_for('admin_login')}?next={encoded_next}")

        now = datetime.now(timezone.utc)
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_admin", None)
                flash("Admin session expired. Please log in again.")
                encoded_next = urllib.parse.quote(request.path, safe="")
                return redirect(f"{url_for('admin_login')}?next={encoded_next}")

        session['last_activity'] = now.strftime("%Y-%m-%d %H:%M:%S")
        return f(*args, **kwargs)
    return decorated_function

# -------------------- STUDENT SETUP FLOW --------------------
@app.route('/')
def home():
    return redirect(url_for('student_login'))  # Or wherever you want to go

# --- PAGE 1: Claim Account ---
@app.route('/student/claim-account', methods=['GET', 'POST'])
def student_claim_account():
    pepper_candidates = get_all_peppers()
    form = StudentClaimAccountForm()

    if form.validate_on_submit():
        first_half = form.first_half.data.strip().lower()
        second_half = form.second_half.data.strip().lower()
        dob_sum = form.dob_sum.data.strip()

        if not dob_sum.isdigit():
            flash("DOB sum must be a number.", "claim")
            return redirect(url_for('student_claim_account'))

        for s in Student.query.filter_by(has_completed_setup=False).all():
            name_code = first_half
            matched_pepper = None

            for pepper in pepper_candidates:
                first_half_hash = hash_hmac(name_code.encode(), s.salt, pepper=pepper)
                second_half_hash = hash_hmac(dob_sum.encode(), s.salt, pepper=pepper)

                if (
                    s.first_half_hash == first_half_hash
                    and s.second_half_hash == second_half_hash
                    and str(s.dob_sum) == dob_sum
                ):
                    matched_pepper = pepper
                    break

            if matched_pepper:
                session['claimed_student_id'] = s.id
                session.pop('generated_username', None)
                session.pop('theme_prompt', None)
                session.pop('theme_slug', None)

                if matched_pepper != get_primary_pepper():
                    s.first_half_hash = hash_hmac(name_code.encode(), s.salt)
                    s.second_half_hash = hash_hmac(dob_sum.encode(), s.salt)
                    db.session.commit()

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


from attendance import get_last_payroll_time, calculate_unpaid_attendance_seconds, get_session_status

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
@app.route('/student/insurance', methods=['GET', 'POST'])
@login_required
def student_insurance():
    student = get_logged_in_student()
    cooldown_message = None
    error_message = None
    plans = {
        "paycheck_protection": 90,
        "personal_responsibility": 60,
        "bundled": 125
    }

    if request.method == 'POST':
        selected_plan = request.form.get('plan')
        if selected_plan not in plans:
            flash("Invalid insurance plan selected.", "insurance_error")
            return redirect(url_for("student_insurance"))

        now = datetime.now(timezone.utc)
        recent_cancellation_tx = Transaction.query.filter(
            Transaction.student_id == student.id,
            Transaction.description == f"Cancelled {selected_plan.replace('_', ' ').title()} Insurance"
        ).order_by(Transaction.timestamp.desc()).first()

        if recent_cancellation_tx and (now - recent_cancellation_tx.timestamp).days < 30:
            flash("You must wait 30 days after cancelling this insurance before purchasing again.", "insurance_error")
            return redirect(url_for("student_insurance"))

        premium = plans[selected_plan]

        # Reject if student will go negative
        if student.checking_balance < premium:
            db.session.add(Transaction(
                student_id=student.id,
                amount=-15,
                account_type="checking",
                type='Fees',
                description="NSF Fee for Insurance Purchase"
            ))
            db.session.commit()
            flash("Insufficient funds for insurance. NSF Fee charged.", "insurance_error")
            return redirect(url_for("student_insurance"))

        # Handle bundled upgrade with prorate logic
        current_plan = student.insurance_plan
        if current_plan != "none" and selected_plan != current_plan:
            current_premium = plans.get(current_plan, 0)
            days_since_paid = (now - (student.insurance_last_paid or now)).days
            prorated_refund = round(current_premium * max(0, (30 - days_since_paid)) / 30, 2)
            if prorated_refund > 0:
                db.session.add(Transaction(
                    student_id=student.id,
                    amount=prorated_refund,
                    account_type="checking",
                    type='Refund',
                    description=f"Prorated Refund for {current_plan.replace('_', ' ').title()}"
                ))

        # Charge new premium
        db.session.add(Transaction(
            student_id=student.id,
            amount=-premium,
            account_type="checking",
            type='Bill',
            description=f"Insurance Premium for {selected_plan.replace('_', ' ').title()}"
        ))

        student.insurance_plan = selected_plan
        student.insurance_last_paid = now
        db.session.commit()
        flash("Insurance purchased successfully!", "insurance_success")
        return redirect(url_for("student_dashboard"))

    current_plan_display = student.insurance_plan.replace('_', ' ').title() if student.insurance_plan != "none" else None
    return render_template('student_insurance_market.html', student=student, cooldown_message=cooldown_message, error_message=error_message)

@app.route('/student/insurance/change', methods=['GET', 'POST'])
@login_required
def student_insurance_change():
    student = get_logged_in_student()

    if request.method == 'POST':
        flash("Insurance change feature coming soon!", "info")
        return redirect(url_for("student_insurance"))

    current_plan = student.insurance_plan if student.insurance_plan and student.insurance_plan != "none" else None
    return render_template('student_insurance_change.html', student=student, current_plan=current_plan)


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
        matched_pepper = None
        students_with_matching_username_structure = Student.query.filter(
            Student.username_hash.isnot(None)
        ).all()

        for s in students_with_matching_username_structure:
            for candidate_hash, pepper in iter_username_hashes(username, s.salt):
                if candidate_hash == s.username_hash:
                    student = s
                    matched_pepper = pepper
                    break
            if student:
                break

        if not student or not check_password_hash(student.pin_hash or '', pin):
            if is_json:
                return jsonify(status="error", message="Invalid credentials"), 401
            flash("Invalid credentials", "error")
            return redirect(url_for('student_login', next=request.args.get('next')))

        # If the username hash was verified with a legacy pepper, migrate it to the
        # current pepper now that we have the plaintext username.
        if matched_pepper and matched_pepper != get_primary_pepper():
            student.username_hash = hash_username(username, student.salt)
            db.session.commit()

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
    students = Student.query.order_by(Student.first_name).all()
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).limit(20).all()
    student_lookup = {s.id: s for s in students}
    # Use TapEvent for logs (append-only) - fetch with student name
    raw_logs = (
        db.session.query(
            TapEvent,
            Student.first_name,
            Student.last_initial
        )
        .join(Student, TapEvent.student_id == Student.id)
        .order_by(TapEvent.timestamp.desc())
        .limit(20)
        .all()
    )
    logs = []
    for log, first_name, last_initial in raw_logs:
        logs.append({
            'student_id': log.student_id,
            'student_name': f"{first_name} {last_initial}.",
            'period': log.period,
            'timestamp': log.timestamp,
            'reason': log.reason,
            'status': log.status
        })
    app.logger.info(f"📝 Dashboard logs data: {logs}")
    for entry in logs:
        app.logger.debug(f"Log entry - student_id: {entry['student_id']}, reason: {entry.get('reason')}")

    # Fetch pending redemption requests
    redemption_requests = StudentItem.query.filter_by(status='processing').order_by(StudentItem.redemption_date.asc()).all()

    return render_template('admin_dashboard.html', students=students, transactions=transactions, student_lookup=student_lookup, logs=logs, redemption_requests=redemption_requests, current_page="dashboard")

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
                session["is_admin"] = True
                session["last_activity"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
    Payroll page: Show payroll estimate and recent payrolls.
    Estimate is computed from TapEvent (append-only), not TapSession.
    """
    from sqlalchemy import desc
    from datetime import datetime, timedelta
    import pytz

    pacific = pytz.timezone('America/Los_Angeles')

    # Get the last payroll time once; it's already UTC-aware from the helper.
    last_payroll_time = get_last_payroll_time()

    # Next scheduled payroll: every other Friday from last payroll
    if last_payroll_time:
        next_pay_date_utc = last_payroll_time + timedelta(days=14)
    else:
        next_pay_date_utc = datetime.now(timezone.utc)

    next_pay_date = next_pay_date_utc.astimezone(pacific)

    # Recent payroll activity: 20 most recent payroll transactions, joined with student info
    recent_raw = (
        db.session.query(
            Transaction,
            Student.first_name.label("student_name"),
            Student.block.label("student_block")
        )
        .join(Student, Transaction.student_id == Student.id)
        .filter(Transaction.type == 'payroll')
        .order_by(Transaction.timestamp.desc())
        .limit(20)
        .all()
    )
    recent_payrolls = [
        {
            'student_id': tx.student_id,
            'student_name': name,
            'student_block': block,
            'amount': tx.amount,
            'timestamp': tx.timestamp  # raw datetime for filter to format
        }
        for tx, name, block in recent_raw
    ]

    # Estimate payroll from TapEvent (since last payroll)
    students = Student.query.all()

    # Use the centralized payroll calculation logic
    payroll_summary = calculate_payroll(students, last_payroll_time)
    total_payroll_estimate = sum(payroll_summary.values())

    app.logger.info(f"PAYROLL ESTIMATE DEBUG: Total estimate is ${total_payroll_estimate:.2f}")

    return render_template(
        'admin_payroll.html',
        recent_payrolls=recent_payrolls,
        next_payroll_date=next_pay_date,
        current_page="payroll",
        total_payroll_estimate=total_payroll_estimate,
        now=datetime.now(pacific).strftime("%Y-%m-%d %I:%M %p")
    )

@app.route('/student/logout')
@login_required
def student_logout():
    session.pop('student_id', None)
    flash("You’ve been logged out.")
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

    pepper = get_primary_pepper()
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
            salt = os.urandom(16)

            # Compute first_half_hash and second_half_hash using HMAC with pepper
            first_half_hash = hash_hmac(name_code.encode(), salt, pepper=pepper)
            second_half_hash = hash_hmac(str(dob_sum).encode(), salt, pepper=pepper)

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
    return jsonify(period_states)



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
                session['last_activity'] = datetime.utcnow().isoformat() + "Z"
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
    import secrets
    invites = AdminInviteCode.query.order_by(AdminInviteCode.created_at.desc()).all()
    form = SystemAdminInviteForm()
    if form.validate_on_submit():
        code = form.code.data or secrets.token_urlsafe(8)
        expires_at = form.expires_at.data
        invite = AdminInviteCode(code=code, expires_at=expires_at)
        db.session.add(invite)
        db.session.commit()
        flash(f"✅ Invite code {code} created successfully.", "success")
        return redirect(url_for("system_admin_dashboard"))
    system_admins = SystemAdmin.query.order_by(SystemAdmin.username.asc()).all()
    logs_url = url_for("system_admin_logs")
    return render_template(
        "system_admin_dashboard.html",
        invites=invites,
        form=form,
        system_admins=system_admins,
        current_page="sysadmin_dashboard",
        logs_url=logs_url
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