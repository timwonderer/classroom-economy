"""Canonical V2 ORM models (DOM-CORE-002).

Wave 1 scope: define the 44 canonical table mappings as an authoritative
reference without changing runtime behavior.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True)
    user_role = sa.Column(
        sa.Enum("student", "teacher", "sysadmin", name="user_role_enum"),
        nullable=True,
        index=True,
    )
    username_hash = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    username_lookup_hash = sa.Column(sa.String(64), unique=True, nullable=True, index=True)
    totp_secret_encrypted = sa.Column(sa.String(200), nullable=True)
    pin_hash = sa.Column(sa.Text, nullable=True)
    passphrase_hash = sa.Column(sa.Text, nullable=True)
    current_session_started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    current_session_expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    current_session_nonce = sa.Column(sa.String(128), nullable=True, index=True)
    # Student recovery fields (DOM-IDEN-002 §V)
    reset_code = sa.Column(sa.String(8), nullable=True)
    reset_code_generated_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    reset_code_expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    last_active_seat_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("seats.id", ondelete="SET NULL", use_alter=True, name="fk_users_last_active_seat_id_seats"),
        nullable=True,
        index=True,
    )


class Seat(Base, TimestampMixin):
    __tablename__ = "seats"
    id = sa.Column(sa.Integer, primary_key=True)
    public_id = sa.Column(
        sa.String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    class_id = sa.Column(sa.String(36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False, index=True)
    role = sa.Column(sa.String(20), nullable=False)
    roster_fingerprint = sa.Column(sa.String(128), nullable=True, index=True)
    dedupe_code = sa.Column(sa.String(8), nullable=True)
    claim_first_name_hash = sa.Column(sa.String(128), nullable=True, index=True)
    claim_last_name_hash = sa.Column(sa.String(128), nullable=True, index=True)
    claimed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    __table_args__ = (
        sa.UniqueConstraint("user_id", "class_id", name="uq_seats_user_class"),
    )


class Class_(Base, TimestampMixin):
    __tablename__ = "classes"
    class_id = sa.Column(sa.String(36), primary_key=True)
    join_code_token = sa.Column(sa.String(20), unique=True, nullable=True, index=True)
    section = sa.Column(sa.String(50), nullable=True)
    display_name = sa.Column(sa.String(100), nullable=True)


class IdentityProfile(Base, TimestampMixin):
    __tablename__ = "identity_profiles"
    id = sa.Column(sa.Integer, primary_key=True)
    seat_id = sa.Column(sa.Integer, sa.ForeignKey("seats.id", ondelete="CASCADE"), unique=True, nullable=True, index=True)
    first_name = sa.Column(sa.LargeBinary, nullable=False)
    last_name = sa.Column(sa.LargeBinary, nullable=False)
    notes = sa.Column(sa.LargeBinary, nullable=True)


class UserInviteToken(Base, TimestampMixin):
    __tablename__ = "user_invite_tokens"
    id = sa.Column(sa.Integer, primary_key=True)
    token_hash = sa.Column(sa.String(128), unique=True, nullable=False, index=True)
    user_role = sa.Column(
        sa.Enum("student", "teacher", "sysadmin", name="user_role_enum"),
        nullable=False,
    )
    issued_by_user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


class UserRecoveryToken(Base, TimestampMixin):
    __tablename__ = "user_recovery_tokens"
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = sa.Column(sa.String(128), unique=True, nullable=False, index=True)
    issued_by_user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
    used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


class ClassFeature(Base, TimestampMixin):
    __tablename__ = "class_features"
    id = sa.Column(sa.Integer, primary_key=True)


class FeatureSetting(Base, TimestampMixin):
    __tablename__ = "feature_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class PolicyVersion(Base, TimestampMixin):
    __tablename__ = "policy_versions"
    id = sa.Column(sa.Integer, primary_key=True)


class PolicyTransition(Base, TimestampMixin):
    __tablename__ = "policy_transitions"
    id = sa.Column(sa.Integer, primary_key=True)


class HallPassSetting(Base, TimestampMixin):
    __tablename__ = "hall_pass_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class RentSetting(Base, TimestampMixin):
    __tablename__ = "rent_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class PayrollSetting(Base, TimestampMixin):
    __tablename__ = "payroll_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class SavedAdjustment(Base, TimestampMixin):
    __tablename__ = "saved_adjustments"
    id = sa.Column(sa.Integer, primary_key=True)


class BankingSetting(Base, TimestampMixin):
    __tablename__ = "banking_settings"
    id = sa.Column(sa.Integer, primary_key=True)


class AttendanceSession(Base, TimestampMixin):
    __tablename__ = "attendance_sessions"
    id = sa.Column(sa.Integer, primary_key=True)


class HallPassLog(Base, TimestampMixin):
    __tablename__ = "hall_pass_logs"
    id = sa.Column(sa.Integer, primary_key=True)


class SeatAttendanceState(Base, TimestampMixin):
    __tablename__ = "seat_attendance_state"
    id = sa.Column(sa.Integer, primary_key=True)


class AssessmentEvent(Base, TimestampMixin):
    __tablename__ = "assessment_events"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationLifecycle(Base, TimestampMixin):
    __tablename__ = "obligation_lifecycle"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationSatisfaction(Base, TimestampMixin):
    __tablename__ = "obligation_satisfaction"
    id = sa.Column(sa.Integer, primary_key=True)


class ObligationReversal(Base, TimestampMixin):
    __tablename__ = "obligation_reversal"
    id = sa.Column(sa.Integer, primary_key=True)


class EntitlementEvent(Base, TimestampMixin):
    __tablename__ = "entitlement_events"
    id = sa.Column(sa.Integer, primary_key=True)


class LedgerTransaction(Base, TimestampMixin):
    __tablename__ = "ledger_transaction"
    id = sa.Column(sa.Integer, primary_key=True)


class LedgerBalanceSnapshot(Base, TimestampMixin):
    __tablename__ = "ledger_balance_snapshot"
    id = sa.Column(sa.Integer, primary_key=True)


class StoreItem(Base, TimestampMixin):
    __tablename__ = "store_items"
    id = sa.Column(sa.Integer, primary_key=True)


class StoreItemVisibility(Base, TimestampMixin):
    __tablename__ = "store_item_visibility"
    id = sa.Column(sa.Integer, primary_key=True)


class StorePurchase(Base, TimestampMixin):
    __tablename__ = "store_purchases"
    id = sa.Column(sa.Integer, primary_key=True)


class RedemptionEvent(Base, TimestampMixin):
    __tablename__ = "redemption_events"
    id = sa.Column(sa.Integer, primary_key=True)


class OperationalEvent(Base, TimestampMixin):
    __tablename__ = "operational_events"
    id = sa.Column(sa.Integer, primary_key=True)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"
    id = sa.Column(sa.Integer, primary_key=True)


class IncidentEvent(Base, TimestampMixin):
    __tablename__ = "incident_events"
    id = sa.Column(sa.Integer, primary_key=True)


class IncidentSummary(Base, TimestampMixin):
    __tablename__ = "incident_summary"
    id = sa.Column(sa.Integer, primary_key=True)


class AlertEvent(Base, TimestampMixin):
    __tablename__ = "alert_events"
    id = sa.Column(sa.Integer, primary_key=True)


class InvariantRunEvent(Base, TimestampMixin):
    __tablename__ = "invariant_run_events"
    id = sa.Column(sa.Integer, primary_key=True)


class JobEvent(Base, TimestampMixin):
    __tablename__ = "job_events"
    id = sa.Column(sa.Integer, primary_key=True)


class HealthCheckEvent(Base, TimestampMixin):
    __tablename__ = "health_check_events"
    id = sa.Column(sa.Integer, primary_key=True)


class InterpretationSnapshot(Base, TimestampMixin):
    __tablename__ = "interpretation_snapshots"
    id = sa.Column(sa.Integer, primary_key=True)


class InterpretationAnnotation(Base, TimestampMixin):
    __tablename__ = "interpretation_annotations"
    id = sa.Column(sa.Integer, primary_key=True)


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueStatusHistory(Base, TimestampMixin):
    __tablename__ = "issue_status_history"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueResolutionAction(Base, TimestampMixin):
    __tablename__ = "issue_resolution_actions"
    id = sa.Column(sa.Integer, primary_key=True)


class TicketCorrelationPack(Base, TimestampMixin):
    __tablename__ = "ticket_correlation_packs"
    id = sa.Column(sa.Integer, primary_key=True)


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"
    id = sa.Column(sa.Integer, primary_key=True)


class IssueCategory(Base, TimestampMixin):
    __tablename__ = "issue_categories"
    id = sa.Column(sa.Integer, primary_key=True)


__all__ = [
    "User",
    "Seat",
    "Class_",
    "IdentityProfile",
    "UserInviteToken",
    "UserRecoveryToken",
    "ClassFeature",
    "FeatureSetting",
    "PolicyVersion",
    "PolicyTransition",
    "HallPassSetting",
    "RentSetting",
    "PayrollSetting",
    "SavedAdjustment",
    "BankingSetting",
    "AttendanceSession",
    "HallPassLog",
    "SeatAttendanceState",
    "AssessmentEvent",
    "ObligationLifecycle",
    "ObligationSatisfaction",
    "ObligationReversal",
    "EntitlementEvent",
    "LedgerTransaction",
    "LedgerBalanceSnapshot",
    "StoreItem",
    "StoreItemVisibility",
    "StorePurchase",
    "RedemptionEvent",
    "OperationalEvent",
    "AuditLog",
    "IncidentEvent",
    "IncidentSummary",
    "AlertEvent",
    "InvariantRunEvent",
    "JobEvent",
    "HealthCheckEvent",
    "InterpretationSnapshot",
    "InterpretationAnnotation",
    "Issue",
    "IssueStatusHistory",
    "IssueResolutionAction",
    "TicketCorrelationPack",
    "Announcement",
    "IssueCategory",
]
