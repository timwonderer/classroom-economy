"""
Database models for Classroom Token Hub.

All SQLAlchemy models are defined here with proper relationships and properties.
Times are stored as UTC in the database.
"""

from datetime import datetime, timedelta, timezone
import enum

from app.extensions import db
from app.utils.encryption import PIIEncryptedType


def _utc_now():
    """Helper function for timezone-aware datetime defaults in SQLAlchemy models."""
    return datetime.now(timezone.utc)


# -------------------- MODELS --------------------

class TeacherBlock(db.Model):
    """
    Represents an unclaimed seat in a teacher's class roster.

    When a teacher uploads a roster, each student creates a TeacherBlock entry (a "seat").
    Students claim their seat by providing the period join code + their credentials.
    Once claimed, the seat links to a Student record via student_id.

    This model enables:
    - Join code-based account claiming (eliminates need for students to know teacher name)
    - Multi-school support (join codes implicitly partition schools)
    - Duplicate prevention (same student claiming across multiple teachers)
    """
    __tablename__ = 'teacher_blocks'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False)
    block = db.Column(db.String(10), nullable=False)  # Legacy technical identifier
    class_label = db.Column(db.String(50), nullable=True)  # Teacher-customizable display name for this class

    # Student identifiers (used for matching during claim)
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_initial = db.Column(db.String(1), nullable=False)

    # Fuzzy name matching - stores hash of each last name part separately
    # Example: "Smith-Jones" → ["hash(smith)", "hash(jones)"]
    last_name_hash_by_part = db.Column(db.JSON, nullable=False)

    # Privacy-aligned DOB sum for verification (non-reversible)
    dob_sum = db.Column(db.Integer, nullable=False)

    # Hashing
    salt = db.Column(db.LargeBinary(16), nullable=False)
    first_half_hash = db.Column(db.String(64), nullable=False)  # Hash of CONCAT(first_initial, DOB_sum) - e.g., "S2025"

    # Join code for this period (shared across all students in same teacher-block)
    join_code = db.Column(db.String(20), nullable=False)

    # Claim status
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    is_claimed = db.Column(db.Boolean, default=False, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=_utc_now)
    claimed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('roster_seats', lazy='dynamic', passive_deletes=True))
    student = db.relationship('Student', backref='roster_seats')

    # Indexes for efficient lookups
    __table_args__ = (
        db.Index('ix_teacher_blocks_join_code', 'join_code'),
        db.Index('ix_teacher_blocks_teacher_block', 'teacher_id', 'block'),
        db.Index('ix_teacher_blocks_claimed', 'is_claimed'),
    )

    def get_class_label(self):
        """Return class_label if set, otherwise fall back to block"""
        return self.class_label if self.class_label else self.block

    def __repr__(self):
        status = "claimed" if self.is_claimed else "unclaimed"
        return f'<TeacherBlock {self.first_name} {self.last_initial}. - {self.teacher_id}/{self.block} - {status}>'


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_initial = db.Column(db.String(1), nullable=False)
    block = db.Column(db.String(10), nullable=False)

    # Hash and credential fields
    # Credential: CONCAT(first_initial, DOB_sum) - simpler than old name_code system
    salt = db.Column(db.LargeBinary(16), nullable=False)
    first_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Hash of "FirstInitial + DOBSum" (e.g., "S2025")
    second_half_hash = db.Column(db.String(64), unique=True, nullable=True)  # Hash of DOB sum (backward compat)
    username_hash = db.Column(db.String(64), unique=True, nullable=True)
    username_lookup_hash = db.Column(db.String(64), unique=True, nullable=True)

    # Fuzzy name matching - stores hash of each last name part separately
    # Example: "Smith-Jones" → ["hash(smith)", "hash(jones)"]
    # Allows matching when teachers enter names with different delimiters
    last_name_hash_by_part = db.Column(db.JSON, nullable=True)

    # Ownership / tenancy
    # DEPRECATED: teacher_id will be removed in future migration
    # Students are now linked to teachers via student_teachers table only
    # This column kept temporarily for backwards compatibility during migration
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    teacher = db.relationship('Admin', backref=db.backref('students', lazy='dynamic'))

    # Teachers associated with this student (many-to-many)
    teachers = db.relationship(
        'Admin',
        secondary='student_teachers',
        backref=db.backref('linked_students', lazy='dynamic'),
        lazy='dynamic',
    )

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
    # Track if student has completed the legacy profile migration
    has_completed_profile_migration = db.Column(db.Boolean, default=False)

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

    def get_active_insurance(self, teacher_id):
        """Return the active insurance enrollment scoped to a teacher, if any."""
        if not teacher_id:
            return None

        return StudentInsurance.query.join(
            InsurancePolicy, StudentInsurance.policy_id == InsurancePolicy.id
        ).filter(
            StudentInsurance.student_id == self.id,
            StudentInsurance.status == 'active',
            InsurancePolicy.teacher_id == teacher_id
        ).first()

    def get_checking_balance(self, teacher_id=None, join_code=None):
        """
        Get checking balance scoped to a specific class economy.

        CRITICAL: For proper period isolation, callers should pass join_code.
        The teacher_id parameter is deprecated and only kept for backward compatibility.

        Args:
            teacher_id: DEPRECATED - Only for backward compatibility
            join_code: The unique class identifier for period-level isolation

        Returns:
            float: The checking balance rounded to 2 decimal places
        """
        if join_code:
            # Proper scoping by join_code (period-level isolation)
            # Include legacy transactions with NULL join_code but matching teacher_id
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'checking' and not tx.is_void and (
                    tx.join_code == join_code or (tx.join_code is None and teacher_id and tx.teacher_id == teacher_id)
                )
            ), 2)
        elif teacher_id:
            # DEPRECATED: Only use this for backward compatibility during migration
            # This will show aggregated balance across all periods with same teacher
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'checking' and not tx.is_void and tx.teacher_id == teacher_id
            ), 2)
        else:
            # No scope provided - return total across all classes
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'checking' and not tx.is_void
            ), 2)

    def get_savings_balance(self, teacher_id=None, join_code=None):
        """
        Get savings balance scoped to a specific class economy.

        CRITICAL: For proper period isolation, callers should pass join_code.
        The teacher_id parameter is deprecated and only kept for backward compatibility.

        Args:
            teacher_id: DEPRECATED - Only for backward compatibility
            join_code: The unique class identifier for period-level isolation

        Returns:
            float: The savings balance rounded to 2 decimal places
        """
        if join_code:
            # Proper scoping by join_code (period-level isolation)
            # Include legacy transactions with NULL join_code but matching teacher_id
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'savings' and not tx.is_void and (
                    tx.join_code == join_code or (tx.join_code is None and teacher_id and tx.teacher_id == teacher_id)
                )
            ), 2)
        elif teacher_id:
            # DEPRECATED: Only use this for backward compatibility during migration
            # This will show aggregated balance across all periods with same teacher
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'savings' and not tx.is_void and tx.teacher_id == teacher_id
            ), 2)
        else:
            # No scope provided - return total across all classes
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.account_type == 'savings' and not tx.is_void
            ), 2)

    def get_total_earnings(self, teacher_id=None, join_code=None):
        """
        Get total earnings scoped to a specific class economy.

        CRITICAL: For proper period isolation, callers should pass join_code.
        The teacher_id parameter is deprecated and only kept for backward compatibility.

        Args:
            teacher_id: DEPRECATED - Only for backward compatibility
            join_code: The unique class identifier for period-level isolation

        Returns:
            float: The total earnings rounded to 2 decimal places
        """
        if join_code:
            # Proper scoping by join_code (period-level isolation)
            # Include legacy transactions with NULL join_code but matching teacher_id
            return round(sum(
                tx.amount for tx in self.transactions
                if (tx.join_code == join_code or (tx.join_code is None and teacher_id and tx.teacher_id == teacher_id))
                and tx.amount > 0 and not tx.is_void
                and not (tx.description or "").startswith("Transfer")
            ), 2)
        elif teacher_id:
            # DEPRECATED: Only use this for backward compatibility during migration
            # This will show aggregated earnings across all periods with same teacher
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.teacher_id == teacher_id and tx.amount > 0 and not tx.is_void
                and not (tx.description or "").startswith("Transfer")
            ), 2)
        else:
            # No scope provided - return total across all classes
            return round(sum(
                tx.amount for tx in self.transactions
                if tx.amount > 0 and not tx.is_void
                and not (tx.description or "").startswith("Transfer")
            ), 2)

    def get_all_teachers(self):
        """
        Get list of all teachers this student is associated with.

        Uses the student_teachers many-to-many relationship.
        DEPRECATED teacher_id is ignored in favor of explicit links only.
        """
        return list(self.teachers.all())

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
    created_at = db.Column(db.DateTime, default=_utc_now)


class StudentTeacher(db.Model):
    __tablename__ = 'student_teachers'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'admin_id', name='uq_student_teachers_student_admin'),
        db.Index('ix_student_teachers_student_id', 'student_id'),
        db.Index('ix_student_teachers_admin_id', 'admin_id'),
    )


class DeletionRequestType(enum.Enum):
    """Enum for deletion request types."""
    PERIOD = 'period'
    ACCOUNT = 'account'
    
    @classmethod
    def from_string(cls, value):
        """Convert string to enum, raising ValueError if invalid."""
        if isinstance(value, cls):
            return value
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid DeletionRequestType: {value}")


class DeletionRequestStatus(enum.Enum):
    """Enum for deletion request statuses."""
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class DeletionRequest(db.Model):
    """
    Tracks teacher requests for period/block or account deletion.
    System admins can only approve deletions that have been requested by teachers
    or for accounts that have been inactive beyond the threshold.
    """
    __tablename__ = 'deletion_requests'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False)
    request_type = db.Column(db.Enum(DeletionRequestType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    period = db.Column(db.String(10), nullable=True)  # Specified for period deletions only
    reason = db.Column(db.Text, nullable=True)  # Optional reason from teacher
    status = db.Column(db.Enum(DeletionRequestStatus, values_callable=lambda x: [e.value for e in x]), default=DeletionRequestStatus.PENDING, nullable=False)
    requested_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('system_admins.id'), nullable=True)

    # Relationships
    # No ORM cascade needed - explicit deletion in system_admin.py:871 + DB CASCADE
    admin = db.relationship('Admin', backref=db.backref('deletion_requests', lazy='dynamic'))
    resolver = db.relationship('SystemAdmin', backref=db.backref('resolved_deletion_requests', lazy='dynamic'))

    __table_args__ = (
        db.Index('ix_deletion_requests_admin_id', 'admin_id'),
        db.Index('ix_deletion_requests_status', 'status'),
    )

    def __repr__(self):
        return f'<DeletionRequest {self.request_type} for Admin {self.admin_id} - {self.status}>'


# -------------------- SYSTEM ADMIN MODEL --------------------
class SystemAdmin(db.Model):
    __tablename__ = 'system_admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    totp_secret = db.Column(db.String(32), nullable=False)


class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)

    # CRITICAL: join_code is the source of truth for class isolation
    # Each join code represents a distinct class economy, even if same teacher
    # Example: Teacher has Period A (join=MATH1A) and Period B (join=MATH3B)
    # Student in both periods should see separate balances/transactions
    join_code = db.Column(db.String(20), nullable=True, index=True)

    amount = db.Column(db.Float, nullable=False)
    # All times stored as UTC (see header note)
    timestamp = db.Column(db.DateTime, default=_utc_now)
    account_type = db.Column(db.String(20), default='checking')
    description = db.Column(db.String(255))
    is_void = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50))  # optional field to describe the transaction type
    # All times stored as UTC
    date_funds_available = db.Column(db.DateTime, default=_utc_now)

    # Relationship to track which teacher created this transaction
    teacher = db.relationship('Admin', backref=db.backref('transactions', lazy='dynamic'))


# ---- TapEvent Model (append-only) ----
class StudentBlock(db.Model):
    """
    Stores per-student, per-period settings and state.
    """
    __tablename__ = 'student_blocks'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    period = db.Column(db.String(10), nullable=False)

    # Toggle for enabling/disabling tap in/out for this student in this period
    tap_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # When student marks "done for the day", store the date (Pacific time)
    # This locks them out until 11:59 PM same day
    done_for_day_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    student = db.relationship("Student", backref=db.backref("student_blocks", passive_deletes=True))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'period', name='uq_student_blocks_student_period'),
        db.Index('ix_student_blocks_student_id', 'student_id'),
        db.Index('ix_student_blocks_period', 'period'),
    )


class TapEvent(db.Model):
    __tablename__ = 'tap_events'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    period = db.Column(db.String(10), nullable=False)
    # CRITICAL: join_code scopes attendance to a specific class economy
    join_code = db.Column(db.String(20), nullable=True, index=True)
    status = db.Column(db.String(10), nullable=False)  # 'active' or 'inactive'
    # All times stored as UTC (see header note)
    timestamp = db.Column(db.DateTime, default=_utc_now)
    reason = db.Column(db.String(50), nullable=True)

    # Flag to indicate if this event was deleted by a teacher
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='SET NULL'), nullable=True)

    student = db.relationship("Student", backref="tap_events")
    deleted_by_admin = db.relationship("Admin", foreign_keys=[deleted_by])


# ---- Hall Pass Log Model ----
class HallPassLog(db.Model):
    __tablename__ = 'hall_pass_logs'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False) # pending, approved, rejected, left, returned
    pass_number = db.Column(db.String(3), nullable=True, unique=True) # Format: letter + 2 digits (e.g., A42)
    period = db.Column(db.String(10), nullable=True) # Which period the request was made in

    # CRITICAL: join_code is the source of truth for class isolation
    # Each hall pass request should be scoped to the specific class/period
    join_code = db.Column(db.String(20), nullable=True, index=True)

    request_time = db.Column(db.DateTime, default=_utc_now, nullable=False)
    decision_time = db.Column(db.DateTime, nullable=True)
    left_time = db.Column(db.DateTime, nullable=True)
    return_time = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref='hall_pass_logs')


class HallPassSettings(db.Model):
    __tablename__ = 'hall_pass_settings'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global default, otherwise period/block identifier

    # Queue system toggle
    queue_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Queue limit (when queue + currently out >= this number, restrict certain passes)
    queue_limit = db.Column(db.Integer, default=10, nullable=False)

    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('hall_pass_settings', lazy='dynamic'))


# -------------------- STORE MODELS --------------------

class StoreItem(db.Model):
    __tablename__ = 'store_items'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    tier = db.Column(db.String(20), nullable=True) # basic, standard, premium, luxury (teacher-only organizational label)
    item_type = db.Column(db.String(20), nullable=False, default='delayed') # immediate, delayed, collective
    inventory = db.Column(db.Integer, nullable=True) # null for unlimited
    limit_per_student = db.Column(db.Integer, nullable=True) # null for no limit
    auto_delist_date = db.Column(db.DateTime, nullable=True)
    auto_expiry_days = db.Column(db.Integer, nullable=True) # days student has to use the item
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_long_term_goal = db.Column(db.Boolean, default=False, nullable=False) # if true, exclude from CWI balance checks

    # Bundle settings
    is_bundle = db.Column(db.Boolean, default=False, nullable=False)
    bundle_quantity = db.Column(db.Integer, nullable=True) # number of items in bundle (e.g., 5)

    # Bulk discount settings
    bulk_discount_enabled = db.Column(db.Boolean, default=False, nullable=False)
    bulk_discount_quantity = db.Column(db.Integer, nullable=True) # minimum quantity for discount
    bulk_discount_percentage = db.Column(db.Float, nullable=True) # discount percentage (e.g., 10 for 10%)

    # Collective goal settings (only for item_type='collective')
    collective_goal_type = db.Column(db.String(20), nullable=True)  # 'fixed' or 'whole_class'
    collective_goal_target = db.Column(db.Integer, nullable=True)  # Fixed number of purchases needed (used when type='fixed')

    # Redemption prompt (for delayed use items)
    redemption_prompt = db.Column(db.Text, nullable=True)  # Optional prompt shown to students when redeeming delayed items

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('store_items', lazy='dynamic'))
    student_items = db.relationship('StudentItem', backref='store_item', lazy=True)

    # Many-to-many relationship for block visibility
    visible_blocks = db.relationship(
        'StoreItemBlock',
        backref='store_item',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    @property
    def blocks_list(self):
        """Return list of block names this item is visible to (empty list means all blocks)."""
        return [b.block for b in self.visible_blocks]

    def set_blocks(self, block_list):
        """Set the blocks this item is visible to. Pass empty list for all blocks."""
        # Clear existing blocks
        StoreItemBlock.query.filter_by(store_item_id=self.id).delete()
        # Add new blocks
        if block_list:
            db.session.add_all([
                StoreItemBlock(store_item_id=self.id, block=block.strip().upper())
                for block in block_list
            ])


class StoreItemBlock(db.Model):
    """Association model for store item block visibility."""
    __tablename__ = 'store_item_blocks'
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id', ondelete='CASCADE'), primary_key=True)
    block = db.Column(db.String(10), primary_key=True)

    __table_args__ = (
        db.Index('ix_store_item_blocks_item', 'store_item_id'),
        db.Index('ix_store_item_blocks_block', 'block'),
    )


class StudentItem(db.Model):
    __tablename__ = 'student_items'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id'), nullable=False)

    # CRITICAL: join_code is the source of truth for class isolation
    # Each purchase should be scoped to the specific class/period where it was made
    join_code = db.Column(db.String(20), nullable=True, index=True)

    purchase_date = db.Column(db.DateTime, default=_utc_now)
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
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global default, otherwise period/block identifier

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
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('rent_settings', lazy='dynamic'))

    # Keep old field names for backward compatibility (deprecated)
    @property
    def late_fee(self):
        return self.late_penalty_amount


class RentPayment(db.Model):
    __tablename__ = 'rent_payments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # Block/Period (e.g., 'A', 'B', 'C')

    # CRITICAL: join_code is the source of truth for class isolation
    # Each rent payment should be scoped to the specific class/period
    join_code = db.Column(db.String(20), nullable=True, index=True)

    amount_paid = db.Column(db.Float, nullable=False)
    period_month = db.Column(db.Integer, nullable=False)  # Month (1-12)
    period_year = db.Column(db.Integer, nullable=False)  # Year (e.g., 2025)
    payment_date = db.Column(db.DateTime, default=_utc_now)
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
    created_at = db.Column(db.DateTime, default=_utc_now)

    student = db.relationship('Student', backref='rent_waivers')
    created_by = db.relationship('Admin', backref='rent_waivers_created')


# -------------------- INSURANCE MODELS --------------------
class InsurancePolicy(db.Model):
    __tablename__ = 'insurance_policies'
    id = db.Column(db.Integer, primary_key=True)
    policy_code = db.Column(db.String(16), unique=True, nullable=False, index=True)  # Unique code per teacher's policy
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)  # Owner teacher
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    premium = db.Column(db.Float, nullable=False)  # Monthly cost
    charge_frequency = db.Column(db.String(20), default='monthly')  # monthly, weekly, etc
    autopay = db.Column(db.Boolean, default=True)
    waiting_period_days = db.Column(db.Integer, default=7)  # Days before coverage starts
    max_claims_count = db.Column(db.Integer, nullable=True)  # Max claims per period (null = unlimited)
    max_claims_period = db.Column(db.String(20), default='month')  # month, semester, year
    max_claim_amount = db.Column(db.Float, nullable=True)  # Max $ per claim (null = unlimited)
    max_payout_per_period = db.Column(db.Float, nullable=True)  # Max total $ payout per period (null = unlimited)

    # Claim type
    claim_type = db.Column(db.String(20), nullable=False, default='legacy_monetary')  # transaction_monetary, non_monetary, legacy_monetary
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

    # Marketing badge for student-facing display
    marketing_badge = db.Column(db.String(50), nullable=True)  # Predefined badge options

    # Tier/Category support for grouped insurance (e.g., paycheck protection tiers)
    tier_category_id = db.Column(db.Integer, nullable=True)  # Groups policies that are mutually exclusive
    tier_name = db.Column(db.String(100), nullable=True)  # Display name for the tier (e.g., "Paycheck Protection")
    tier_color = db.Column(db.String(20), nullable=True)  # Color theme for the tier (e.g., "primary", "success", "warning")

    # Settings mode: simple or advanced
    settings_mode = db.Column(db.String(20), nullable=True, default='advanced')  # simple or advanced

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', foreign_keys=[teacher_id], backref='insurance_policies_owned')
    student_policies = db.relationship('StudentInsurance', backref='policy', lazy='dynamic')
    claims = db.relationship('InsuranceClaim', backref='policy', lazy='dynamic')

    # Many-to-many relationship for block visibility
    visible_blocks = db.relationship(
        'InsurancePolicyBlock',
        backref='policy',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    @property
    def blocks_list(self):
        """Return list of block names this policy is visible to (empty list means all blocks)."""
        return [b.block for b in self.visible_blocks]

    def set_blocks(self, block_list):
        """Set the blocks this policy is visible to. Pass empty list for all blocks."""
        # Clear existing blocks
        InsurancePolicyBlock.query.filter_by(policy_id=self.id).delete()
        # Add new blocks
        if block_list:
            db.session.add_all([
                InsurancePolicyBlock(policy_id=self.id, block=block.strip().upper())
                for block in block_list
            ])

    @property
    def is_monetary_claim(self):
        return self.claim_type != 'non_monetary'


class InsurancePolicyBlock(db.Model):
    """Association model for insurance policy block visibility."""
    __tablename__ = 'insurance_policy_blocks'
    policy_id = db.Column(db.Integer, db.ForeignKey('insurance_policies.id', ondelete='CASCADE'), primary_key=True)
    block = db.Column(db.String(10), primary_key=True)

    __table_args__ = (
        db.Index('ix_insurance_policy_blocks_policy', 'policy_id'),
        db.Index('ix_insurance_policy_blocks_block', 'block'),
    )


class StudentInsurance(db.Model):
    __tablename__ = 'student_insurance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey('insurance_policies.id'), nullable=False)

    # CRITICAL: join_code is the source of truth for class isolation
    # Each insurance enrollment should be scoped to the specific class/period
    join_code = db.Column(db.String(20), nullable=True, index=True)

    status = db.Column(db.String(20), default='active')  # active, cancelled, suspended
    purchase_date = db.Column(db.DateTime, default=_utc_now)
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
    __table_args__ = (
        db.UniqueConstraint('transaction_id', name='uq_insurance_claims_transaction_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    student_insurance_id = db.Column(db.Integer, db.ForeignKey('student_insurance.id'), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey('insurance_policies.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    incident_date = db.Column(db.DateTime, nullable=False)  # When incident occurred
    filed_date = db.Column(db.DateTime, default=_utc_now)
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
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)

    # Relationships
    student = db.relationship('Student', backref='insurance_claims')
    processed_by = db.relationship('Admin', backref='processed_claims')
    transaction = db.relationship('Transaction', backref='insurance_claims')


# ---- Error Log Model ----
class ErrorLog(db.Model):
    __tablename__ = 'error_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=_utc_now, nullable=False, index=True)
    error_type = db.Column(db.String(100), nullable=True)  # Type of error (e.g., Exception class name)
    error_message = db.Column(db.Text, nullable=True)  # Error message
    request_path = db.Column(db.String(500), nullable=True)  # URL path that caused the error
    request_method = db.Column(db.String(10), nullable=True)  # HTTP method (GET, POST, etc.)
    user_agent = db.Column(db.String(500), nullable=True)  # Browser/client info
    ip_address = db.Column(db.String(50), nullable=True)  # IP address of requester
    log_output = db.Column(db.Text, nullable=False)  # Last 50 lines of log
    stack_trace = db.Column(db.Text, nullable=True)  # Full stack trace


# ---- User Report Model (Bug Reports, Suggestions, Comments) ----
class UserReport(db.Model):
    __tablename__ = 'user_reports'
    id = db.Column(db.Integer, primary_key=True)

    # Anonymous user identification (HMAC of user identifier)
    anonymous_code = db.Column(db.String(64), nullable=False, index=True)
    user_type = db.Column(db.String(20), nullable=False)  # 'student', 'teacher', 'anonymous'

    # Report details
    report_type = db.Column(db.String(20), nullable=False, default='bug')  # 'bug', 'suggestion', 'comment'
    error_code = db.Column(db.String(10), nullable=True)  # HTTP error code (404, 500, etc.) if applicable
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)  # What happened
    steps_to_reproduce = db.Column(db.Text, nullable=True)  # What they did before the error
    expected_behavior = db.Column(db.Text, nullable=True)  # What they expected to happen
    page_url = db.Column(db.String(500), nullable=True)  # URL where error occurred

    # Metadata
    submitted_at = db.Column(db.DateTime, default=_utc_now, nullable=False, index=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Admin management
    status = db.Column(db.String(20), default='new', nullable=False)  # 'new', 'reviewed', 'rewarded', 'closed', 'spam'
    admin_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_sysadmin_id = db.Column(db.Integer, db.ForeignKey('system_admins.id'), nullable=True)

    # Reward tracking (for legitimate bugs)
    reward_amount = db.Column(db.Float, nullable=True, default=0.0)
    reward_sent_at = db.Column(db.DateTime, nullable=True)

    # Internal student ID (hidden from sysadmin, used only for reward routing)
    _student_id = db.Column('student_id', db.Integer, db.ForeignKey('students.id'), nullable=True)
    student = db.relationship(
        'Student',
        backref=db.backref('reports', cascade='all, delete-orphan'),
        foreign_keys=[_student_id],
    )

    reviewed_by = db.relationship('SystemAdmin', backref='reviewed_reports', foreign_keys=[reviewed_by_sysadmin_id])


# ---- Admin Model ----
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=True)  # Teacher's display name (defaults to username if not set)
    # TOTP-only: store secret, remove password_hash
    totp_secret = db.Column(db.String(32), nullable=False)
    # Account recovery: Hashed DOB sum (similar to student system)
    dob_sum_hash = db.Column(db.String(64), nullable=True)  # Hashed Sum of MM + DD + YYYY
    salt = db.Column(db.LargeBinary(16), nullable=True)  # Salt for DOB sum hash
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=True)  # Nullable for existing records
    last_login = db.Column(db.DateTime, nullable=True)
    has_assigned_students = db.Column(db.Boolean, default=False, nullable=False)  # One-time setup flag

    def get_display_name(self):
        """Return display_name if set, otherwise fall back to username"""
        return self.display_name if self.display_name else self.username


# ---- Account Recovery Models ----
class RecoveryRequest(db.Model):
    """Teacher account recovery request - requires student verification"""
    __tablename__ = 'recovery_requests'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False, index=True)
    dob_sum_hash = db.Column(db.String(64), nullable=True)  # Hashed input for verification trail

    # Status tracking
    status = db.Column(
        db.Enum('pending', 'verified', 'expired', 'cancelled', name='recovery_request_status_enum'),
        nullable=False,
        default='pending'
    )  # pending, verified, expired, cancelled
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # Auto-expire after X days
    completed_at = db.Column(db.DateTime, nullable=True)

    # Partial progress - allows teacher to save progress and resume later
    partial_codes = db.Column(db.JSON, nullable=True)  # Array of entered codes (not yet validated)
    resume_pin_hash = db.Column(db.String(64), nullable=True)  # Hashed PIN to resume progress
    resume_new_username = db.Column(db.String(100), nullable=True)  # Temporary storage for new username

    # Relationships
    admin = db.relationship('Admin', backref=db.backref('recovery_requests', lazy='dynamic'))
    verification_codes = db.relationship('StudentRecoveryCode', backref='recovery_request', lazy='dynamic', cascade='all, delete-orphan')


class StudentRecoveryCode(db.Model):
    """Student verification code for teacher account recovery"""
    __tablename__ = 'student_recovery_codes'

    id = db.Column(db.Integer, primary_key=True)
    recovery_request_id = db.Column(db.Integer, db.ForeignKey('recovery_requests.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)

    # Verification code (6-digit, hashed)
    code_hash = db.Column(db.String(64), nullable=True)  # NULL until student verifies
    verified_at = db.Column(db.DateTime, nullable=True)

    # Notification tracking
    notified_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    dismissed = db.Column(db.Boolean, default=False, nullable=False)  # Student dismissed notification

    # Relationships
    student = db.relationship('Student', backref=db.backref('recovery_codes', lazy='dynamic'))


# ---- Payroll Settings Model ----
class PayrollSettings(db.Model):
    __tablename__ = 'payroll_settings'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global/default settings
    pay_rate = db.Column(db.Float, nullable=False, default=0.25)  # $ per minute
    payroll_frequency_days = db.Column(db.Integer, nullable=False, default=14)
    next_payroll_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

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

    # Economy Balance Check Field
    # NOTE: This is NOT used for actual payroll calculations - only for economy balance validation
    expected_weekly_hours = db.Column(db.Float, nullable=True, default=5.0)  # Expected class hours per week

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('payroll_settings', lazy='dynamic'))

    def __repr__(self):
        return f'<PayrollSettings {self.block or "Global"}>'


# ---- Payroll Reward Model ----
class PayrollReward(db.Model):
    __tablename__ = 'payroll_rewards'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('payroll_rewards', lazy='dynamic'))

    def __repr__(self):
        return f'<PayrollReward {self.name}: ${self.amount}>'


# ---- Payroll Fine Model ----
class PayrollFine(db.Model):
    __tablename__ = 'payroll_fines'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)  # Positive value, will be deducted
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('payroll_fines', lazy='dynamic'))

    def __repr__(self):
        return f'<PayrollFine {self.name}: -${self.amount}>'


# ---- Banking Settings Model ----
class BankingSettings(db.Model):
    __tablename__ = 'banking_settings'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global default, otherwise period/block identifier

    # Interest settings for savings
    savings_apy = db.Column(db.Float, default=0.0)  # Annual Percentage Yield (e.g., 5.0 for 5%)
    savings_monthly_rate = db.Column(db.Float, default=0.0)  # Monthly rate (calculated or custom)
    interest_calculation_type = db.Column(db.String(20), default='simple')  # 'simple' or 'compound'
    compound_frequency = db.Column(db.String(20), default='monthly')  # 'daily', 'weekly', 'monthly'

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
    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('banking_settings', lazy='dynamic'))

    def __repr__(self):
        return f'<BankingSettings APY:{self.savings_apy}% OD:{self.overdraft_protection_enabled}>'


# -------------------- DEMO STUDENT MODEL --------------------
class DemoStudent(db.Model):
    """
    Tracks demo student sessions created by admins for testing the student experience.
    Demo sessions auto-expire after 10 minutes and store all actions separately.
    """
    __tablename__ = 'demo_students'
    id = db.Column(db.Integer, primary_key=True)

    # Admin who created this demo session
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)

    # The temporary student record created for this demo
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    # Session tracking
    session_id = db.Column(db.String(255), nullable=False, unique=True)  # Flask session ID
    created_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # Auto-cleanup after 10 minutes
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)

    # Demo configuration (snapshot of initial state)
    config_checking_balance = db.Column(db.Float, default=0.0)
    config_savings_balance = db.Column(db.Float, default=0.0)
    config_hall_passes = db.Column(db.Integer, default=3)
    config_insurance_plan = db.Column(db.String(50), default='none')
    config_is_rent_enabled = db.Column(db.Boolean, default=True)
    config_period = db.Column(db.String(10), default='A')

    # Relationships
    admin = db.relationship('Admin', backref='demo_sessions')
    student = db.relationship('Student', backref='demo_sessions', foreign_keys=[student_id])

    def __repr__(self):
        status = 'active' if self.is_active else 'ended'
        return f'<DemoStudent admin_id={self.admin_id} student_id={self.student_id} {status}>'


# -------------------- FEATURE SETTINGS MODEL --------------------
class FeatureSettings(db.Model):
    """
    Per-period/block feature toggle settings for a teacher.

    Allows teachers to enable/disable major features on a per-period basis.
    If block is NULL, settings apply as global defaults for the teacher.
    Period-specific settings override global defaults.

    Features that can be toggled:
    - Payroll (time tracking & payments)
    - Insurance (policy marketplace & claims)
    - Banking (savings, interest, overdraft)
    - Rent (housing costs)
    - Hall Pass (bathroom/water breaks)
    - Store (marketplace for rewards)
    - Bug Reports (allow students to report issues)
    - Bug Rewards (reward students for valid bug reports)
    """
    __tablename__ = 'feature_settings'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False)
    block = db.Column(db.String(10), nullable=True)  # NULL = global defaults for teacher

    # Feature toggles - all default to True (enabled)
    payroll_enabled = db.Column(db.Boolean, default=True, nullable=False)
    insurance_enabled = db.Column(db.Boolean, default=True, nullable=False)
    banking_enabled = db.Column(db.Boolean, default=True, nullable=False)
    rent_enabled = db.Column(db.Boolean, default=True, nullable=False)
    hall_pass_enabled = db.Column(db.Boolean, default=True, nullable=False)
    store_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Bug report settings
    bug_reports_enabled = db.Column(db.Boolean, default=True, nullable=False)
    bug_rewards_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=_utc_now)
    updated_at = db.Column(db.DateTime, default=_utc_now, onupdate=_utc_now)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('feature_settings', lazy='dynamic', passive_deletes=True))

    # Unique constraint: one settings row per teacher-block combination
    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'block', name='uq_feature_settings_teacher_block'),
        db.Index('ix_feature_settings_teacher_id', 'teacher_id'),
    )

    def __repr__(self):
        block_str = self.block or 'Global'
        return f'<FeatureSettings teacher={self.teacher_id} block={block_str}>'

    def to_dict(self):
        """Return feature settings as a dictionary."""
        return {
            'payroll_enabled': self.payroll_enabled,
            'insurance_enabled': self.insurance_enabled,
            'banking_enabled': self.banking_enabled,
            'rent_enabled': self.rent_enabled,
            'hall_pass_enabled': self.hall_pass_enabled,
            'store_enabled': self.store_enabled,
            'bug_reports_enabled': self.bug_reports_enabled,
            'bug_rewards_enabled': self.bug_rewards_enabled,
        }

    @classmethod
    def get_defaults(cls):
        """Return default feature settings dictionary."""
        return {
            'payroll_enabled': True,
            'insurance_enabled': True,
            'banking_enabled': True,
            'rent_enabled': True,
            'hall_pass_enabled': True,
            'store_enabled': True,
            'bug_reports_enabled': True,
            'bug_rewards_enabled': True,
        }


# -------------------- TEACHER ONBOARDING MODEL --------------------
class TeacherOnboarding(db.Model):
    """
    Tracks onboarding progress for teachers.

    New teachers are guided through an initial setup process that helps them:
    1. Understand the platform features
    2. Configure feature toggles
    3. Set up their first period/block
    4. Upload their roster
    5. Configure basic settings (payroll, rent, etc.)

    Once completed, teachers can access the regular dashboard.
    Onboarding can be skipped but the flag is preserved for potential re-entry.
    """
    __tablename__ = 'teacher_onboarding'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Onboarding status
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    is_skipped = db.Column(db.Boolean, default=False, nullable=False)

    # Step tracking (for resume functionality)
    current_step = db.Column(db.Integer, default=1, nullable=False)
    total_steps = db.Column(db.Integer, default=5, nullable=False)

    # Detailed step completion tracking (JSON for flexibility)
    # Format: {"welcome": true, "features": true, "periods": false, "roster": false, "settings": false}
    steps_completed = db.Column(db.JSON, default=dict, nullable=False)

    # Timestamps
    started_at = db.Column(db.DateTime, default=_utc_now, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    skipped_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, default=_utc_now, nullable=False)

    # Relationships
    teacher = db.relationship('Admin', backref=db.backref('onboarding', uselist=False, passive_deletes=True))

    def __repr__(self):
        status = 'completed' if self.is_completed else ('skipped' if self.is_skipped else 'in_progress')
        return f'<TeacherOnboarding teacher={self.teacher_id} step={self.current_step}/{self.total_steps} status={status}>'

    def mark_step_completed(self, step_name):
        """Mark a specific step as completed."""
        from sqlalchemy.orm.attributes import flag_modified
        if self.steps_completed is None:
            self.steps_completed = {}
        self.steps_completed[step_name] = True
        flag_modified(self, 'steps_completed')
        self.last_activity_at = datetime.now(timezone.utc)

    def is_step_completed(self, step_name):
        """Check if a specific step is completed."""
        if self.steps_completed is None:
            return False
        return self.steps_completed.get(step_name, False)

    def complete_onboarding(self):
        """Mark the onboarding as completed."""
        self.is_completed = True
        self.completed_at = datetime.now(timezone.utc)
        self.last_activity_at = datetime.now(timezone.utc)

    def skip_onboarding(self):
        """Mark the onboarding as skipped."""
        self.is_skipped = True
        self.skipped_at = datetime.now(timezone.utc)
        self.last_activity_at = datetime.now(timezone.utc)

    @property
    def needs_onboarding(self):
        """Check if teacher needs to complete onboarding."""
        return not self.is_completed and not self.is_skipped
