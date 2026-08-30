"""Increase payroll pay rate precision

Revision ID: 6f79a33fe78a
Revises: d0bb45617620
Create Date: 2026-08-30 19:16:55.108027

"""
from alembic import op
import sqlalchemy as sa


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
revision = '6f79a33fe78a'
down_revision = 'd0bb45617620'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('payroll_settings') and column_exists('payroll_settings', 'pay_rate'):
        op.alter_column(
            'payroll_settings',
            'pay_rate',
            existing_type=sa.Numeric(precision=12, scale=2),
            type_=sa.Numeric(precision=18, scale=8),
            existing_nullable=False,
        )


def downgrade():
    if table_exists('payroll_settings') and column_exists('payroll_settings', 'pay_rate'):
        op.alter_column(
            'payroll_settings',
            'pay_rate',
            existing_type=sa.Numeric(precision=18, scale=8),
            type_=sa.Numeric(precision=12, scale=2),
            existing_nullable=False,
        )
