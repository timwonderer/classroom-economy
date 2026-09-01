"""Add payroll_cycle_id to payroll_event (DOM-PROD-001 §XV)

Revision ID: d5f6a7b8c9e0
Revises: c4e5f6a7b8d9
Create Date: 2026-08-31

Economic-cycle attribution for payroll events. Class-wide cycle settlement stamps
the same payroll_cycle_id on every payroll event it produces, so a completed
class-level cycle is queryable as a unit. NULL for events recorded outside a
completed cycle (ad-hoc per-seat runs, manual credits, reversals). Nullable and
additive — existing rows and callers are unaffected.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5f6a7b8c9e0'
down_revision = 'c4e5f6a7b8d9'
branch_labels = None
depends_on = None


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


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if table_exists('payroll_event') and not column_exists('payroll_event', 'payroll_cycle_id'):
        op.add_column(
            'payroll_event',
            sa.Column('payroll_cycle_id', sa.String(length=36), nullable=True),
        )
        print("✅ Added payroll_event.payroll_cycle_id")
    else:
        print("⚠️  Column 'payroll_cycle_id' already exists on 'payroll_event' (or table missing), skipping...")

    if table_exists('payroll_event') and not index_exists('payroll_event', 'ix_payroll_event_payroll_cycle_id'):
        op.create_index(
            'ix_payroll_event_payroll_cycle_id',
            'payroll_event', ['payroll_cycle_id'],
        )
        print("✅ Created index ix_payroll_event_payroll_cycle_id")
    else:
        print("⚠️  Index 'ix_payroll_event_payroll_cycle_id' already exists (or table missing), skipping...")


def downgrade():
    if index_exists('payroll_event', 'ix_payroll_event_payroll_cycle_id'):
        op.drop_index('ix_payroll_event_payroll_cycle_id', table_name='payroll_event')
        print("❌ Dropped index ix_payroll_event_payroll_cycle_id")

    if column_exists('payroll_event', 'payroll_cycle_id'):
        op.drop_column('payroll_event', 'payroll_cycle_id')
        print("❌ Dropped payroll_event.payroll_cycle_id")
    else:
        print("⚠️  Column 'payroll_cycle_id' does not exist on 'payroll_event', skipping...")
