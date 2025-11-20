"""
Database models for Classroom Token Hub.

All SQLAlchemy models are defined here with proper relationships and properties.
Times are stored as UTC in the database.
"""

from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.utils.encryption import PIIEncryptedType


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

    hall_passes = db.Column(db.Integer, default=3)

    is_rent_enabled = db.Column(db.Boolean, default=True)
    insurance_plan = db.Column(db.String, default="none")
    insurance_last_paid = db.Column(db.DateTime, nullable=True)
    second_factor_type = db.Column(db.String, nullable=True)
    second_factor_enabled = db.Column(db.Boolean, default=False)
    has_completed_setup = db.Column(db.Boolean, default=False)
    # Privacy-aligned DOB sum for username generation (non-reversible)
    dob_sum = db.Column(db.Integer, nullable=True)

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


# ---- Hall Pass Log Model ----
class HallPassLog(db.Model):
    __tablename__ = 'hall_pass_logs'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False) # pending, approved, rejected, left, returned
    pass_number = db.Column(db.String(3), nullable=True, unique=True) # Format: letter + 2 digits (e.g., A42)
    period = db.Column(db.String(10), nullable=True) # Which period the request was made in
    request_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decision_time = db.Column(db.DateTime, nullable=True)
    left_time = db.Column(db.DateTime, nullable=True)
    return_time = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref='hall_pass_logs')


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

    # Bundle settings
    is_bundle = db.Column(db.Boolean, default=False, nullable=False)
    bundle_quantity = db.Column(db.Integer, nullable=True) # number of items in bundle (e.g., 5)

    # Bulk discount settings
    bulk_discount_enabled = db.Column(db.Boolean, default=False, nullable=False)
    bulk_discount_quantity = db.Column(db.Integer, nullable=True) # minimum quantity for discount
    bulk_discount_percentage = db.Column(db.Float, nullable=True) # discount percentage (e.g., 10 for 10%)

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

    # Bundle tracking - for items purchased as part of a bundle
    is_from_bundle = db.Column(db.Boolean, default=False, nullable=False)
    bundle_remaining = db.Column(db.Integer, nullable=True) # remaining uses in bundle
    quantity_purchased = db.Column(db.Integer, default=1, nullable=False) # quantity purchased (for bulk discounts)

    # Relationships
    student = db.relationship('Student', backref=db.backref('items', lazy='dynamic'))


# -------------------- RENT SETTINGS MODEL --------------------
class RentSettings(db.Model):
    __tablename__ = 'rent_settings'
    id = db.Column(db.Integer, primary_key=True)

    # Main toggle
    is_enabled = db.Column(db.Boolean, default=True)

    # Rent amount and frequency
    rent_amount = db.Column(db.Float, default=50.0)
    frequency_type = db.Column(db.String(20), default='monthly')  # 'daily', 'weekly', 'monthly', 'custom'
    custom_frequency_value = db.Column(db.Integer, nullable=True)  # For custom: x per time unit
    custom_frequency_unit = db.Column(db.String(20), nullable=True)  # 'days', 'weeks', 'months'

    # Due date settings
    first_rent_due_date = db.Column(db.DateTime, nullable=True)
    due_day_of_month = db.Column(db.Integer, default=1)  # For monthly frequency (kept for compatibility)

    # Grace period and late penalties
    grace_period_days = db.Column(db.Integer, default=3)
    late_penalty_amount = db.Column(db.Float, default=10.0)
    late_penalty_type = db.Column(db.String(20), default='once')  # 'once' or 'recurring'
    late_penalty_frequency_days = db.Column(db.Integer, nullable=True)  # For recurring type

    # Bill preview and payment options
    bill_preview_enabled = db.Column(db.Boolean, default=False)
    bill_preview_days = db.Column(db.Integer, default=7)
    allow_incremental_payment = db.Column(db.Boolean, default=False)
    prevent_purchase_when_late = db.Column(db.Boolean, default=False)

    # Metadata
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Keep old field names for backward compatibility (deprecated)
    @property
    def late_fee(self):
        return self.late_penalty_amount


class RentPayment(db.Model):
    __tablename__ = 'rent_payments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # Block/Period (e.g., 'A', 'B', 'C')
    amount_paid = db.Column(db.Float, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)  # Month (1-12)
    period_year = db.Column(db.Integer, nullable=False)  # Year (e.g., 2025)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    was_late = db.Column(db.Boolean, default=False)
    late_fee_charged = db.Column(db.Float, default=0.0)

    student = db.relationship('Student', backref='rent_payments')


class RentWaiver(db.Model):
    __tablename__ = 'rent_waivers'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    waiver_start_date = db.Column(db.DateTime, nullable=False)
    waiver_end_date = db.Column(db.DateTime, nullable=False)
    periods_count = db.Column(db.Integer, nullable=False)  # Number of rent periods to skip
    reason = db.Column(db.Text, nullable=True)
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref='rent_waivers')
    created_by = db.relationship('Admin', backref='rent_waivers_created')


# -------------------- INSURANCE MODELS --------------------
class InsurancePolicy(db.Model):
    __tablename__ = 'insurance_policies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    premium = db.Column(db.Float, nullable=False)  # Monthly cost
    charge_frequency = db.Column(db.String(20), default='monthly')  # monthly, weekly, etc
    autopay = db.Column(db.Boolean, default=True)
    waiting_period_days = db.Column(db.Integer, default=7)  # Days before coverage starts
    max_claims_count = db.Column(db.Integer, nullable=True)  # Max claims per period (null = unlimited)
    max_claims_period = db.Column(db.String(20), default='month')  # month, semester, year
    max_claim_amount = db.Column(db.Float, nullable=True)  # Max $ per claim (null = unlimited)

    # Claim type
    is_monetary = db.Column(db.Boolean, default=True)  # True = monetary claims, False = item/service claims

    # Special rules
    no_repurchase_after_cancel = db.Column(db.Boolean, default=False)  # Permanent block on repurchase
    enable_repurchase_cooldown = db.Column(db.Boolean, default=False)  # Enable temporary cooldown period
    repurchase_wait_days = db.Column(db.Integer, default=30)  # Days to wait after cancel (if cooldown enabled)
    auto_cancel_nonpay_days = db.Column(db.Integer, default=7)  # Days of non-payment before cancel
    claim_time_limit_days = db.Column(db.Integer, default=30)  # Days from incident to file claim

    # Bundle settings (JSON or separate table in future)
    bundle_with_policy_ids = db.Column(db.Text, nullable=True)  # Comma-separated IDs
    bundle_discount_percent = db.Column(db.Float, default=0)  # Discount % for bundle
    bundle_discount_amount = db.Column(db.Float, default=0)  # Discount $ amount for bundle

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student_policies = db.relationship('StudentInsurance', backref='policy', lazy='dynamic')
    claims = db.relationship('InsuranceClaim', backref='policy', lazy='dynamic')


class StudentInsurance(db.Model):
    __tablename__ = 'student_insurance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey('insurance_policies.id'), nullable=False)

    status = db.Column(db.String(20), default='active')  # active, cancelled, suspended
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    cancel_date = db.Column(db.DateTime, nullable=True)
    last_payment_date = db.Column(db.DateTime, nullable=True)
    next_payment_due = db.Column(db.DateTime, nullable=True)
    coverage_start_date = db.Column(db.DateTime, nullable=True)  # After waiting period

    # Track payment status
    payment_current = db.Column(db.Boolean, default=True)
    days_unpaid = db.Column(db.Integer, default=0)

    # Relationships
    student = db.relationship('Student', backref='insurance_policies')
    claims = db.relationship('InsuranceClaim', backref='student_policy', lazy='dynamic')


class InsuranceClaim(db.Model):
    __tablename__ = 'insurance_claims'
    id = db.Column(db.Integer, primary_key=True)
    student_insurance_id = db.Column(db.Integer, db.ForeignKey('student_insurance.id'), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey('insurance_policies.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    incident_date = db.Column(db.DateTime, nullable=False)  # When incident occurred
    filed_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=False)
    claim_amount = db.Column(db.Float, nullable=True)  # For monetary claims: requested amount
    claim_item = db.Column(db.Text, nullable=True)  # For non-monetary claims: what they're claiming
    comments = db.Column(db.Text, nullable=True)  # Optional comments from student

    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, paid
    rejection_reason = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    approved_amount = db.Column(db.Float, nullable=True)
    processed_date = db.Column(db.DateTime, nullable=True)
    processed_by_admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)

    # Relationships
    student = db.relationship('Student', backref='insurance_claims')
    processed_by = db.relationship('Admin', backref='processed_claims')


# ---- Error Log Model ----
class ErrorLog(db.Model):
    __tablename__ = 'error_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    error_type = db.Column(db.String(100), nullable=True)  # Type of error (e.g., Exception class name)
    error_message = db.Column(db.Text, nullable=True)  # Error message
    request_path = db.Column(db.String(500), nullable=True)  # URL path that caused the error
    request_method = db.Column(db.String(10), nullable=True)  # HTTP method (GET, POST, etc.)
    user_agent = db.Column(db.String(500), nullable=True)  # Browser/client info
    ip_address = db.Column(db.String(50), nullable=True)  # IP address of requester
    log_output = db.Column(db.Text, nullable=False)  # Last 50 lines of log
    stack_trace = db.Column(db.Text, nullable=True)  # Full stack trace


# ---- Admin Model ----
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # TOTP-only: store secret, remove password_hash
    totp_secret = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)  # Nullable for existing records
    last_login = db.Column(db.DateTime, nullable=True)


# ---- Payroll Settings Model ----
class PayrollSettings(db.Model):
    __tablename__ = 'payroll_settings'
    id = db.Column(db.Integer, primary_key=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global/default settings
    pay_rate = db.Column(db.Float, nullable=False, default=0.25)  # $ per minute
    payroll_frequency_days = db.Column(db.Integer, nullable=False, default=14)
    next_payroll_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional: different rates for different scenarios
    overtime_multiplier = db.Column(db.Float, default=1.0)
    bonus_rate = db.Column(db.Float, default=0.0)

    # Enhanced settings for simple/advanced modes
    settings_mode = db.Column(db.String(20), nullable=False, default='simple')  # 'simple' or 'advanced'

    # Simple mode fields
    daily_limit_hours = db.Column(db.Float, nullable=True)  # Max hours per day (auto tap-out)

    # Advanced mode fields
    time_unit = db.Column(db.String(20), nullable=False, default='minutes')  # seconds/minutes/hours/days
    overtime_enabled = db.Column(db.Boolean, nullable=False, default=False)
    overtime_threshold = db.Column(db.Float, nullable=True)  # Threshold value
    overtime_threshold_unit = db.Column(db.String(20), nullable=True)  # seconds/minutes/hours
    overtime_threshold_period = db.Column(db.String(20), nullable=True)  # day/week/month
    max_time_per_day = db.Column(db.Float, nullable=True)  # Max time value (overrides overtime)
    max_time_per_day_unit = db.Column(db.String(20), nullable=True)  # seconds/minutes/hours
    pay_schedule_type = db.Column(db.String(20), nullable=False, default='biweekly')  # daily/weekly/biweekly/monthly/custom
    pay_schedule_custom_value = db.Column(db.Integer, nullable=True)  # For custom schedule
    pay_schedule_custom_unit = db.Column(db.String(20), nullable=True)  # day/week for custom
    first_pay_date = db.Column(db.DateTime, nullable=True)  # First payday
    rounding_mode = db.Column(db.String(20), nullable=False, default='down')  # 'up' or 'down'

    def __repr__(self):
        return f'<PayrollSettings {self.block or "Global"}>'


# ---- Payroll Reward Model ----
class PayrollReward(db.Model):
    __tablename__ = 'payroll_rewards'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PayrollReward {self.name}: ${self.amount}>'


# ---- Payroll Fine Model ----
class PayrollFine(db.Model):
    __tablename__ = 'payroll_fines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)  # Positive value, will be deducted
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PayrollFine {self.name}: -${self.amount}>'


# ---- Banking Settings Model ----
class BankingSettings(db.Model):
    __tablename__ = 'banking_settings'
    id = db.Column(db.Integer, primary_key=True)

    # Interest settings for savings
    savings_apy = db.Column(db.Float, default=0.0)  # Annual Percentage Yield (e.g., 5.0 for 5%)
    savings_monthly_rate = db.Column(db.Float, default=0.0)  # Monthly rate (calculated or custom)

    # Interest payout schedule
    interest_schedule_type = db.Column(db.String(20), default='monthly')  # 'weekly', 'monthly'
    interest_schedule_cycle_days = db.Column(db.Integer, default=30)  # For monthly: 30 day cycle
    interest_payout_start_date = db.Column(db.DateTime, nullable=True)  # Starting date for payouts

    # Overdraft protection
    overdraft_protection_enabled = db.Column(db.Boolean, default=False)  # If enabled, savings covers checking

    # Overdraft/NSF fees
    overdraft_fee_enabled = db.Column(db.Boolean, default=False)  # Enable/disable overdraft fees
    overdraft_fee_type = db.Column(db.String(20), default='flat')  # 'flat' or 'progressive'
    overdraft_fee_flat_amount = db.Column(db.Float, default=0.0)  # Flat fee per transaction

    # Progressive fee settings
    overdraft_fee_progressive_1 = db.Column(db.Float, default=0.0)  # First tier fee
    overdraft_fee_progressive_2 = db.Column(db.Float, default=0.0)  # Second tier fee
    overdraft_fee_progressive_3 = db.Column(db.Float, default=0.0)  # Third tier fee
    overdraft_fee_progressive_cap = db.Column(db.Float, nullable=True)  # Maximum total fees per period

    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<BankingSettings APY:{self.savings_apy}% OD:{self.overdraft_protection_enabled}>'
