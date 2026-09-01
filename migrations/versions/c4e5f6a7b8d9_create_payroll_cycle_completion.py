"""Create payroll_cycle_completion table (DOM-PROD-001 §XV)

Revision ID: c4e5f6a7b8d9
Revises: b3d7f1a9c2e4
Create Date: 2026-08-31

Persistent replay-identity anchor for a completed class-level payroll run. One row
per (class_id, idempotency_key), recording the payroll_cycle_id that run allocated.
Written in the same atomic commit as the payroll-completion lifecycle so it exists
iff the whole lifecycle committed; it is the top-level replay guard for
FEAT-PROD-004. Append-only; the anchor is immutable.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e5f6a7b8d9'
down_revision = 'b3d7f1a9c2e4'
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


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get FK constraints referencing a column (dynamic downgrade discovery)."""
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

def upgrade():
    if not table_exists('payroll_cycle_completion'):
        op.create_table(
            'payroll_cycle_completion',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('idempotency_key', sa.String(length=255), nullable=False),
            sa.Column('payroll_cycle_id', sa.String(length=36), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ['class_id'], ['classes.class_id'],
                name='fk_payroll_cycle_completion_class_id',
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'class_id', 'idempotency_key',
                name='uq_payroll_cycle_completion_class_key',
            ),
        )
        print("✅ Created payroll_cycle_completion")
    else:
        print("⚠️  Table 'payroll_cycle_completion' already exists, skipping...")

    if not index_exists('payroll_cycle_completion', 'ix_payroll_cycle_completion_class_id'):
        op.create_index(
            'ix_payroll_cycle_completion_class_id',
            'payroll_cycle_completion', ['class_id'],
        )
        print("✅ Created index ix_payroll_cycle_completion_class_id")
    else:
        print("⚠️  Index 'ix_payroll_cycle_completion_class_id' already exists, skipping...")

    if not index_exists('payroll_cycle_completion', 'ix_payroll_cycle_completion_payroll_cycle_id'):
        op.create_index(
            'ix_payroll_cycle_completion_payroll_cycle_id',
            'payroll_cycle_completion', ['payroll_cycle_id'],
        )
        print("✅ Created index ix_payroll_cycle_completion_payroll_cycle_id")
    else:
        print("⚠️  Index 'ix_payroll_cycle_completion_payroll_cycle_id' already exists, skipping...")


def downgrade():
    if index_exists('payroll_cycle_completion', 'ix_payroll_cycle_completion_payroll_cycle_id'):
        op.drop_index('ix_payroll_cycle_completion_payroll_cycle_id', table_name='payroll_cycle_completion')
        print("❌ Dropped index ix_payroll_cycle_completion_payroll_cycle_id")

    if index_exists('payroll_cycle_completion', 'ix_payroll_cycle_completion_class_id'):
        op.drop_index('ix_payroll_cycle_completion_class_id', table_name='payroll_cycle_completion')
        print("❌ Dropped index ix_payroll_cycle_completion_class_id")

    if table_exists('payroll_cycle_completion'):
        op.drop_table('payroll_cycle_completion')
        print("❌ Dropped table payroll_cycle_completion")
    else:
        print("⚠️  Table 'payroll_cycle_completion' does not exist, skipping...")
