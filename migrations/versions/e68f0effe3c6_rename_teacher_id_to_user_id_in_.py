"""Rename teacher_id to user_id in ClassEconomy

Revision ID: e68f0effe3c6
Revises: 4beac340ed58
Create Date: 2026-06-27 20:26:33.881185

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
revision = 'e68f0effe3c6'
down_revision = '4beac340ed58'
branch_labels = None
depends_on = None


def upgrade():
    # Rename teacher_id to user_id
    op.alter_column('classes', 'teacher_id', new_column_name='user_id')
    op.drop_index(op.f('ix_classes_teacher_id'), table_name='classes')
    op.create_index(op.f('ix_classes_user_id'), 'classes', ['user_id'], unique=False)



def downgrade():
    op.alter_column('classes', 'user_id', new_column_name='teacher_id')
    op.drop_index(op.f('ix_classes_user_id'), table_name='classes')
    op.create_index(op.f('ix_classes_teacher_id'), 'classes', ['teacher_id'], unique=False)

