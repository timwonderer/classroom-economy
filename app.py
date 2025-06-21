from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import pytz
from sqlalchemy import or_, func, text
from sqlalchemy.exc import SQLAlchemyError
import math
PACIFIC = pytz.timezone('America/Los_Angeles')
utc = pytz.utc
import pyotp
import urllib.parse
import os

required_env_vars = ["SECRET_KEY", "DATABASE_URL", "FLASK_ENV"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing_vars)
    )

app = Flask(__name__)
app.config.from_mapping(
    DEBUG=False,
    ENV=os.environ["FLASK_ENV"],
    SECRET_KEY=os.environ["SECRET_KEY"],
    SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None",
)


def url_encode_filter(s):
    return urllib.parse.quote_plus(s)

app.jinja_env.filters['url_encode'] = url_encode_filter

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
app.logger.addHandler(stream_handler)

if os.getenv("FLASK_ENV", app.config.get("ENV")) == "production":
    log_file = os.getenv("LOG_FILE", "app.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    app.logger.addHandler(file_handler)

# ---- Jinja2 filter: Format UTC datetime to Pacific Time ----
import pytz
def format_datetime(value, fmt='%Y-%m-%d %I:%M %p', tz_name='America/Los_Angeles'):
    """
    Convert a UTC datetime to the specified timezone and format it.
    """
    if not value:
        return ''
    utc = pytz.utc
    target_tz = pytz.timezone(tz_name)
    # Localize naive datetimes as UTC
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
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    qr_id = db.Column(db.String(100), unique=True, nullable=False)
    pin_hash = db.Column(db.String(256), nullable=False)
    block = db.Column(db.String(1), nullable=False)
    passes_left = db.Column(db.Integer, default=3)
    last_tap_in = db.Column(db.DateTime)
    last_tap_out = db.Column(db.DateTime)
    is_rent_enabled = db.Column(db.Boolean, default=True)
    is_property_tax_enabled = db.Column(db.Boolean, default=False)
    owns_seat = db.Column(db.Boolean, default=False)
    insurance_plan = db.Column(db.String, default="none")
    insurance_last_paid = db.Column(db.DateTime, nullable=True)
    second_factor_type = db.Column(db.String, nullable=True)
    second_factor_secret = db.Column(db.String, nullable=True)
    second_factor_enabled = db.Column(db.Boolean, default=False)
    has_completed_setup = db.Column(db.Boolean, default=False)

    transactions = db.relationship('Transaction', backref='student', lazy=True)
    purchases = db.relationship('Purchase', backref='student', lazy=True)
    tap_sessions = db.relationship('TapSession', back_populates='student', lazy='dynamic')

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
        now = datetime.utcnow()
        recent_timeframe = now - timedelta(days=2)
        return [
            tx for tx in self.transactions
            if tx.amount > 0
            and not tx.is_void
            and tx.timestamp >= recent_timeframe
            and not tx.description.lower().startswith("transfer")
        ]

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

    @property
    def next_pay_date(self):
        from datetime import timedelta
        return (self.last_tap_in or datetime.utcnow()) + timedelta(days=14)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    account_type = db.Column(db.String(20), default='checking')
    description = db.Column(db.String(255))
    is_void = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50))  # optional field to describe the transaction type
    date_funds_available = db.Column(db.DateTime, default=datetime.utcnow)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    item_name = db.Column(db.String(100))
    redeemed = db.Column(db.Boolean, default=False)
    date_purchased = db.Column(db.DateTime, default=datetime.utcnow)

# ---- TapSession Model ----
from datetime import datetime
class TapSession(db.Model):
    __tablename__ = 'tap_sessions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # e.g., 'a', 'b'
    tap_in_time = db.Column(db.DateTime, default=lambda: datetime.now(PACIFIC))
    tap_out_time = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.String(50), nullable=True)
    is_done = db.Column(db.Boolean, default=False)
    duration_seconds = db.Column(db.Integer, default=0)
    is_paid = db.Column(db.Boolean, default=False)

    student = db.relationship("Student", back_populates="tap_sessions")

# ---- Admin Model ----
class Admin(db.Model):
    __tablename__ = 'admins'
    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(80), unique=True, nullable=False)
    password_hash  = db.Column(db.Text, nullable=False)

    @staticmethod
    def hash_password(pw: str) -> str:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, pw)

# after your models are defined but before you start serving requests
from flask.cli import with_appcontext
import os

def ensure_default_admin():
    user = os.environ.get("ADMIN_USERNAME")
    pw   = os.environ.get("ADMIN_PASSWORD")
    if user and pw and not Admin.query.filter_by(username=user).first():
        a = Admin(username=user,
                  password_hash=Admin.hash_password(pw))
        db.session.add(a)
        db.session.commit()
        app.logger.info(f"🚀 Created default admin '{user}'")


# ---- Flask CLI command to manually ensure default admin ----
@app.cli.command("ensure-admin")
@with_appcontext
def ensure_admin_command():
    """Create the default admin user if credentials are provided."""
    ensure_default_admin()





# -------------------- AUTH HELPERS --------------------
SESSION_TIMEOUT_MINUTES = 10

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            return redirect(url_for('student_login', next=request.url))

        now = datetime.now(utc)
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop('student_id', None)
                flash("Session expired. Please log in again.")
                return redirect(url_for('student_login', next=request.url))

        session['last_activity'] = now.strftime("%Y-%m-%d %H:%M:%S")
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
            return redirect(url_for("admin_login", next=request.url))

        now = datetime.now(utc)
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_admin", None)
                flash("Admin session expired. Please log in again.")
                return redirect(url_for("admin_login", next=request.url))

        session['last_activity'] = now.strftime("%Y-%m-%d %H:%M:%S")
        return f(*args, **kwargs)
    return decorated_function

# -------------------- STUDENT SETUP FLOW --------------------
@app.route('/')
def home():
    return redirect(url_for('student_login'))  # Or wherever you want to go

@app.route('/setup-complete')
@login_required
def setup_complete():
    student = get_logged_in_student()
    student.has_completed_setup = True
    db.session.commit()
    return render_template('student_setup_complete.html')

@app.route('/student/setup', methods=['GET', 'POST'])
@login_required
def student_setup():
    student = get_logged_in_student()
    if request.method == 'POST':
        # Clear unrelated flash messages
        for category in ['setup']:
            session.modified = True
            flash("Setup completed successfully!", category)

        # Save the new PIN
        student.pin_hash = generate_password_hash(request.form.get("pin"))

        # Save the passphrase as the second factor secret
        passphrase = request.form.get("second_factor_secret")
        if passphrase:
            student.second_factor_secret = passphrase
        else:
            flash("Passphrase is required.", "setup")
            return redirect(url_for('student_setup'))

        student.has_completed_setup = True
        db.session.commit()
        flash("Setup completed successfully!", "setup")
        return redirect(url_for('setup_complete'))

    return render_template('student_setup.html', student=student)

# -------------------- STUDENT DASHBOARD --------------------
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    student = get_logged_in_student()
    apply_savings_interest(student)  # Apply savings interest if not already applied
    transactions = Transaction.query.filter_by(student_id=student.id).order_by(Transaction.timestamp.desc()).all()
    purchases = Purchase.query.filter_by(student_id=student.id).all()
    
    checking_transactions = [tx for tx in transactions if tx.account_type == 'checking']
    savings_transactions = [tx for tx in transactions if tx.account_type == 'savings']
    
    forecast_interest = round(student.savings_balance * (0.045 / 12), 2)

    # ---- Compute session status for each block based on real DB state ----
    from datetime import date

    def get_session_status(student_id, blk):
        today = date.today()
        # Active session: no tap_out_time
        active = TapSession.query.filter_by(
            student_id=student_id,
            period=blk,
            tap_out_time=None
        ).first()
        if active:
            # still tapped in
            t_in = active.tap_in_time
            if getattr(t_in, 'tzinfo', None) is None:
                t_in = utc.localize(t_in)
            seconds = int((datetime.now(PACIFIC) - t_in.astimezone(PACIFIC)).total_seconds())
            return True, False, seconds

        # Not active: sum all sessions today for this block
        sessions = TapSession.query.filter(
            TapSession.student_id==student_id,
            TapSession.period==blk,
            func.date(TapSession.tap_in_time)==today
        ).all()
        total = 0
        done = False
        for s in sessions:
            t_in = s.tap_in_time
            t_out = s.tap_out_time or datetime.now(PACIFIC)
            if getattr(t_in, 'tzinfo', None) is None:
                t_in = utc.localize(t_in)
            if getattr(t_out, 'tzinfo', None) is None:
                t_out = utc.localize(t_out)
            total += (t_out.astimezone(PACIFIC) - t_in.astimezone(PACIFIC)).total_seconds()
            # mark done if any session had reason 'done'
            if s.reason and s.reason.lower() == 'done':
                done = True
        return False, done, int(total)

    # Determine all blocks for this student dynamically
    student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]
    period_states = {blk: get_session_status(student.id, blk) for blk in student_blocks}

    # Compute most recent deposit and insurance paid flag
    recent_deposit = student.recent_deposits[0] if student.recent_deposits else None
    insurance_paid = bool(student.insurance_last_paid)

    tz = pytz.timezone('America/Los_Angeles')
    local_now = datetime.now(tz)
    return render_template(
        'student_dashboard.html',
        student=student,
        student_blocks=student_blocks,
        period_states=period_states,
        checking_transactions=checking_transactions,
        savings_transactions=savings_transactions,
        purchases=purchases,
        now=local_now,
        forecast_interest=forecast_interest,
        recent_deposit=recent_deposit,
        insurance_paid=insurance_paid
    )

# -------------------- TRANSFER ROUTE --------------------
@app.route('/student/transfer', methods=['GET', 'POST'])
@login_required
def student_transfer():
    student = get_logged_in_student()

    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        passphrase = request.form.get("passphrase")
        if passphrase != student.second_factor_secret:
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

        now = datetime.utcnow()
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

# -------------------- TRANSFER ROUTE SUPPORT FUNCTIONS --------------------
def apply_savings_interest(student, annual_rate=0.045):
    now = datetime.utcnow()
    this_month = now.month
    this_year = now.year

    # Check if interest was already applied this month
    for tx in student.transactions:
        if (
            tx.account_type == 'savings'
            and tx.description == "Monthly Savings Interest"
            and tx.timestamp.month == this_month
            and tx.timestamp.year == this_year
        ):
            return  # Interest already applied this month

    if any(tx.account_type == 'savings' and "Transfer" in tx.description and tx.timestamp.date() == now.date() for tx in student.transactions):
        return

    eligible_balance = sum(
        tx.amount for tx in student.transactions
        if tx.account_type == 'savings' and
           not tx.is_void and
           tx.amount > 0 and
           (now - tx.date_funds_available).days >= 30
    )
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
    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        qr_id = request.form.get('qr_id')
        pin = request.form.get('pin')
        student = Student.query.filter_by(qr_id=qr_id).first()

        if not student or not check_password_hash(student.pin_hash, pin):
            if is_json:
                return jsonify(status="error", message="Invalid credentials"), 401
            flash("Invalid credentials", "error")
            return redirect(url_for('student_login', next=request.args.get('next')))

        session['student_id'] = student.id
        session['last_activity'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        if not student.has_completed_setup:
            if is_json:
                return jsonify(status="success", message="Login successful")
            return redirect(url_for('student_setup'))

        if is_json:
            return jsonify(status="success", message="Login successful")

        next_url = request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('student_dashboard'))

    return render_template('student_login.html')

# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    students = Student.query.order_by(Student.name).all()
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).limit(20).all()
    student_lookup = {s.id: s for s in students}
    raw_logs = TapSession.query.order_by(TapSession.tap_in_time.desc()).limit(20).all()
    logs = []
    for log in raw_logs:
        dur = log.duration_seconds or 0
        # Recalculate if negative and both timestamps present
        if dur < 0 and log.tap_in_time and log.tap_out_time:
            t_in = log.tap_in_time
            if getattr(t_in, 'tzinfo', None) is None:
                t_in = utc.localize(t_in)
            t_out = log.tap_out_time
            if getattr(t_out, 'tzinfo', None) is None:
                t_out = utc.localize(t_out)
            dur = int((t_out - t_in).total_seconds())
        logs.append({
            'student_id': log.student_id,
            'period': log.period,
            'tap_in_time': log.tap_in_time,
            'tap_out_time': log.tap_out_time,
            'duration_seconds': dur,
            'reason': log.reason
        })
    app.logger.info(f"📝 Dashboard logs data: {logs}")
    for entry in logs:
        app.logger.debug(f"Log entry - student_id: {entry['student_id']}, reason: {entry.get('reason')}")
    return render_template('admin_dashboard.html', students=students, transactions=transactions, student_lookup=student_lookup, logs=logs)

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

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        username = request.form.get("username")
        password = request.form.get("password")

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session["is_admin"] = True
            if is_json:
                return jsonify(status="success", message="Login successful")
            flash("Admin login successful.")
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("admin_dashboard"))
        else:
            if is_json:
                return jsonify(status="error", message="Invalid credentials"), 401
            flash("Invalid credentials.", "error")
            return redirect(url_for("admin_login", next=request.args.get("next")))
    return render_template("admin_login.html")

@app.route('/admin/logout')
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.")
    return redirect(url_for("admin_login"))


@app.route('/admin/students')
@admin_required
def admin_students():
    students = Student.query.order_by(Student.block, Student.name).all()
    from datetime import datetime
    for student in students:
        # fetch latest session with tap_out_time (regardless of is_done)
        latest_session = (
            TapSession.query
            .filter(TapSession.student_id == student.id, TapSession.tap_out_time != None)
            .order_by(TapSession.tap_out_time.desc())
            .first()
        )
        if latest_session:
            student.last_tap_out = latest_session.tap_out_time
        else:
            student.last_tap_out = None
        # Attach tap-out reason
        student.last_tap_out_reason = latest_session.reason if latest_session else None
        # fetch latest session tap_in_time
        latest_in = TapSession.query.filter_by(student_id=student.id).order_by(TapSession.tap_in_time.desc()).first()
        if latest_in:
            student.last_tap_in = latest_in.tap_in_time
        else:
            student.last_tap_in = None
    return render_template('admin_students.html', students=students, current_page="students")

# -------------------- ADMIN HALL PASS MANAGEMENT PLACEHOLDER --------------------
@app.route('/admin/hall-pass-management')
@admin_required
def admin_pass_management():
    flash("Hall pass management is not implemented yet.", "admin_info")
    return redirect(url_for('admin_dashboard'))



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
        Student.name.label('student_name'),
        Student.block.label('student_block')
    ).join(Student, Transaction.student_id == Student.id)

    # Apply filters
    if student_q:
        query = query.filter(
            or_(
                Student.name.ilike(f"%{student_q}%"),
                func.cast(Student.id, db.String).ilike(f"%{student_q}%")
            )
        )
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
    # Fetch latest tap session for additional info
    latest_session = TapSession.query.filter_by(student_id=student.id).order_by(TapSession.tap_in_time.desc()).first()
    if latest_session:
        student.last_tap_in = latest_session.tap_in_time
        student.last_tap_out = latest_session.tap_out_time
        student.last_tap_out_reason = latest_session.reason
    else:
        student.last_tap_in = None
        student.last_tap_out = None
        student.last_tap_out_reason = None

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
    purchases = Purchase.query.filter_by(student_id=student.id).all()
    return render_template('student_detail.html', student=student, transactions=transactions, purchases=purchases)


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
            'student_name': student.name if student else 'Unknown',
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


# -------------------- ADMIN RUN PAYROLL MANUALLY --------------------
@app.route('/admin/run-payroll', methods=['POST'])
@admin_required
def run_payroll():
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        from sqlalchemy.sql import func
        RATE_PER_SECOND = 0.25 / 60  # $0.25 per minute

        unpaid_sessions = TapSession.query.filter_by(is_done=True, is_paid=False).all()
        summary = {}

        for session in unpaid_sessions:
            if not session.duration_seconds or session.duration_seconds <= 0:
                continue

            amount = round(session.duration_seconds * RATE_PER_SECOND, 2)
            if amount <= 0:
                continue

            tx = Transaction(
                student_id=session.student_id,
                amount=amount,
                description="Payroll based on attendance",
                account_type="checking",
                type="payroll"
            )
            db.session.add(tx)
            session.is_paid = True
            summary.setdefault(session.student_id, 0)
            summary[session.student_id] += amount

        db.session.commit()
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
    from sqlalchemy import desc
    from datetime import datetime, timedelta
    import pytz
    # Next scheduled payroll: every other Friday from last payroll
    last_payroll_tx = Transaction.query.filter_by(type="payroll").order_by(desc(Transaction.timestamp)).first()
    pacific = pytz.timezone('America/Los_Angeles')
    next_pay_date = (last_payroll_tx.timestamp + timedelta(days=14)) if last_payroll_tx else datetime.utcnow()
    next_pay_date = next_pay_date.astimezone(pacific)  # raw datetime for template filter

    # Recent payroll activity: 20 most recent payroll transactions, joined with student info
    recent_raw = (
        db.session.query(
            Transaction,
            Student.name.label("student_name"),
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

    # Compute total estimate from unpaid sessions
    RATE_PER_SECOND = 0.25 / 60  # $0.25 per minute, must match run_payroll
    unpaid_sessions = TapSession.query.filter_by(is_done=True, is_paid=False).all()
    total_payroll_estimate = round(sum(
        session.duration_seconds * RATE_PER_SECOND
        for session in unpaid_sessions
        if session.duration_seconds and session.duration_seconds > 0
    ), 2)

    next_payroll_date = next_pay_date

    return render_template(
        'admin_payroll.html',
        recent_payrolls=recent_payrolls,
        next_payroll_date=next_payroll_date,
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

@app.route('/admin/add-student', methods=['GET', 'POST'])
@admin_required
def admin_add_student():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        qr_id = request.form.get('qr_id')
        pin = request.form.get('pin')
        block = request.form.get('block')
        if not (name and email and qr_id and pin and block):
            flash("Please fill in all required fields.", "admin_error")
            return redirect(url_for('admin_add_student'))
        new_student = Student(name=name, email=email, qr_id=qr_id, block=block,
                              pin_hash=generate_password_hash(pin))
        db.session.add(new_student)
        db.session.commit()
        flash("Student added successfully!", "admin_success")
        return redirect(url_for('admin_students'))
    return render_template('admin_add_student.html')

# -------------------- ADMIN FULL ATTENDANCE LOG --------------------
@app.route('/admin/attendance-log')
@admin_required
def admin_attendance_log():
    # Build student lookup for names and blocks, streaming in batches
    students = {s.id: {'name': s.name, 'block': s.block} for s in Student.query.yield_per(50)}
    # Fetch attendance sessions, streaming in batches
    raw_logs = TapSession.query.order_by(TapSession.tap_in_time.desc()).yield_per(100)
    # Format logs as dicts, normalizing negative durations
    attendance_logs = []
    for log in raw_logs:
        # Compute a positive duration if the stored one is negative or missing
        dur = log.duration_seconds or 0
        if dur < 0 and log.tap_in_time and log.tap_out_time:
            t_in = log.tap_in_time
            if getattr(t_in, 'tzinfo', None) is None:
                t_in = utc.localize(t_in)
            t_out = log.tap_out_time
            if getattr(t_out, 'tzinfo', None) is None:
                t_out = utc.localize(t_out)
            dur = int((t_out - t_in).total_seconds())
        attendance_logs.append({
            'student_id': log.student_id,
            'tap_in_time': log.tap_in_time,
            'tap_out_time': log.tap_out_time,
            'duration_seconds': dur,
            'reason': log.reason
        })
    return render_template(
        'admin_attendance_log.html',
        logs=attendance_logs,
        students=students,
        current_page="attendance"
    )

@app.route('/admin/upload-students', methods=['GET', 'POST'])
@admin_required
def admin_upload_students():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file:
            flash("No file provided", "admin_error")
            return redirect(url_for('admin_upload_students'))
        import csv, io
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        added_count = 0
        for row in csv_input:
            try:
                new_student = Student(
                    name=row.get('name'),
                    email=row.get('email'),
                    qr_id=row.get('qr_id'),
                    block=row.get('block'),
                    pin_hash=generate_password_hash(row.get('pin')) if row.get('pin') else None,
                )
                db.session.add(new_student)
                added_count += 1
            except (ValueError, SQLAlchemyError) as e:
                db.session.rollback()
                app.logger.error(f"Error processing row {row}: {e}", exc_info=True)
                flash(f"Error processing row: {e}", "admin_error")
        db.session.commit()
        flash(f"Uploaded {added_count} students successfully!", "admin_success")
        return redirect(url_for('admin_students'))
    return render_template('admin_upload_students.html', current_page="upload_students")

@app.route('/admin/download-csv-template')
@admin_required
def download_csv_template():
    """
    Provides a pre-formatted CSV template for student information.
    Columns: name, email, qr_id, block, pin
    """
    csv_content = "name,email,qr_id,block,pin\nSample Name,sample@example.com,QR12345,1,YourPINHere\n"
    return Response(csv_content,
                    mimetype='text/csv',
                    headers={"Content-disposition": "attachment; filename=student_template.csv"})


@app.route('/api/tap', methods=['POST'])
@login_required
def handle_tap():
    data = request.get_json()
    student = get_logged_in_student()
    # Derive valid blocks (uppercase) from the student's block field
    if isinstance(student.block, str):
        valid_periods = [b.strip().upper() for b in student.block.split(',') if b.strip()]
    else:
        valid_periods = []

    period = data.get("period", "").upper()
    action = data.get("action")

    if period not in valid_periods or action not in ["tap_in", "tap_out"]:
        return jsonify({"error": "Invalid period or action"}), 400

    now = datetime.now(PACIFIC)

    session_entry = TapSession.query.filter_by(
        student_id=student.id,
        period=period,
        is_done=False,
        tap_out_time=None
    ).first()

    if action == "tap_in":
        if not session_entry:
            session_entry = TapSession(
                student_id=student.id,
                period=period,
                tap_in_time=now,
                is_done=False
            )
            db.session.add(session_entry)
    elif action == "tap_out":
        if session_entry:
            # Record tap-out time and reason
            session_entry.tap_out_time = now
            session_entry.reason = data.get("reason", session_entry.reason)
            # Only mark session done if reason indicates final exit
            if session_entry.reason and session_entry.reason.lower() == 'done':
                session_entry.is_done = True
            # Calculate the session duration in seconds
            if session_entry.tap_in_time and session_entry.tap_out_time:
                # Ensure tap_in_time is timezone-aware in Pacific
                t_in = session_entry.tap_in_time
                if getattr(t_in, 'tzinfo', None) is None:
                    t_in = PACIFIC.localize(t_in)
                # Ensure tap_out_time is timezone-aware in Pacific (if needed)
                t_out = session_entry.tap_out_time
                if getattr(t_out, 'tzinfo', None) is None:
                    t_out = PACIFIC.localize(t_out)
                session_entry.duration_seconds = int((t_out - t_in).total_seconds())

    try:
        db.session.commit()
        app.logger.info(
            f"TAP success - student {student.id} {period} {action}"
        )
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(
            f"TAP failed for student {student.id}: {e}", exc_info=True
        )
        return jsonify({"error": "Database error"}), 500

    return jsonify({"status": "ok"})


@app.route('/health')
def health_check():
    """Simple health check endpoint for uptime monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except SQLAlchemyError as e:
        app.logger.exception('Health check failed')
        return jsonify(error='Database error'), 500


@app.route('/debug/filters')
def debug_filters():
    return jsonify(list(app.jinja_env.filters.keys()))

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)
