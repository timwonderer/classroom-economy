"""Drop all unauthorized tables per DOM-CORE-002 constitutional audit

Revision ID: 7c3d4e5f6a7b
Revises: 6b2c3d4e5f6a
Create Date: 2026-07-16 08:00:00.000000

Drops every table that is not authorized by DOM-CORE-002 v1.6 or that is
explicitly prohibited by INV-IDEN-001 / DOM-CORE-002 §1-2.

Drop groups (rationale in comments):
  A. Insurance system       — no domain authority
  B. Rent derived state     — obligation_satisfaction + obligation_reversal cover this
  C. Legacy identity        — INV-IDEN-001 prohibition
  D. Persisted compute      — DOM-CORE-002 §2 explicit prohibition
  E. Legacy error pipeline  — absorbed into operational_events (DOM-OPS-001)
  F. Analytics / ITR        — absorbed into canonical interpretation + OPS tables
  G. Support (user_reports) — absorbed into issues pipeline (DOM-SUP-001) [also in 6b2c3d4e5f6a]
  H. Misc unauthorized      — no authoritative state or redundant
"""

import sqlalchemy as sa
from alembic import op

# ============================================================================
# IDEMPOTENCY HELPERS
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [c['name'] for c in inspector.get_columns(table_name)]
    except Exception:
        return False

def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [i['name'] for i in inspector.get_indexes(table_name)]
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

def foreign_key_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(fk.get('name') == constraint_name for fk in inspector.get_foreign_keys(table_name))
    except Exception:
        return False

def drop_table_if_exists(table_name):
    if table_exists(table_name):
        op.drop_table(table_name)
        print(f"✅ Dropped {table_name}")
    else:
        print(f"⚠️  {table_name} does not exist, skipping")


def drop_constraint_if_exists(table_name, constraint_name):
    if not table_exists(table_name):
        return
    if foreign_key_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_='foreignkey')
        print(f"✅ Dropped constraint {constraint_name}")

# ============================================================================

revision = '7c3d4e5f6a7b'
down_revision = '6b2c3d4e5f6a'
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================================
    # GROUP A: Insurance system — no domain authority
    # Canonical replacement: policy_versions(domain='insurance') for policy
    # content; obligation_lifecycle/satisfaction for enrollment state;
    # obligation_satisfaction/reversal for claims.
    # Drop order: dependents first (claims → enrollments → policy_blocks → policies)
    # =========================================================================
    drop_table_if_exists('insurance_claims')
    drop_table_if_exists('insurance_enrollments')
    drop_table_if_exists('insurance_policy_blocks')
    drop_constraint_if_exists('ledger_transaction', 'ledger_transaction_policy_id_fkey')
    drop_table_if_exists('insurance_policies')

    # =========================================================================
    # GROUP B: Rent derived state
    # rent_payments → obligation_satisfaction(method=PAYMENT) + ledger_transaction ref
    # rent_waivers  → obligation_satisfaction(method=WAIVER)
    # rent_items    → store_items + rent_settings
    # rent_policy_versions → policy_versions(domain='rent')
    # Drop order: payments/waivers before items/policy_versions (FK chain)
    # =========================================================================
    drop_table_if_exists('rent_payments')
    drop_table_if_exists('rent_waivers')
    drop_table_if_exists('rent_items')
    drop_constraint_if_exists('rent_settings', 'fk_rent_settings_active_version_id')
    drop_constraint_if_exists('rent_settings', 'fk_rent_settings_next_version_id')
    drop_constraint_if_exists('assessment_events', 'fk_assessment_events_rent_policy_version_id')
    drop_table_if_exists('rent_policy_versions')

    # =========================================================================
    # GROUP C: Legacy identity tables — INV-IDEN-001 prohibition
    # teachers             → User(user_role=TEACHER)
    # system_admins        → User(user_role=SYSADMIN)
    # teacher_invite_codes → open signup flow (DOM-IDEN-001)
    # user_invite_tokens   → EXTINCT (DOM-CORE-002 §1)
    # user_recovery_tokens → EXTINCT (DOM-CORE-002 §1)
    # class_memberships    → deprecated; ClassEconomy/classes is canonical
    # system_admin_credentials / teacher_credentials → split-credential migration artifacts
    # =========================================================================
    drop_table_if_exists('teacher_invite_codes')
    drop_table_if_exists('user_invite_tokens')
    drop_table_if_exists('user_recovery_tokens')
    drop_table_if_exists('class_memberships')
    drop_table_if_exists('system_admin_credentials')
    drop_table_if_exists('teacher_credentials')
    # teachers / system_admins dropped last (other tables may FK to them)
    drop_constraint_if_exists('ledger_transaction', 'ledger_transaction_teacher_id_fkey')
    drop_table_if_exists('system_admins')
    drop_table_if_exists('teachers')

    # =========================================================================
    # GROUP D: Persisted compute — DOM-CORE-002 §2 explicit prohibition
    # "No persisted compute-result caches"
    # =========================================================================
    drop_table_if_exists('payroll_cache')

    # =========================================================================
    # GROUP E: Legacy error pipeline
    # error_logs   → to be replaced by operational_events(level=ERROR|CRITICAL)
    # error_events → absorbed into operational_events (DOM-OPS-001)
    # =========================================================================
    drop_table_if_exists('error_logs')
    drop_table_if_exists('error_events')

    # =========================================================================
    # GROUP F: Analytics / ITR — absorbed into canonical tables
    # analytics_snapshots → interpretation_snapshots (DOM-ITR-001)
    # analytics_alerts    → alert_events (DOM-OPS-001)
    # analytics_events    → audit_events / interpretation_annotations
    # economy_snapshot    → derived interpretation cache (DOM-ITR-001)
    # integrity_status    → recomputable from chain_heads + audit_events
    # =========================================================================
    drop_table_if_exists('analytics_snapshots')
    drop_table_if_exists('analytics_alerts')
    drop_table_if_exists('analytics_events')
    drop_table_if_exists('economy_snapshots')  # also try plural form
    drop_table_if_exists('economy_snapshot')
    drop_table_if_exists('integrity_status')

    # =========================================================================
    # GROUP G: Support — absorbed into issues pipeline (DOM-SUP-001)
    # user_reports dropped by migration 6b2c3d4e5f6a; guard here for safety
    # =========================================================================
    drop_table_if_exists('user_reports')

    # =========================================================================
    # GROUP H: Misc unauthorized
    # saved_adjustments  → overlaps payroll_rewards/payroll_fines (DOM-CLASS-001)
    # teacher_onboarding → derived from class_features + feature_settings
    # =========================================================================
    drop_table_if_exists('saved_adjustments')
    drop_table_if_exists('teacher_onboarding')

    print("✅ All unauthorized tables dropped")


def downgrade():
    # These tables are being permanently removed as part of constitutional
    # compliance. Downgrade is intentionally not implemented — restoring
    # these tables would require a full code rollback, not just schema rollback.
    raise NotImplementedError(
        "Downgrade not supported: these tables are constitutionally prohibited "
        "and must not be restored. Roll back via git if needed."
    )
