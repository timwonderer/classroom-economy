"""Create interpretation_cycle_record table (DOM-ITR-001 §IX)

Revision ID: b3d7f1a9c2e4
Revises: 68e4cabff66e
Create Date: 2026-08-30

Durable, immutable per-cycle materialization of Interpretation output. One row
per (class_id, payroll_cycle_id), written only as a declared side effect of
FEAT-PROD-004 at payroll completion. Append-only; never recomputed. Not a cache.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'b3d7f1a9c2e4'
down_revision = '68e4cabff66e'
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
    if not table_exists('interpretation_cycle_record'):
        op.create_table(
            'interpretation_cycle_record',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('payroll_cycle_id', sa.String(length=36), nullable=False),
            sa.Column('cycle_started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('cycle_completed_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('reference_configuration', JSONB(), nullable=False),
            sa.Column('observations_json', JSONB(), nullable=False),
            sa.ForeignKeyConstraint(
                ['class_id'], ['classes.class_id'],
                name='fk_interpretation_cycle_record_class_id',
                ondelete='CASCADE',
            ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'class_id', 'payroll_cycle_id',
                name='uq_interpretation_cycle_record_class_cycle',
            ),
        )
        print("✅ Created interpretation_cycle_record")
    else:
        print("⚠️  Table 'interpretation_cycle_record' already exists, skipping...")

    if not index_exists('interpretation_cycle_record', 'ix_interpretation_cycle_record_class_id'):
        op.create_index(
            'ix_interpretation_cycle_record_class_id',
            'interpretation_cycle_record', ['class_id'],
        )
        print("✅ Created index ix_interpretation_cycle_record_class_id")
    else:
        print("⚠️  Index 'ix_interpretation_cycle_record_class_id' already exists, skipping...")

    if not index_exists('interpretation_cycle_record', 'ix_interpretation_cycle_record_payroll_cycle_id'):
        op.create_index(
            'ix_interpretation_cycle_record_payroll_cycle_id',
            'interpretation_cycle_record', ['payroll_cycle_id'],
        )
        print("✅ Created index ix_interpretation_cycle_record_payroll_cycle_id")
    else:
        print("⚠️  Index 'ix_interpretation_cycle_record_payroll_cycle_id' already exists, skipping...")


def downgrade():
    if index_exists('interpretation_cycle_record', 'ix_interpretation_cycle_record_payroll_cycle_id'):
        op.drop_index('ix_interpretation_cycle_record_payroll_cycle_id', table_name='interpretation_cycle_record')
        print("❌ Dropped index ix_interpretation_cycle_record_payroll_cycle_id")

    if index_exists('interpretation_cycle_record', 'ix_interpretation_cycle_record_class_id'):
        op.drop_index('ix_interpretation_cycle_record_class_id', table_name='interpretation_cycle_record')
        print("❌ Dropped index ix_interpretation_cycle_record_class_id")

    if table_exists('interpretation_cycle_record'):
        op.drop_table('interpretation_cycle_record')
        print("❌ Dropped table interpretation_cycle_record")
    else:
        print("⚠️  Table 'interpretation_cycle_record' does not exist, skipping...")
