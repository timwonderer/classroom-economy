"""Make bill_cycles.next_assessment_at nullable for terminal cycles

Revision ID: 1ed7b3643792
Revises: d5f6a7b8c9e0
Create Date: 2026-09-03 03:26:01.513048

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = '1ed7b3643792'
down_revision = 'd5f6a7b8c9e0'
branch_labels = None
depends_on = None


def upgrade():
    # Scope: ONLY bill_cycles.next_assessment_at nullability. Autogen also
    # surfaced unrelated model drift owned by other in-flight work (assessment_events,
    # attendance_sessions, classes, hall_pass_settings, identity_profiles,
    # insurance_claim_productivity_dates, ledger_balance_snapshot, payroll_settings);
    # those are intentionally excluded from this migration.
    #
    # A terminal bill cycle (DOM-OBL-001 §160/§241) carries no next assessment —
    # next_assessment_at = NULL stops future recurrence. Make the column nullable.
    if column_exists('bill_cycles', 'next_assessment_at'):
        op.alter_column('bill_cycles', 'next_assessment_at',
                   existing_type=postgresql.TIMESTAMP(timezone=True),
                   nullable=True)
        print("✅ bill_cycles.next_assessment_at is now nullable")
    else:
        print("⚠️  bill_cycles.next_assessment_at missing, skipping")


def downgrade():
    # Reverse only the bill_cycles change. Restoring NOT NULL requires that no
    # terminal (NULL) rows exist; backfill a sentinel = cycle_boundary_at so the
    # constraint can be reinstated without data loss on rollback.
    if column_exists('bill_cycles', 'next_assessment_at'):
        op.execute(
            "UPDATE bill_cycles SET next_assessment_at = cycle_boundary_at "
            "WHERE next_assessment_at IS NULL"
        )
        op.alter_column('bill_cycles', 'next_assessment_at',
                   existing_type=postgresql.TIMESTAMP(timezone=True),
                   nullable=False)
        print("❌ bill_cycles.next_assessment_at reverted to NOT NULL")
    else:
        print("⚠️  bill_cycles.next_assessment_at missing, skipping")
