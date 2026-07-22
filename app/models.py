"""
Database models for Classroom Token Hub.

All SQLAlchemy models are defined here with proper relationships and properties.
Times are stored as UTC in the database.
"""

from datetime import timezone, timedelta
from decimal import Decimal, InvalidOperation
import enum
import logging
import secrets
import uuid

import pytz
import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, validates, synonym
from sqlalchemy import event
from app.extensions import db
from app.hash_utils import get_random_salt, hash_hmac, hash_username, hash_username_lookup
from app.utils.encryption import PIIEncryptedType, normalize_totp_for_storage
from app.utils.time import utc_now, ensure_utc

logger = logging.getLogger(__name__)


def _quantize_currency(value):
    """
    Convert a value to Decimal and quantize to 2 decimal places for currency.

    This ensures exact decimal representation and fixes floating-point errors
    like -0.00 overdraft fees and unpayable rent balances.

    Args:
        value: A Decimal, float, int, or numeric value

    Returns:
        Decimal: The value quantized to 2 decimal places (e.g., 123.45)
    """
    if value is None:
        return Decimal('0.00')
    try:
        if isinstance(value, Decimal):
            if not value.is_finite():
                return Decimal('0.00')
            return value.quantize(Decimal('0.01'))
        else:
            quantized = Decimal(str(value)).quantize(Decimal('0.01'))
            if not quantized.is_finite():
                return Decimal('0.00')
            return quantized
    except (InvalidOperation, ValueError, TypeError):
        # Handle NaN, Infinity, or unparseable values
        return Decimal('0.00')

def _current_utc_month():
    return utc_now().month

def _current_utc_year():
    return utc_now().year



# -------------------- MODELS --------------------


# -------------------- ENUMS --------------------

class AttendanceReasonCode(str, enum.Enum):
    """Reason codes for attendance session boundaries."""
    HALL_PASS = 'hall_pass'
    DONE_FOR_DAY = 'done_for_day'
    START_WORK = 'start_work'


# Legacy tap reason enum removed; attendance is expressed through attendance_sessions (DOM-PROD-001).




class TransactionStatus(str, enum.Enum):
    PENDING = 'pending'
    POSTED = 'posted'
    VOID = 'void'

class AccountType(str, enum.Enum):
    CHECKING = 'checking'
    SAVINGS = 'savings'


class LedgerMechanism(str, enum.Enum):
    SELF = 'self'
    TEACHER = 'teacher'
    SYSTEM = 'system'

class UserRole(str, enum.Enum):
    STUDENT = 'student'
    TEACHER = 'teacher'
    SYSADMIN = 'sysadmin'

# Alerting history is represented in alert_events (DOM-OPS-001)


class User(db.Model):
    """Global authentication, recovery, and session principal."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    user_role = db.Column(
        db.Enum(UserRole, values_callable=lambda x: [e.value for e in x], name='user_role_enum'),
        nullable=True,
        index=True,
    )
    username_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    username_lookup_hash = db.Column(db.String(64), unique=True, nullable=True, index=True)
    totp_secret_encrypted = db.Column(db.String(200), nullable=True)
    pin_hash = db.Column(db.Text, nullable=True)
    passphrase_hash = db.Column(db.Text, nullable=True)
    current_session_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_session_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_session_nonce = db.Column(db.String(128), nullable=True, index=True)
    # Student recovery fields
    reset_code = db.Column(db.String(8), nullable=True)
    reset_code_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reset_code_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_active_seat_id = db.Column(
        db.Integer,
        db.ForeignKey('seats.id', ondelete='SET NULL', use_alter=True, name='fk_users_last_active_seat_id_seats'),
        nullable=True,
        index=True,
    )

    # Transitional pointer until session restoration is fully seat-based.
    last_active_class_id = db.Column(
        db.String(36),
        db.ForeignKey('classes.class_id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Hall pass public verification token (256-bit, capability-based, rotatable)
    # Used for /verify/hallpass/<token> and not derived from teacher authority
    hall_pass_verify_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    @staticmethod
    def generate_verify_token() -> str:
        """Generate a new 256-bit random hall pass verification token."""
        import secrets
        return secrets.token_hex(32)

    seats = db.relationship(
        'Seat',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan',
        passive_deletes=True,
        foreign_keys='Seat.user_id',
    )
    last_active_seat = db.relationship('Seat', foreign_keys=[last_active_seat_id], post_update=True)

    @validates('totp_secret_encrypted')
    def _validate_totp_secret_encrypted(self, _key, value):
        return normalize_totp_for_storage(value) if value else None

    def get_display_username(self):
        """Return the canonical public username for UI display."""
        if getattr(self.user_role, "value", self.user_role) == UserRole.SYSADMIN.value:
            return f"sysadmin_{self.id}"
        return f"user_{self.id}"


class IdentityProfile(db.Model):
    """Seat-bound display identity with no authentication or authority semantics."""

    __tablename__ = 'identity_profiles'

    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(
        db.Integer,
        db.ForeignKey('seats.id', ondelete='CASCADE'),
        nullable=True,
        unique=True,
        index=True,
    )
    class_id = db.Column(
        db.String(36),
        db.ForeignKey('classes.class_id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    # Transitional discriminator until every profile is bound to a seat.
    profile_type = db.Column(db.String(32), nullable=False, index=True)
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    notes = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)
    # No recovery artifacts on IdentityProfile
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        db.Index('ix_identity_profiles_type_name', 'profile_type', 'last_name'),
    )

    @property
    def last_initial(self):
        """Backward-compatible accessor for display contexts needing just the initial."""
        return self.last_name[0] if self.last_name else ''

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# Provisioning and recovery token tables are no longer part of the runtime schema


class Seat(db.Model):
    """Class-local participant identity for a user."""

    __tablename__ = 'seats'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False, default='student')

    # Canonical seat-local metadata for the identity overhaul target.
    roster_fingerprint = db.Column(db.String(128), nullable=True, index=True)
    dedupe_code = db.Column(db.String(8), nullable=True)
    claim_first_name_hash = db.Column(db.String(128), nullable=True, index=True)
    claim_last_name_hash = db.Column(db.String(128), nullable=True, index=True)
    claimed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    has_received_rent_exemption = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    identity_profile = db.relationship(
        'IdentityProfile',
        backref=db.backref('seat', uselist=False),
        uselist=False,
        foreign_keys='IdentityProfile.seat_id',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    class_economy = db.relationship(
        'ClassEconomy',
        foreign_keys=[class_id],
        backref=db.backref('seats', lazy='dynamic', passive_deletes=True),
    )

    __table_args__ = (
        db.UniqueConstraint('user_id', 'class_id', name='uq_seats_user_class'),
    )

    @property
    def recent_deposits(self):
        if not hasattr(self, "transactions") or self.transactions is None:
            return []
        return (
            self.transactions.filter(Transaction.amount > 0)
            .order_by(Transaction.timestamp.desc())
            .all()
        )

    @property
    def is_rent_enabled(self):
        return not self.has_received_rent_exemption

    @property
    def block(self):
        """Compatibility view for legacy block-based admin rendering."""
        if self.class_economy is None:
            return None
        return self.class_economy.section

    @block.setter
    def block(self, value):
        if self.class_economy is not None:
            self.class_economy.section = value


# Sysadmin authority now lives on User.user_role=SYSADMIN
# Teacher invite-code support is handled outside the canonical runtime schema



class ClassEconomy(db.Model):
    """Canonical class anchor identified by a public join code and internal class_id."""
    __tablename__ = 'classes'

    class_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_public_id = db.Column(db.String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    join_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    section = db.Column(db.String(50), nullable=True)
    block = synonym("section")
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    display_name = db.Column(db.String(100), nullable=True)
    class_timezone = db.Column(db.String(64), nullable=False, default='UTC', server_default='UTC')
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    features = db.relationship('ClassFeature', backref='class_economy', cascade='all, delete-orphan', lazy='dynamic')
    teacher = db.relationship(
        'User',
        foreign_keys=[user_id],
        backref=db.backref('classes', lazy='dynamic', passive_deletes=True),
    )
    created_by_user = db.relationship('User', foreign_keys=[created_by_user_id])

    @property
    def status(self):
        return "active"

    @status.setter
    def status(self, _value):
        return None

    @validates("class_timezone")
    def validate_class_timezone(self, _key, value):
        if value is None:
            return None
        normalized = value.strip()
        if normalized not in pytz.all_timezones_set:
            raise ValueError("Class timezone must be a valid IANA timezone.")
        return normalized


@event.listens_for(ClassEconomy, "before_update")
def prevent_class_timezone_mutation(_mapper, _connection, target):
    state = sa.inspect(target)
    history = state.attrs.class_timezone.history
    if not history.has_changes():
        return

    previous_values = [value for value in history.deleted if value is not None]
    if previous_values and target.class_timezone != previous_values[0]:
        raise ValueError("Class timezone is immutable once set.")


# Derived interpretation cache is excluded from the canonical runtime schema



class PasskeyCredential(db.Model):
    """Unified passkey credential metadata owned by users."""

    __tablename__ = 'passkey_credentials'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    credential_id = db.Column(db.Text, unique=False, nullable=True, index=False)
    authenticator_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_used = db.Column(db.DateTime(timezone=True))

    user = db.relationship('User', backref=db.backref('passkey_credentials', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<PasskeyCredential {self.authenticator_name or "Unnamed"} for User {self.user_id}>'


class Transaction(db.Model):
    __tablename__ = 'ledger_transaction'
    id = db.Column(db.Integer, primary_key=True)
    # seat_id is the canonical ledger anchor.
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    target_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # CRITICAL: class_id is the canonical anchor for class isolation.
    # join_code is ingress/display metadata only and may resolve to class_id
    # at the boundary, but it is never the runtime authority.
    join_code = db.Column(db.String(20), nullable=True, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True, index=True)

    mechanism = db.Column(
        db.Enum(LedgerMechanism, values_callable=lambda x: [e.value for e in x], name='ledger_mechanism_enum'),
        nullable=False,
        default=LedgerMechanism.SELF,
        server_default=LedgerMechanism.SELF.value,
    )

    # CRITICAL: Use Numeric for exact decimal representation to avoid floating-point errors
    # Float causes bugs: -0.00 overdraft fees, unpayable rent balances
    amount = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    # All times stored as UTC (see header note)
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now)
    account_type = db.Column(db.String(20), default='checking')

    # Ledger Fields
    status = db.Column(
        db.Enum(TransactionStatus),
        default=TransactionStatus.POSTED,
        nullable=False,
        server_default=TransactionStatus.POSTED.name,
    )
    amount_cents = db.Column(db.Integer, nullable=False)  # Signed integer (e.g. 100 = $1.00)
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    voided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    effective_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    description = db.Column(db.String(255))
    correlation_id = db.Column(db.String(100), nullable=False, index=True)
    feat_code = db.Column(db.String(100), nullable=True, index=True)
    idempotency_key = db.Column(db.String(100), nullable=True, index=True)
    is_void = db.Column(db.Boolean, default=False)
    # References for compensating/reversal ledger entries.
    # Stored as IDs for backend portability.
    original_transaction_id = db.Column(db.Integer, nullable=True, index=True)
    reversal_transaction_id = db.Column(db.Integer, nullable=True, index=True)
    policy_id = db.Column(db.Integer, nullable=True, index=True)
    type = db.Column(db.String(50))  # optional field to describe the transaction type
    # All times stored as UTC
    date_funds_available = db.Column(db.DateTime(timezone=True), default=utc_now)

    # Audit lineage — proof that this row entered through a lawful CTH execution path.
    # lineage_token is a fast provenance pointer (copy of AuditEvent.hmac_signature).
    # Canonical proof requires: payload digest match + valid chain continuity via verifier.
    # NULL means the row predates lineage rollout (UNVERIFIED state, not INVALID).
    lineage_event_id = db.Column(db.Integer, db.ForeignKey('audit_events.id'), nullable=True, index=True)
    lineage_token    = db.Column(db.String(64), nullable=True)
    lineage_version  = db.Column(db.Integer, nullable=True, default=1)

    # Relationship to track which actor and target seat the transaction binds to
    teacher = db.relationship('User', backref=db.backref('transactions', lazy='dynamic'))
    seat = db.relationship('Seat', backref=db.backref('transactions', lazy='dynamic'), foreign_keys=[seat_id])
    target_seat = db.relationship('Seat', foreign_keys=[target_seat_id], post_update=True)
    actor_seat = db.relationship('Seat', foreign_keys=[actor_seat_id], post_update=True)

    __table_args__ = (
        db.Index('ix_transaction_seat_ledger', 'join_code', 'seat_id', 'status', 'account_type'),
        db.Index('ix_transaction_class_scope', 'class_id', 'target_seat_id', 'actor_seat_id', 'account_type'),
        db.Index(
            'uq_transaction_idempotency_scope',
            'class_id',
            'target_seat_id',
            'feat_code',
            'idempotency_key',
            'type',
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'")
        ),
    )


@sa.event.listens_for(Transaction, "before_insert")
@sa.event.listens_for(Transaction, "before_update")
def _enforce_transaction_integrity(_mapper, _connection, target):
    """
    Enforce FEAT Constitutional Invariants on every ledger write.
    1. Synchronize amount_cents.
    2. Auto-populate canonical target/actor seat fields and class_id if possible.
    3. Assert correlation_id in Tier 1 paths.
    4. Auto-populate feat_code from active context.
    """
    from app.feats.base import is_feat_active, get_correlation_id, get_active_feat_name, FEAT_REGISTRY, validate_id_format

    # 1. Sync amount_cents
    if target.amount is not None:
        target.amount_cents = int(_quantize_currency(target.amount) * 100)

    # 2. FEAT Context Enforcement
    if is_feat_active():
        feat_name = get_active_feat_name()
        target.feat_code = feat_name

        # Auto-propagate correlation_id if not explicitly set
        if not target.correlation_id:
            target.correlation_id = get_correlation_id()

        # Session Isolation: Prevent mixed correlations in one flush.
        # This only fires for INSERTs — for UPDATEs, target.correlation_id is
        # historical lineage data from the FEAT that ORIGINATED the row and is
        # legitimately different from the active FEAT's correlation_id. The
        # active FEAT's identity on UPDATE is captured by feat_code above; the
        # row's correlation_id is its provenance, not the current operation's
        # identity. (Prior to this split, the check fired on UPDATE as well,
        # which made cross-FEAT Transaction mutations — refunds, voids,
        # reversal_transaction_id linkage — impossible under FEAT enforcement.
        # The contradiction was hidden by FEATBypass wrapping every test.)
        _target_state = sa.inspect(target)
        _is_new_insert = _target_state.transient or _target_state.pending
        session = db.session.object_session(target)
        if session and _is_new_insert:
            active_corr = session.info.get("active_correlation_id")
            if active_corr and target.correlation_id != active_corr:
                 raise ValueError(f"FATAL: Mixed correlation in flush. Context={active_corr}, Object={target.correlation_id}")
            session.info["active_correlation_id"] = target.correlation_id
    else:
        from app.feats.base import FEATContextError
        raise FEATContextError("MANDATORY FEAT CONSTITUTIONAL VIOLATION: Ledger mutation outside of FEAT context.")

    if not target.class_id and target.target_seat_id:
        seat_class_id = _connection.execute(
            sa.text("SELECT class_id FROM seats WHERE id = :seat_id LIMIT 1"),
            {"seat_id": target.target_seat_id},
        ).scalar()
        if seat_class_id:
            target.class_id = str(seat_class_id)

    if target.actor_seat_id and target.class_id:
        actor_class_id = _connection.execute(
            sa.text("SELECT class_id FROM seats WHERE id = :seat_id LIMIT 1"),
            {"seat_id": target.actor_seat_id},
            ).scalar()
        if actor_class_id and str(actor_class_id) != str(target.class_id):
            raise ValueError("FATAL: Actor seat is outside the transaction class scope.")

    # 5. Global Format Validation
    state = sa.inspect(target)
    is_new = state.transient or state.pending

    is_bypass = False
    feat_name = "UNTRACKED"
    if is_feat_active():
        feat_name = get_active_feat_name()
        is_bypass = feat_name == "FEAT-BYPASS-LEGACY" or (
            bool(getattr(target, "correlation_id", None))
            and str(target.correlation_id).startswith("bypass_test_")
        )

    if is_bypass:
        if not target.correlation_id or not target.correlation_id.startswith("bypass_test_"):
            raise ValueError(f"FATAL: Bypass mode active but correlation_id does not start with 'bypass_test_': {target.correlation_id}")
    else:
        # 1. Mandatory Identity Alignment (V2 Law)
        # Tier-1 ledger FEATs require explicit class anchors; low-blast
        # admin/test flows can continue during routine validation.
        meta = FEAT_REGISTRY.get(feat_name, {})
        is_tier_1 = meta.get("blast_radius") == "HIGH" or (feat_name and feat_name.startswith("FEAT-LED"))
        if is_tier_1 and not target.class_id:
             raise ValueError(f"FATAL: Ledger mutation missing mandatory class_id in {feat_name}. Clean break V2 requires explicit class anchoring.")
        if not target.correlation_id or target.correlation_id == "NO-CORRELATION":
            raise ValueError(f"FATAL: Ledger mutation missing correlation_id in {feat_name}.")

        if is_new:
            if not validate_id_format(target.correlation_id, "corr_"):
                raise ValueError(f"FATAL: Invalid correlation_id format for new insert in {feat_name}: {target.correlation_id}. Must start with 'corr_' or 'bypass_test_'")
        else:
            if not (validate_id_format(target.correlation_id, "corr_") or 
                    target.correlation_id.startswith("bypass_test_")):
                raise ValueError(f"FATAL: Invalid correlation_id format for update in {feat_name}: {target.correlation_id}")

    # 4. Validation for Tier 1 / Ledger paths
    meta = FEAT_REGISTRY.get(feat_name, {})
    is_tier_1 = meta.get("blast_radius") == "HIGH" or (feat_name and feat_name.startswith("FEAT-LED"))
    bypass_correlation = bool(getattr(target, "correlation_id", None)) and str(target.correlation_id).startswith("bypass_test_")

    if is_tier_1 and not bypass_correlation:
         if target.correlation_id != get_correlation_id():
              raise ValueError(f"FATAL: Correlation mismatch in {feat_name}. Record={target.correlation_id}, Context={get_correlation_id()}")

         # 2. Assert Identity Anchors (seat_id + class_id are the clean-break authority)
         if not target.class_id:
              raise ValueError(f"FATAL: Ledger mutation in {feat_name} missing class_id. Must be provided by service.")

         if not target.seat_id:
              raise ValueError(f"FATAL: Ledger mutation in {feat_name} missing seat_id. Must be provided by service.")

    # 4. Identity synchronization (pure assignment only)
    # seat_id is the runtime anchor; student_id is only used for seat lookup.

def _resolve_seat_id(connection, student_id, *, class_id=None):
    """Lookup seat ID for a student in a class universe."""
    if not student_id or not class_id:
        return None

    seat_id = connection.execute(
        sa.text("SELECT id FROM seats WHERE user_id = :student_id AND class_id = :class_id LIMIT 1"),
        {"student_id": student_id, "class_id": class_id},
    ).scalar()
    return int(seat_id) if seat_id else None


class LedgerBalanceSnapshot(db.Model):
    """
    Authorized snapshot of posted balances (ledger_balance_snapshot — DOM-LED-001).
    Available Balance = Posted Balance (Snapshot) + Sum(Pending Transactions from Ledger)
    """
    __tablename__ = 'ledger_balance_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    join_code = db.Column(db.String(20), nullable=True)

    # Balances stored in CENTS to avoid floating point issues
    posted_checking_balance_cents = db.Column(db.Integer, default=0, nullable=False)
    posted_savings_balance_cents = db.Column(db.Integer, default=0, nullable=False)

    last_settlement_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.UniqueConstraint('class_id', 'seat_id', name='uq_balance_cache_seat_universe'),
    )


class AttendanceSession(db.Model):
    """Canonical attendance session facts per seat/class."""
    __tablename__ = 'attendance_sessions'

    id = db.Column(db.Integer, primary_key=True)
    target_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=False, index=True)
    actor_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='SET NULL'), nullable=False, index=True)
    mechanism = db.Column(db.String(20), nullable=False, default="self")
    status = db.Column(db.String(20), nullable=False, default="active")
    reason_code = db.Column(db.String(32), nullable=False, index=True)
    # Hall-pass rows carry the consumed entitlement instance id, not the log row id.
    hall_pass_id = db.Column(db.String(100), nullable=True, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    target_seat = db.relationship("Seat", foreign_keys=[target_seat_id], backref=db.backref("attendance_sessions", passive_deletes=True))
    target_user = db.relationship("User", foreign_keys=[target_user_id], post_update=True)
    actor_seat = db.relationship("Seat", foreign_keys=[actor_seat_id], post_update=True)

    __table_args__ = (
        db.Index('ix_attendance_sessions_target_user_id_active', 'target_user_id', unique=True, postgresql_where=sa.text("status = 'active' AND target_user_id IS NOT NULL")),
    )


# Legacy tap table removed; canonical replacement: attendance_sessions (DOM-PROD-001).


# ---- Hall Pass Log Model ----
class HallPassLog(db.Model):
    __tablename__ = 'hall_pass_logs'
    id = db.Column(db.Integer, primary_key=True)
    requested_by_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='SET NULL'), nullable=False, index=True)
    approved_by_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='SET NULL'), nullable=False, index=True)
    correlation_id = db.Column(db.String(100), nullable=False, index=True)
    # FK-style reference to EntitlementEvent.entitlement_id for the consumed pass.
    hall_pass_id = db.Column(db.String(100), nullable=False, unique=False, index=True)
    destination = db.Column(db.String(255), nullable=True)

    # CRITICAL: class_id is the source of truth for class isolation
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    requested_by_seat = db.relationship('Seat', foreign_keys=[requested_by_seat_id], post_update=True)
    approved_by_seat = db.relationship('Seat', foreign_keys=[approved_by_seat_id], post_update=True)


class PayrollEvent(db.Model):
    __tablename__ = "payroll_event"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    target_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='SET NULL'), nullable=False, index=True)
    correlation_id = db.Column(db.String(100), nullable=False, index=True)
    idempotency_key = db.Column(db.String(255), nullable=False, index=True)
    policy_version_id = db.Column(db.Integer, db.ForeignKey('policy_versions.id', ondelete='RESTRICT'), nullable=False, index=True)
    mechanism = db.Column(db.String(20), nullable=False, default="TEACHER")
    payroll_event_type = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    summary_json = db.Column(db.JSON, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('class_id', 'target_seat_id', 'correlation_id', 'idempotency_key', 'payroll_event_type', name='uq_payroll_event_replay_guard'),
    )


class HallPassSettings(db.Model):
    __tablename__ = 'hall_pass_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Queue system toggle
    queue_enabled = db.Column(db.Boolean, default=True, nullable=False)

    # Queue limit (when queue + currently out >= this number, restrict certain passes)
    queue_limit = db.Column(db.Integer, default=10, nullable=False)

    # Pass type configurations stored as JSON.
    pass_types = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @staticmethod
    def get_default_pass_types():
        """Return default pass types when teacher hasn't configured any."""
        return [
            {"name": "Bathroom", "queue_limit": None, "simultaneous_limit": None, "enabled": True},
            {"name": "Water Fountain", "queue_limit": None, "simultaneous_limit": None, "enabled": True},
            {"name": "Office", "queue_limit": None, "simultaneous_limit": None, "enabled": True},
            {"name": "Nurse", "queue_limit": None, "simultaneous_limit": None, "enabled": True},
            {"name": "Counselor", "queue_limit": None, "simultaneous_limit": None, "enabled": True}
        ]

    def get_pass_types(self):
        """Get pass types, defaulting to the built-in set when unset."""
        if not self.pass_types:
            return self.get_default_pass_types()

        for pt in self.pass_types:
            pt.setdefault('enabled', True)
        return self.pass_types


# Persisted compute-result caches are explicitly prohibited by DOM-CORE-002


# -------------------- STORE MODELS --------------------

class StoreItem(db.Model):
    __tablename__ = 'store_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    tier = db.Column(db.String(20), nullable=True) # basic, standard, premium, luxury (teacher-only organizational label)
    item_type = db.Column(db.String(20), nullable=False, default='delayed') # immediate, delayed, collective
    inventory = db.Column(db.Integer, nullable=True) # null for unlimited
    limit_per_student = db.Column(db.Integer, nullable=True) # null for no limit
    auto_delist_date = db.Column(db.DateTime(timezone=True), nullable=True)
    auto_expiry_days = db.Column(db.Integer, nullable=True) # days student has to use the item
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_long_term_goal = db.Column(db.Boolean, default=False, nullable=False) # if true, exclude from CWI balance checks
    bypass_cwi_warnings = db.Column(db.Boolean, default=False, nullable=False)

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
    collective_goal_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Optional deadline; unmet goals are auto-refunded on expiration
    collective_goal_instance_code = db.Column(db.String(36), nullable=True, index=True)

    # Redemption prompt (for delayed use items)
    redemption_prompt = db.Column(db.Text, nullable=True)  # Optional prompt shown to students when redeeming delayed items

    # Rent Linked
    is_rent_linked = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    teacher = db.relationship('User', backref=db.backref('store_items', lazy='dynamic'))
    # Seat-level visibility is the canonical replacement for legacy block visibility.
    visible_seats = db.relationship(
        'StoreItemVisibility',
        back_populates='store_item',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    @property
    def blocks_list(self):
        """Return block labels derived from canonical seat-level visibility."""
        seat_ids = [row.seat_id for row in self.visible_seats.all()]
        if not seat_ids:
            return []
        rows = (
            db.session.query(ClassEconomy.section)
            .join(Seat, Seat.class_id == ClassEconomy.class_id)
            .filter(Seat.id.in_(seat_ids), ClassEconomy.section.isnot(None))
            .distinct()
            .all()
        )
        return [section for (section,) in rows if section]

    def set_blocks(self, block_list):
        """Set the visibility blocks using canonical seat-level visibility rows."""
        StoreItemVisibility.query.filter_by(store_item_id=self.id).delete()
        if not block_list:
            return
        normalized_blocks = {block.strip().upper() for block in block_list if block and block.strip()}
        if not normalized_blocks:
            return
        seat_ids = [
            seat_id
            for (seat_id,) in (
                db.session.query(Seat.id)
                .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
                .filter(
                    ClassEconomy.section.isnot(None),
                    ClassEconomy.section.in_(normalized_blocks),
                    ClassEconomy.class_id == self.class_id,
                )
                .distinct()
                .all()
            )
        ]
        if seat_ids:
            db.session.add_all([
                StoreItemVisibility(store_item_id=self.id, seat_id=seat_id)
                for seat_id in seat_ids
            ])


@sa.event.listens_for(StoreItem, "before_insert")
@sa.event.listens_for(StoreItem, "before_update")
def _sync_store_item_scope(_mapper, connection, target):
    """Synchronize store_items class scope during the transition."""
    class_id = getattr(target, "class_id", None)
    if not class_id:
        raise ValueError("store_items require canonical class_id")


# StoreItemBlock removed — store_item_blocks unauthorized; canonical replacement: store_item_visibility (DOM-STORE-001)


# StudentItem removed — student_items unauthorized; canonical replacement: store_purchases + redemption_events (DOM-STORE-001)
# RedemptionAuditAction / RedemptionAuditSource / RedemptionAuditLog removed — redemption_audit_logs unauthorized;
#   canonical replacement: redemption_events (DOM-STORE-001) + audit_events (DOM-OPS-001)


# -------------------- CANONICAL STORE MODELS (v2) --------------------


class StoreItemVisibility(db.Model):
    __tablename__ = 'store_item_visibility'
    id = db.Column(db.Integer, primary_key=True)
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id', ondelete='CASCADE'), nullable=False, index=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('store_item_id', 'seat_id', name='uq_store_item_visibility_item_seat'),
    )

    store_item = db.relationship('StoreItem', back_populates='visible_seats')
    seat = db.relationship('Seat', backref=db.backref('store_visibility_grants', lazy='dynamic'))


class StorePurchaseStatus(enum.Enum):
    PURCHASED = 'purchased'
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    EXPIRED = 'expired'
    REDEEMED = 'redeemed'
    VOIDED = 'voided'


class StorePurchase(db.Model):
    __tablename__ = 'store_purchases'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_purchase = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    total_price = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='purchased')
    idempotency_key = db.Column(db.String(100), nullable=True, unique=True, index=True)
    ledger_tx_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id'), nullable=True, index=True)
    purchased_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    expiry_date = db.Column(db.DateTime(timezone=True), nullable=True)
    is_from_bundle = db.Column(db.Boolean, default=False, nullable=False)
    bundle_remaining = db.Column(db.Integer, nullable=True)
    uses_remaining = db.Column(db.Integer, nullable=True)
    collective_goal_instance_code = db.Column(db.String(36), nullable=True, index=True)

    seat = db.relationship('Seat', backref=db.backref('store_purchases', lazy='dynamic'))
    store_item = db.relationship('StoreItem', backref=db.backref('purchases', lazy='dynamic'))
    ledger_tx = db.relationship('Transaction', backref=db.backref('store_purchase', uselist=False))

    __table_args__ = (
        db.Index('ix_store_purchases_seat_class', 'seat_id', 'class_id'),
    )


class RedemptionEventAction(enum.Enum):
    REQUEST = 'request'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class RedemptionEventSource(enum.Enum):
    LIVE = 'live'


class RedemptionEvent(db.Model):
    __tablename__ = 'redemption_events'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    purchase_id = db.Column(db.Integer, db.ForeignKey('store_purchases.id', ondelete='CASCADE'), nullable=False, index=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='SET NULL'), nullable=True, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True, index=True)
    action = db.Column(
        db.Enum(
            RedemptionEventAction,
            values_callable=lambda x: [e.value for e in x],
            name='redemption_event_action_enum',
        ),
        nullable=False,
        index=True,
    )
    source = db.Column(
        db.Enum(
            RedemptionEventSource,
            values_callable=lambda x: [e.value for e in x],
            name='redemption_event_source_enum',
        ),
        nullable=False,
        default=RedemptionEventSource.LIVE,
    )
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    seat_display_name = db.Column(db.String(120), nullable=False)
    class_display_label = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    purchase = db.relationship('StorePurchase', backref=db.backref('redemption_events', lazy='dynamic'))
    initiated_by = db.relationship('User', backref=db.backref('initiated_redemption_events', lazy='dynamic'))

    __table_args__ = (
        db.Index('ix_redemption_events_initiated_by_timestamp', 'initiated_by_user_id', 'timestamp'),
    )


# -------------------- RENT SETTINGS MODEL --------------------
class RentSettings(db.Model):
    __tablename__ = 'rent_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Rent amount and frequency
    rent_amount = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('50.00'))
    frequency_type = db.Column(db.String(20), default='monthly')  # 'daily', 'weekly', 'monthly', 'custom'
    custom_frequency_value = db.Column(db.Integer, nullable=True)  # For custom: x per time unit
    custom_frequency_unit = db.Column(db.String(20), nullable=True)  # 'days', 'weeks', 'months'

    # Due date settings
    first_rent_due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    due_day_of_month = db.Column(db.Integer, default=1)  # For monthly frequency.

    # Grace period and late penalties
    grace_period_days = db.Column(db.Integer, default=3)
    late_penalty_amount = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('10.00'))
    late_penalty_type = db.Column(db.String(20), default='once')  # 'once' or 'recurring'
    late_penalty_frequency_days = db.Column(db.Integer, nullable=True)  # For recurring type

    # Bill preview and payment options
    bill_preview_enabled = db.Column(db.Boolean, default=False)
    bill_preview_days = db.Column(db.Integer, default=7)
    allow_incremental_payment = db.Column(db.Boolean, default=False)
    prevent_purchase_when_late = db.Column(db.Boolean, default=False)
    bypass_cwi_warnings = db.Column(db.Boolean, default=False, nullable=False)

    # Metadata
    rent_configured_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=True, index=True)
    rent_effective_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    cycle_length_days = db.Column(db.Integer, nullable=False, default=30)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Version tracking is modeled in canonical policy tables.

    # Keep old field names for accessors.
    @property
    def late_fee(self):
        return self.late_penalty_amount

    _FROZEN_POLICY_FIELDS = (
        'rent_amount', 'frequency_type', 'custom_frequency_value', 'custom_frequency_unit',
        'due_day_of_month', 'grace_period_days', 'late_penalty_amount', 'late_penalty_type',
        'late_penalty_frequency_days', 'bill_preview_enabled', 'bill_preview_days',
        'allow_incremental_payment', 'prevent_purchase_when_late', 'cycle_length_days',
    )

@event.listens_for(RentSettings, "before_insert")
@event.listens_for(RentSettings, "before_update")
def _sync_rent_settings_scope(mapper, connection, target):
    """Canonical rent settings scope must already be class_id anchored."""
    if getattr(target, "class_id", None) is None:
        raise ValueError("rent_settings require canonical class_id")


# Rent policy state is now canonical


# Rent payment state is expressed through obligation satisfaction and ledger references


# Rent waiver state is expressed through obligation satisfaction

# Rent store state is now canonical




# Legacy insurance system entities are not part of the canonical runtime schema



# ---- Canonical Obligations Domain (DOM-OBL-001) ----

class ObligationAssessment(db.Model):
    """Authoritative record of a seat becoming liable for a policy-defined charge."""
    __tablename__ = 'assessment_events'

    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    join_code = db.Column(db.String(20), nullable=True, index=True)
    period = db.Column(db.String(10), nullable=True, index=True)

    obligation_type = db.Column(db.String(30), nullable=False, index=True)  # RENT, INSURANCE_PREMIUM

    # Policy snapshot at assessment time — INV-OBL-009
    amount_snap = db.Column(db.Numeric(precision=12, scale=2), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    assessed_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    policy_version_id = db.Column(
        db.Integer,
        db.ForeignKey('policy_versions.id'),
        nullable=True,
        index=True,
    )

    # Rent-cycle fields — preserved from prepay coverage-window model (INV-ARC-015)
    period_key = db.Column(db.String(20), nullable=True)
    coverage_start_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    coverage_end_time = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    cycle_idempotency_key = db.Column(db.String(160), nullable=True, index=True)
    period_month = db.Column(db.Integer, nullable=True)
    period_year = db.Column(db.Integer, nullable=True)
    coverage_month = db.Column(db.Integer, nullable=True)
    coverage_year = db.Column(db.Integer, nullable=True)

    seat = db.relationship('Seat', backref=db.backref('obligation_assessments', passive_deletes=True))
    satisfaction = db.relationship('ObligationSatisfaction', uselist=False, backref='assessment')
    reversal = db.relationship('ObligationReversal', uselist=False, backref='assessment')
    entitlement_events = db.relationship('EntitlementEvent', backref='assessment')
    policy_version = db.relationship('PolicyVersion', backref=db.backref('assessments', lazy='dynamic'))
    __table_args__ = (
        db.UniqueConstraint('seat_id', 'class_id', 'cycle_idempotency_key', name='uq_assessment_events_idempotency'),
        db.Index('ix_assessment_events_seat_class', 'seat_id', 'class_id'),
    )


class ObligationLifecycle(db.Model):
    """Current derived lifecycle state for one canonical assessment event."""
    __tablename__ = 'obligation_lifecycle'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment_events.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    assessment = db.relationship('ObligationAssessment', backref=db.backref('lifecycle', uselist=False))


class ObligationSatisfaction(db.Model):
    """Immutable record of how a valid debt was resolved — INV-OBL-004."""
    __tablename__ = 'obligation_satisfaction'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment_events.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    method = db.Column(db.String(20), nullable=False)  # PAYMENT, WAIVER
    amount_paid = db.Column(db.Numeric(precision=12, scale=2), nullable=True)
    was_late = db.Column(db.Boolean, default=False, nullable=False)
    late_fee_charged = db.Column(db.Numeric(precision=12, scale=2), nullable=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id', ondelete='SET NULL'), nullable=True, index=True)
    satisfied_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)


class ObligationReversal(db.Model):
    """Immutable record of an assessment correction or nullification — INV-OBL-005."""
    __tablename__ = 'obligation_reversal'

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment_events.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    reason = db.Column(db.Text, nullable=True)
    reversed_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    reversed_by_seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)


# Legacy insurance enrollment state is not part of the canonical runtime schema


class EntitlementEvent(db.Model):
    """Append-only stream of obligation-linked perk grants, consumptions, and revocations — INV-OBL-002/003."""
    __tablename__ = 'entitlement_events'

    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment_events.id', ondelete='SET NULL'), nullable=True, index=True)
    trigger_id = db.Column(db.String(200), nullable=True, index=True)  # Idempotency key (INV-OBL-003)
    correlation_id = db.Column(db.String(100), nullable=True, index=True)
    entitlement_id = db.Column(db.String(100), nullable=True, index=True)
    quantity_delta = db.Column(db.Integer, nullable=False)  # +N grant, -N consumption/revocation
    event_type = db.Column(db.String(20), nullable=False)  # GRANT, CONSUMPTION, REVOCATION
    occurred_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    seat = db.relationship('Seat', backref=db.backref('entitlement_events', passive_deletes=True))

    __table_args__ = (
        db.Index('ix_entitlement_events_seat_class', 'seat_id', 'class_id'),
    )


# ---- Error Log Model ----
# Error logging state is represented in the canonical operations tables


class ActorRequestTrace(db.Model):
    """Short-lived request trace rows for ticket correlation."""

    __tablename__ = 'actor_request_trace'

    id = db.Column(db.Integer, primary_key=True)
    actor_type = db.Column(db.String(20), nullable=False, index=True)
    actor_public_id = db.Column(db.String(64), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='SET NULL'), nullable=True, index=True)
    request_id = db.Column(db.String(128), nullable=False, index=True)
    method = db.Column(db.String(10), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        db.Index('ix_actor_trace_actor_public_created', 'actor_type', 'actor_public_id', 'created_at'),
    )


# Error events are represented in operational_events


# ---- User Report Model (Bug Reports, Suggestions, Comments) ----
# Legacy support report rows removed; support issues are now canonical


# ---- Issue Resolution System Models ----

class IssueCategory(db.Model):
    """
    Predefined categories for student issue reports.
    Categories guide students to provide relevant context for their issue.
    """
    __tablename__ = 'issue_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    category_type = db.Column(db.String(50), nullable=False)  # 'transaction', 'general'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)

    # Relationships
    issues = db.relationship('Issue', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<IssueCategory {self.name} ({self.category_type})>'


class Issue(db.Model):
    """
    Core issue tracking model for the Issue Resolution & Escalation system.

    This system provides a safe, auditable, non-communicative mechanism for handling
    errors, disputes, and system issues. Students submit issues which are reviewed
    by teachers and potentially escalated to sysadmins.

    Key principles:
    - No direct student-to-sysadmin communication
    - Teachers are first and primary decision-makers
    - All issues tied to concrete system records when possible
    - Clear lifecycle, ownership, and audit trail
    - Non-identifying data for sysadmin review
    """
    __tablename__ = 'issues'

    id = db.Column(db.Integer, primary_key=True)

    # Public actor identifier (submitter) — resolves to seats.public_id for internal lookups
    actor_public_id = db.Column(db.String(64), nullable=False, index=True)

    # Public reviewer identifier (teacher) — resolves to seats.public_id in the same class
    reviewer_public_id = db.Column(db.String(64), nullable=True, index=True)

    # External-facing class context — resolves to classes.class_public_id
    class_public_id = db.Column(db.String(36), nullable=True, index=True)

    # Issue categorization
    category_id = db.Column(db.Integer, db.ForeignKey('issue_categories.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)  # 'transaction', 'general'

    # Student submission (immutable after submission)
    student_explanation = db.Column(db.Text, nullable=False)
    student_expected_outcome = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Context attachment (transaction/record-specific issues)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id'), nullable=True)
    related_record_type = db.Column(db.String(50), nullable=True)  # 'transaction', 'attendance_session', etc.
    related_record_id = db.Column(db.Integer, nullable=True)  # Generic ID for other record types

    # System context snapshot (automatic, immutable)
    context_snapshot = db.Column(db.JSON, nullable=True)  # Ledger state, amounts, timestamps, etc.
    page_url = db.Column(db.String(500), nullable=True)
    system_metadata = db.Column(db.JSON, nullable=True)  # Recent events, browser info, etc.

    # Status tracking
    status = db.Column(db.String(50), default='OPEN', nullable=False, index=True)
    # Canonical statuses follow FEAT-TICK-001; older rows may still use earlier values.

    # Review and resolution
    teacher_reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    teacher_notes = db.Column(db.Text, nullable=True)  # Separate from student content
    teacher_resolution = db.Column(db.String(100), nullable=True)  # Type of resolution applied
    teacher_resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Escalation to sysadmin
    escalated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    escalation_reason = db.Column(db.String(200), nullable=True)
    teacher_diagnostic_note = db.Column(db.Text, nullable=True)  # Diagnostic note for sysadmin
    share_class_name_with_sysadmin = db.Column(db.Boolean, default=False, nullable=False)  # Consent for class disclosure
    eligible_for_reward = db.Column(db.Boolean, default=False, nullable=False)  # Marks if student may receive reward for a legitimate bug

    # Sysadmin review and resolution
    sysadmin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    sysadmin_reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    sysadmin_notes = db.Column(db.Text, nullable=True)  # Separate from student content, visible to teacher only
    sysadmin_resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Closure
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by_type = db.Column(db.String(20), nullable=True)  # 'reviewer', 'sysadmin', 'system'

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    sysadmin = db.relationship('User', foreign_keys=[sysadmin_id], backref=db.backref('reviewed_issues', lazy='dynamic'))
    related_transaction = db.relationship('Transaction', backref='related_issues')
    status_history = db.relationship('IssueStatusHistory', backref='issue', lazy='dynamic', cascade='all, delete-orphan', order_by='IssueStatusHistory.changed_at.desc()')
    resolution_actions = db.relationship('IssueResolutionAction', backref='issue', lazy='dynamic', cascade='all, delete-orphan', order_by='IssueResolutionAction.created_at.desc()')
    correlation_pack = db.relationship(
        'TicketCorrelationPack',
        backref=db.backref('issue', uselist=False),
        uselist=False,
        cascade='all, delete-orphan',
    )

    # Indexes
    __table_args__ = (
        db.Index('ix_issues_actor_status', 'actor_public_id', 'status'),
        db.Index('ix_issues_class_status', 'class_public_id', 'status'),
    )

    # Canonical lifecycle statuses (SPEC-TICK-001).
    STATUS_OPEN = 'OPEN'
    STATUS_TEACHER_REVIEW = 'TEACHER_REVIEW'
    STATUS_ESCALATED_TO_DEV = 'ESCALATED_TO_DEV'
    STATUS_DEV_RESOLVED = 'DEV_RESOLVED'
    STATUS_TEACHER_FINAL_REVIEW = 'TEACHER_FINAL_REVIEW'
    STATUS_CLOSED = 'CLOSED'

    # Prior status values retained for reads.
    LEGACY_TO_CANONICAL_STATUS = {
        'submitted': STATUS_OPEN,
        'teacher_review': STATUS_TEACHER_REVIEW,
        'teacher_resolved': STATUS_TEACHER_FINAL_REVIEW,
        'elevated': STATUS_ESCALATED_TO_DEV,
        'developer_review': STATUS_ESCALATED_TO_DEV,
        'developer_resolved': STATUS_DEV_RESOLVED,
    }

    def get_student_visible_status(self):
        """Return simplified status badge for student view."""
        canonical_status = self.LEGACY_TO_CANONICAL_STATUS.get(self.status, self.status)
        status_map = {
            self.STATUS_OPEN: 'Submitted',
            self.STATUS_TEACHER_REVIEW: 'Teacher Review',
            self.STATUS_ESCALATED_TO_DEV: 'Escalated to Developer',
            self.STATUS_DEV_RESOLVED: 'Developer Fix Applied - Teacher Review Required',
            self.STATUS_TEACHER_FINAL_REVIEW: 'Teacher Final Review',
            self.STATUS_CLOSED: 'Closed',
        }
        return status_map.get(canonical_status, 'Unknown')

    def is_locked(self):
        """Check if issue is locked from further student edits (after escalation)."""
        canonical_status = self.LEGACY_TO_CANONICAL_STATUS.get(self.status, self.status)
        return canonical_status in [self.STATUS_ESCALATED_TO_DEV, self.STATUS_DEV_RESOLVED, self.STATUS_CLOSED]

    def __repr__(self):
        return f'<Issue #{self.id} ({self.status}) - actor={self.actor_public_id}>'


class TicketCorrelationPack(db.Model):
    """Immutable correlation snapshot attached to an issue at submission time."""

    __tablename__ = 'ticket_correlation_pack'

    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id', ondelete='CASCADE'), primary_key=True)
    correlation_version = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    actor_type = db.Column(db.String(20), nullable=False)
    actor_public_id = db.Column(db.String(64), nullable=False)
    class_public_id = db.Column(db.String(36), nullable=True)
    request_trace_json = db.Column(db.JSON, nullable=False, default=list)
    error_refs_json = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        db.Index('ix_ticket_correlation_actor_public', 'actor_type', 'actor_public_id'),
    )


class IssueStatusHistory(db.Model):
    """
    Tracks all status changes for an issue.
    Provides complete audit trail for issue lifecycle.
    """
    __tablename__ = 'issue_status_history'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False, index=True)
    class_public_id = db.Column(db.String(36), nullable=True, index=True)

    previous_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=False)
    changed_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    changed_by_type = db.Column(db.String(20), nullable=False)  # 'student', 'teacher', 'sysadmin', 'system'
    changed_by_public_id = db.Column(db.String(64), nullable=True)  # actor_public_id of who made the change
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<IssueStatusHistory Issue#{self.issue_id}: {self.previous_status} → {self.new_status}>'


class IssueResolutionAction(db.Model):
    """
    Tracks resolution actions taken on an issue.
    Records what teachers did to resolve transaction/record disputes.
    """
    __tablename__ = 'issue_resolution_actions'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False, index=True)
    class_public_id = db.Column(db.String(36), nullable=True, index=True)

    action_type = db.Column(db.String(100), nullable=False)
    # Action types: 'reverse_transaction', 'correct_amount', 'correct_time', 'waive_fee', 'deny_issue', 'manual_adjustment', etc.

    action_description = db.Column(db.Text, nullable=True)
    performed_by_type = db.Column(db.String(20), nullable=False)  # 'teacher', 'sysadmin'
    performed_by_public_id = db.Column(db.String(64), nullable=True)  # actor_public_id of performer

    # Related changes (for audit trail)
    related_transaction_id = db.Column(db.Integer, db.ForeignKey('ledger_transaction.id'), nullable=True)
    amount_changed = db.Column(db.Float, nullable=True)
    before_value = db.Column(db.Text, nullable=True)
    after_value = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    related_transaction = db.relationship('Transaction')

    def __repr__(self):
        return f'<IssueResolutionAction Issue#{self.issue_id}: {self.action_type}>'


# Teacher identity lives in User (user_role=TEACHER)


# ---- Account Recovery Models ----
class RecoveryRequest(db.Model):
    """Teacher account recovery request - requires student verification"""
    __tablename__ = 'recovery_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Status tracking
    status = db.Column(
        db.Enum('pending', 'verified', 'expired', 'cancelled', name='recovery_request_status_enum'),
        nullable=False,
        default='pending'
    )  # pending, verified, expired, cancelled
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)  # Auto-expire after X days
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Partial progress - allows teacher to save progress and resume later
    partial_codes = db.Column(db.JSON, nullable=True)  # Array of entered codes (not yet validated)
    resume_pin_hash = db.Column(db.String(64), nullable=True)  # Hashed PIN to resume progress
    resume_new_username = db.Column(db.String(100), nullable=True)  # Temporary storage for new username

    # Relationships
    user = db.relationship('User', backref=db.backref('recovery_requests', lazy='dynamic'))
    verification_codes = db.relationship('StudentRecoveryCode', backref='recovery_request', lazy='dynamic', cascade='all, delete-orphan')


class StudentRecoveryCode(db.Model):
    """Student verification code for teacher account recovery"""
    __tablename__ = 'student_recovery_codes'

    id = db.Column(db.Integer, primary_key=True)
    recovery_request_id = db.Column(db.Integer, db.ForeignKey('recovery_requests.id'), nullable=False, index=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False, index=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)

    code_hash = db.Column(db.String(64), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    notified_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    dismissed = db.Column(db.Boolean, default=False, nullable=False)

    seat = db.relationship('Seat', backref=db.backref('recovery_codes', lazy='dynamic'))


# ---- Payroll Settings Model ----
class PayrollSettings(db.Model):
    __tablename__ = 'payroll_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global/default settings
    pay_rate = db.Column(db.Numeric(precision=12, scale=2), nullable=False, default=0.25)  # $ per minute
    payroll_frequency_days = db.Column(db.Integer, nullable=False, default=14)
    next_payroll_date = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

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
    first_pay_date = db.Column(db.DateTime(timezone=True), nullable=True)  # First payday
    rounding_mode = db.Column(db.String(20), nullable=False, default='down')  # 'up' or 'down'

    # Economy Balance Check Field
    # NOTE: This is NOT used for actual payroll calculations - only for economy balance validation
    expected_weekly_hours = db.Column(db.Float, nullable=True, default=5.0)  # Expected class hours per week

    def __repr__(self):
        return f'<PayrollSettings class_id={self.class_id} block={self.block or "Global"}>'


# Adjustment state overlaps payroll rewards and fines


# ---- Banking Settings Model ----
class BankingSettings(db.Model):
    __tablename__ = 'banking_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, index=True)
    block = db.Column(db.String(10), nullable=True)  # NULL = global default, otherwise period/block identifier

    # Interest settings for savings
    savings_apy = db.Column(db.Numeric(precision=8, scale=6), default=Decimal('0.000000'))  # Annual Percentage Yield (e.g., 5.0 for 5%)
    savings_monthly_rate = db.Column(db.Numeric(precision=8, scale=6), default=Decimal('0.000000'))  # Monthly rate (calculated or custom)
    interest_calculation_type = db.Column(db.String(20), default='simple')  # 'simple' or 'compound'
    compound_frequency = db.Column(db.String(20), default='monthly')  # 'daily', 'weekly', 'monthly'

    # Interest payout schedule
    interest_schedule_type = db.Column(db.String(20), default='monthly')  # 'weekly', 'monthly'
    interest_schedule_cycle_days = db.Column(db.Integer, default=30)  # For monthly: 30 day cycle
    interest_payout_start_date = db.Column(db.DateTime(timezone=True), nullable=True)  # Starting date for payouts

    # Overdraft protection
    overdraft_protection_enabled = db.Column(db.Boolean, default=False)  # If enabled, savings covers checking

    # Overdraft/NSF fees
    overdraft_fee_enabled = db.Column(db.Boolean, default=False)  # Enable/disable overdraft fees
    overdraft_fee_type = db.Column(db.String(20), default='flat')  # 'flat' or 'progressive'
    overdraft_fee_flat_amount = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('0.00'))  # Flat fee per transaction

    # Progressive fee settings
    overdraft_fee_progressive_1 = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('0.00'))  # First tier fee
    overdraft_fee_progressive_2 = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('0.00'))  # Second tier fee
    overdraft_fee_progressive_3 = db.Column(db.Numeric(precision=12, scale=2), default=Decimal('0.00'))  # Third tier fee
    overdraft_fee_progressive_cap = db.Column(db.Numeric(precision=12, scale=2), nullable=True)  # Maximum total fees per period

    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f'<BankingSettings APY:{self.savings_apy}% OD:{self.overdraft_protection_enabled}>'


# -------------------- FEATURE SETTINGS MODEL --------------------
class ClassFeature(db.Model):
    """Row existence represents feature enablement for a class."""
    __tablename__ = 'class_features'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.String(36),
        db.ForeignKey('classes.class_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    feature_name = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('class_id', 'feature_name', name='uq_class_features_class_feature'),
        db.CheckConstraint(
            "feature_name IN ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')",
            name='ck_class_features_feature_name',
        ),
        db.Index('ix_class_features_feature_name', 'feature_name'),
    )

    @classmethod
    def feature_names(cls):
        return ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')

    @classmethod
    def defaults_dict(cls):
        return {
            f'{feature_name}_enabled': (feature_name == 'payroll')
            for feature_name in cls.feature_names()
        }

    @classmethod
    def enabled_names_for_class(cls, class_id):
        if not class_id:
            return set()
        return {
            feature_name
            for (feature_name,) in db.session.query(cls.feature_name)
            .filter(cls.class_id == class_id)
            .all()
        }

    @classmethod
    def feature_map_for_class(cls, class_id):
        enabled_names = cls.enabled_names_for_class(class_id)
        return {
            f'{feature_name}_enabled': feature_name in enabled_names
            for feature_name in cls.feature_names()
        }


class FeatureSettings(db.Model):
    """
    Per-class economy policy settings.

    Feature enablement lives in ``class_features``. This table only stores
    policy configuration that applies when a feature is enabled.
    """
    __tablename__ = 'feature_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Economy policy and rebalance tracking
    economy_policy_mode = db.Column(db.String(20), default='default', nullable=False)
    economy_policy_updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    economy_policy_alignment_status = db.Column(db.String(32), nullable=True)
    economy_last_rebalanced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    economy_last_rebalanced_by = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f'<FeatureSettings class_id={self.class_id}>'

    def to_dict(self):
        """Return enabled class features as a dictionary."""
        return ClassFeature.feature_map_for_class(self.class_id)

    @classmethod
    def get_defaults(cls):
        """Return the default feature map for newly created classes."""
        return ClassFeature.defaults_dict()


class PolicyVersion(db.Model):
    """Immutable class-scoped economic policy version lineage."""

    __tablename__ = 'policy_versions'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.String(36),
        db.ForeignKey('classes.class_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    domain = db.Column(db.String(32), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    policy_payload_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    activated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_transition_id = db.Column(db.Integer, db.ForeignKey('policy_transitions.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'class_id',
            'domain',
            'version_number',
            name='uq_policy_versions_class_domain_version',
        ),
        db.Index('ix_policy_versions_class_domain_active', 'class_id', 'domain', 'is_active'),
    )


class PolicyTransition(db.Model):
    """Append-only class-scoped economic policy transition lineage."""

    __tablename__ = 'policy_transitions'

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.String(36),
        db.ForeignKey('classes.class_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    domain = db.Column(db.String(32), nullable=False)
    source_policy_version_id = db.Column(db.Integer, db.ForeignKey('policy_versions.id'), nullable=True)
    target_policy_version_id = db.Column(db.Integer, db.ForeignKey('policy_versions.id'), nullable=False)
    activation_mode = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='pending')
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    created_by = db.Column(db.Integer, nullable=True)
    applied_at = db.Column(db.DateTime(timezone=True), nullable=True)
    correlation_id = db.Column(db.String(64), nullable=True, index=True)
    superseded_by_transition_id = db.Column(db.Integer, db.ForeignKey('policy_transitions.id'), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.Index('ix_policy_transitions_class_domain_status', 'class_id', 'domain', 'status'),
    )


@event.listens_for(ClassEconomy, 'after_insert')
def _seed_default_class_features(mapper, connection, target):
    """New classes start with payroll enabled and all other features disabled."""
    connection.execute(
        sa.insert(ClassFeature.__table__),
        {
            'class_id': target.class_id,
            'feature_name': 'payroll',
            'created_at': utc_now(),
        },
    )


# Teacher onboarding state is derived from class_features and feature_settings


# -------------------- ANNOUNCEMENT MODEL --------------------
class Announcement(db.Model):
    """
    Announcements for teachers and system administrators.

    Teacher Announcements:
    - Teachers post to specific class periods (scoped by class_id)
    - join_code remains ingress/display metadata only
    - Only visible to students in that class period

    Platform announcements:
    - System admins post with broader audience types
    - Can target: all students, all teachers, specific teacher's classes, or everyone
    - Teachers cannot see these in their announcement management
    """
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)

    # Author (one of these will be set)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    system_admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)

    # Audience targeting
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True, index=True)
    audience_type = db.Column(db.String(30), default='class', nullable=False)  # 'class', 'system_wide', 'all_teachers', 'all_students', 'teacher_all_classes', 'specific_class'
    target_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)  # For 'teacher_all_classes' audience type

    # Announcement content
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # Display settings
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    priority = db.Column(db.String(20), default='normal', nullable=False)  # 'low', 'normal', 'high', 'urgent'

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Optional expiration

    # Relationships
    teacher = db.relationship('User', foreign_keys=[user_id], backref=db.backref('announcements', lazy='dynamic', passive_deletes=True))
    system_admin = db.relationship('User', foreign_keys=[system_admin_id], backref=db.backref('sysadmin_announcements', lazy='dynamic', passive_deletes=True))
    target_teacher = db.relationship('User', foreign_keys=[target_teacher_id], backref=db.backref('targeted_announcements', lazy='dynamic', passive_deletes=True))

    # Indexes
    __table_args__ = (
        db.Index('ix_announcements_audience_type', 'audience_type', 'is_active'),
        db.Index('ix_announcements_system_admin', 'system_admin_id', 'is_active'),
    )

    def __repr__(self):
        author = f"Teacher {self.user_id}" if self.user_id else f"SysAdmin {self.system_admin_id}"
        return f'<Announcement {self.id} - {self.title[:30]} ({author}, {self.audience_type})>'

    def is_expired(self):
        """Check if announcement has expired."""
        if self.expires_at is None:
            return False

        expires_at = ensure_utc(self.expires_at)

        return utc_now() > expires_at

    def should_display(self):
        """Check if announcement should be displayed."""
        return self.is_active and not self.is_expired()

    def get_priority_class(self):
        """Get CSS class for announcement priority."""
        priority_classes = {
            'low': 'alert-secondary',
            'normal': 'alert-info',
            'high': 'alert-warning',
            'urgent': 'alert-danger'
        }
        return priority_classes.get(self.priority, 'alert-info')

    def get_priority_icon(self):
        """Get icon for announcement priority."""
        priority_icons = {
            'low': 'push_pin',
            'normal': 'campaign',
            'high': 'warning',
            'urgent': 'error'
        }
        return priority_icons.get(self.priority, 'campaign')

    def get_audience_label(self):
        """Get human-readable label for audience type."""
        labels = {
            'class': 'Class Period',
            'system_wide': 'Everyone (System-Wide)',
            'all_teachers': 'All Teachers',
            'all_students': 'All Students',
            'teacher_all_classes': 'Teacher\'s All Classes',
            'specific_class': 'Specific Class'
        }
        return labels.get(self.audience_type, 'Unknown')

    def is_system_admin_announcement(self):
        """Check if this is a system admin announcement."""
        return self.system_admin_id is not None


# Analytics state is represented by interpretation and audit tables


# -------------------- AUDIT LINEAGE MODELS --------------------


class AuditEvent(db.Model):
    """Append-only tamper-evident chain entry for all protected writes.

    Each row proves a specific mutation occurred through a lawful CTH execution
    path. Rows must never be updated or deleted by application code.

    Chain scope: "class:<class_id>" for class-scoped entities, "system" for
    platform/sysadmin events.
    """
    __tablename__ = "audit_events"

    id               = db.Column(db.Integer, primary_key=True)
    chain_scope      = db.Column(db.String(64), nullable=False)
    sequence_number  = db.Column(db.Integer, nullable=False)
    previous_hash    = db.Column(db.String(64), nullable=False)
    event_hash       = db.Column(db.String(64), nullable=False, unique=True)

    table_name       = db.Column(db.String(64), nullable=False)
    row_pk           = db.Column(db.String(64), nullable=False)
    operation        = db.Column(db.String(16), nullable=False)

    actor_type       = db.Column(db.String(32), nullable=True)
    actor_id_hash    = db.Column(db.String(64), nullable=True)
    class_id         = db.Column(db.String(36), nullable=True)
    seat_id          = db.Column(db.Integer, nullable=True)
    teacher_id       = db.Column(db.Integer, nullable=True)
    feat_id          = db.Column(db.String(32), nullable=True)
    idempotency_key  = db.Column(db.String(128), nullable=True)
    correlation_id   = db.Column(db.String(64), nullable=True)
    request_id       = db.Column(db.String(64), nullable=True)

    payload_digest   = db.Column(db.String(64), nullable=False)
    context_digest   = db.Column(db.String(64), nullable=False)
    created_at_utc   = db.Column(db.DateTime(timezone=True), nullable=False)
    signer_key_id    = db.Column(db.String(16), nullable=False, default="v1")
    signature_version = db.Column(db.Integer, nullable=False, default=1)
    hmac_signature   = db.Column(db.String(64), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("chain_scope", "sequence_number", name="uq_audit_chain_position"),
        db.Index("ix_audit_events_chain_scope", "chain_scope"),
        db.Index("ix_audit_events_class_id", "class_id"),
        db.Index("ix_audit_events_correlation_id", "correlation_id"),
        db.Index("ix_audit_events_table_row", "table_name", "row_pk"),
    )

    def __repr__(self):
        return f'<AuditEvent {self.chain_scope}#{self.sequence_number} {self.operation} {self.table_name}:{self.row_pk}>'


class ChainHead(db.Model):
    """One row per chain scope — tracks the latest hash and sequence number.

    Updated atomically (SELECT FOR UPDATE) with each AuditEvent insert so the
    chain never forks. Genesis rows use hash="genesis" and sequence=0.
    """
    __tablename__ = "chain_heads"

    chain_scope      = db.Column(db.String(64), primary_key=True)
    latest_hash      = db.Column(db.String(64), nullable=False)
    latest_sequence  = db.Column(db.Integer, nullable=False, default=0)
    event_count      = db.Column(db.Integer, nullable=False, default=0)
    last_updated_utc = db.Column(db.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f'<ChainHead {self.chain_scope} seq={self.latest_sequence}>'


# Integrity status is recomputable from chain_heads and audit_events
