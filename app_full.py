from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import pytz
PACIFIC = pytz.timezone('America/Los_Angeles')
import pyotp
import urllib.parse
import os

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None"
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "1%Inspiration&99%Effort")

def url_encode_filter(s):
    return urllib.parse.quote_plus(s)

app.jinja_env.filters['url_encode'] = url_encode_filter

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

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://timwonderer:Deduce-Python5-Customize@localhost/classroom_economy'
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
# -------------------- AUTH HELPERS --------------------
SESSION_TIMEOUT_MINUTES = 10

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            return redirect(url_for('student_login'))

        now = datetime.utcnow()
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop('student_id', None)
                flash("Session expired. Please log in again.")
                return redirect(url_for('student_login'))

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
            return redirect(url_for("admin_login"))

        now = datetime.utcnow()
        last_activity = session.get('last_activity')

        if last_activity:
            last_activity = datetime.strptime(last_activity, "%Y-%m-%d %H:%M:%S")
            if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
                session.pop("is_admin", None)
                flash("Admin session expired. Please log in again.")
                return redirect(url_for("admin_login"))

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

    # Updated tap session status logic for periods a and b
    def get_session_status(student_id, period):
        from datetime import datetime
        today = datetime.utcnow().date()
        completed = TapSession.query.filter_by(student_id=student_id, period=period, is_done=True).all()
        seconds_logged = sum(s.duration_seconds or 0 for s in completed)
        latest_session = max(completed, key=lambda s: s.tap_out_time, default=None)
        locked_out = latest_session and latest_session.tap_out_time.date() == today

        active_session = TapSession.query.filter_by(student_id=student_id, period=period, is_done=False).first()
        is_tapped_in = active_session is not None
        is_done = not is_tapped_in and locked_out

        duration_seconds = seconds_logged
        if active_session:
            duration_seconds += int((datetime.utcnow() - active_session.tap_in_time).total_seconds())

        return is_tapped_in, is_done, duration_seconds

    is_tapped_in_a, is_done_a, duration_seconds_a = get_session_status(student.id, 'a')
    is_tapped_in_b, is_done_b, duration_seconds_b = get_session_status(student.id, 'b')

    tz = pytz.timezone('America/Los_Angeles')
    local_now = datetime.now(tz)
    return render_template('student_dashboard.html', student=student,
                           checking_transactions=checking_transactions,
                           savings_transactions=savings_transactions,
                           purchases=purchases, now=local_now, forecast_interest=forecast_interest,
                           is_tapped_in_a=is_tapped_in_a,
                           is_done_a=is_done_a,
                           duration_seconds_a=duration_seconds_a,
                           is_tapped_in_b=is_tapped_in_b,
                           is_done_b=is_done_b,
                           duration_seconds_b=duration_seconds_b)

# -------------------- TRANSFER ROUTE --------------------
@app.route('/student/transfer', methods=['GET', 'POST'])
@login_required
def student_transfer():
    student = get_logged_in_student()

    if request.method == 'POST':
        passphrase = request.form.get("passphrase")
        if passphrase != student.second_factor_secret:
            flash("Incorrect passphrase. Transfer canceled.", "transfer_error")
            return redirect(url_for("student_transfer"))

        from_account = request.form.get('from_account')
        to_account = request.form.get('to_account')
        amount = float(request.form.get('amount'))

        if from_account == to_account:
            flash("Cannot transfer to the same account.", "transfer_error")
        elif amount <= 0:
            flash("Amount must be greater than 0.", "transfer_error")
        elif from_account == 'checking' and amount > student.checking_balance:
            flash("Insufficient checking funds.", "transfer_error")
        elif from_account == 'savings' and amount > student.savings_balance:
            flash("Insufficient savings funds.", "transfer_error")
        else:
            db.session.add(Transaction(student_id=student.id, amount=-amount, account_type=from_account, description=f"Transfer to {to_account}"))
            db.session.add(Transaction(student_id=student.id, amount=amount, account_type=to_account, description=f"Transfer from {from_account}"))
            flash("Transfer completed successfully!", "transfer_success")
            db.session.commit()
            return redirect(url_for('student_dashboard'))

#    return render_template('student_transfer.html', student=student)
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
                description="NSF Fee for Insurance Purchase",
                account_type="checking",
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
                    description=f"Prorated Refund for {current_plan.replace('_', ' ').title()}",
                    account_type="checking",
                ))

        # Charge new premium
        db.session.add(Transaction(
            student_id=student.id,
            amount=-premium,
            description=f"Insurance Premium for {selected_plan.replace('_', ' ').title()}",
            account_type="checking",
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
            description="Monthly Savings Interest"
        )
        db.session.add(interest_tx)
        db.session.commit()

# -------------------- STUDENT LOGIN --------------------
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        qr_id = request.form.get('qr_id')
        pin = request.form.get('pin')
        student = Student.query.filter_by(qr_id=qr_id).first()

        if not student or not check_password_hash(student.pin_hash, pin):
            flash("Invalid credentials")
            return redirect(url_for('student_login'))

        session['student_id'] = student.id
        session['last_activity'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        if not student.has_completed_setup:
            return redirect(url_for('student_setup'))

        return redirect(url_for('student_dashboard'))

    return render_template('student_login.html')

# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    students = Student.query.order_by(Student.name).all()
    transactions = Transaction.query.order_by(Transaction.timestamp.desc()).limit(20).all()
    student_lookup = {s.id: s for s in students}
    logs = TapSession.query.order_by(TapSession.tap_in_time.desc()).limit(20).all()
    return render_template('admin_dashboard.html', students=students, transactions=transactions, student_lookup=student_lookup, logs=logs)

@app.route('/admin/bonuses', methods=['POST'])
@admin_required
def give_bonus_all():
    title = request.form.get('title')
    amount = float(request.form.get('amount'))
    tx_type = request.form.get('type')

    students = Student.query.all()
    for student in students:
        tx = Transaction(student_id=student.id, amount=amount, type=tx_type, description=title, account_type='checking')
        db.session.add(tx)

    db.session.commit()
    flash("Bonus/Payroll posted successfully!")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        # Replace with something more secure later!
        if username == "admin" and password == "bhu87ygv":
            session["is_admin"] = True
            flash("Admin login successful.")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.")
            return redirect(url_for("admin_login"))
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
    # Ensure TapSession is imported
    # Already imported above, but for safety:
    # from .models import TapSession
    for student in students:
        # fetch latest completed session tap_out_time
        latest_session = TapSession.query.filter_by(student_id=student.id, is_done=True).order_by(TapSession.tap_out_time.desc()).first()
        if latest_session:
            student.last_tap_out = latest_session.tap_out_time
        else:
            student.last_tap_out = None
        # fetch latest session tap_in_time
        latest_in = TapSession.query.filter_by(student_id=student.id).order_by(TapSession.tap_in_time.desc()).first()
        if latest_in:
            student.last_tap_in = latest_in.tap_in_time
        else:
            student.last_tap_in = None
    return render_template('admin_students.html', students=students, selected_page="students")

# -------------------- ADMIN HALL PASS MANAGEMENT PLACEHOLDER --------------------
@app.route('/admin/hall-pass-management')
@admin_required
def admin_pass_management():
    flash("Hall pass management is not implemented yet.", "admin_info")
    return redirect(url_for('admin_dashboard'))

# -------------------- ADMIN TRANSACTION LOG PLACEHOLDER --------------------
@app.route('/admin/transaction-log')
@admin_required
def admin_transaction_log():
    flash("Transaction log is not implemented yet.", "admin_info")
    return redirect(url_for('admin_dashboard'))

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
    tx = Transaction.query.get_or_404(transaction_id)
    tx.is_void = True
    db.session.commit()
    flash("✅ Transaction voided.", "success")
    return redirect(url_for('admin_payroll'))


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
        student_ids = [s.id for s in Student.query.filter_by(block=block).all()]
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

    student_lookup = {s.id: s for s in Student.query.all()}
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
        selected_page="payroll_history",
        selected_block=block,
        selected_start=start_date_str,
        selected_end=end_date_str,
        current_time=current_time
    )


# -------------------- ADMIN RUN PAYROLL MANUALLY --------------------
@app.route('/admin/run-payroll', methods=['POST'])
@admin_required
def run_payroll():
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
        flash(f"✅ Payroll complete. Paid {len(summary)} students.", "admin_success")
    except Exception as e:
        app.logger.error(f"❌ Payroll error: {e}")
        flash("Payroll error occurred. Check logs.", "admin_error")
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

    return render_template(
        'admin_payroll.html',
        recent_payrolls=recent_payrolls,
        next_pay_date=next_pay_date,
        selected_page="payroll",
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
    try:
        app.logger.info("🔄 Entered admin_attendance_log route")
        logs = TapSession.query.order_by(TapSession.tap_in_time.desc()).all()
        students = {
            s.id: {"name": s.name, "block": s.block} for s in Student.query.all()
        }
        app.logger.info("✔️ Successfully fetched logs and students")
        return render_template(
            'admin_attendance_log.html',
            logs=logs,
            students=students,
            selected_page="attendance"
        )
    except Exception as e:
        app.logger.error(f"❌ Exception in admin_attendance_log: {e}")
        flash("An error occurred while loading the attendance log.", "admin_error")
        return redirect(url_for('admin_dashboard'))

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
            except Exception as e:
                flash(f"Error processing row: {e}", "admin_error")
        db.session.commit()
        flash(f"Uploaded {added_count} students successfully!", "admin_success")
        return redirect(url_for('admin_students'))
    return render_template('admin_upload_students.html')

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
    period = data.get("period")
    action = data.get("action")

    if period not in ["a", "b"] or action not in ["tap_in", "tap_out"]:
        return jsonify({"error": "Invalid input"}), 400

    now = datetime.now(PACIFIC)
    student = get_logged_in_student()

    session_entry = TapSession.query.filter_by(
        student_id=student.id,
        period=period,
        is_done=False
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
            session_entry.tap_out_time = now
            session_entry.is_done = True
            session_entry.reason = data.get("reason", session_entry.reason)
            # Calculate the session duration in seconds
            if session_entry.tap_in_time and session_entry.tap_out_time:
                session_entry.duration_seconds = int((now - session_entry.tap_in_time).total_seconds())

    db.session.commit()
    return jsonify({"status": "ok"})


@app.route('/debug/filters')
def debug_filters():
    return jsonify(list(app.jinja_env.filters.keys()))

if __name__ == '__main__':
    app.run(debug=True)