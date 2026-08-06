"""Add one-terminal-per-lineage unique partial index to entitlement_events

Revision ID: 8c62d78f82bb
Revises: a1c2d3e4f5a6
Create Date: 2026-08-06 04:49:43.153614

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
    """Get FKs for a column (for downgrade without hardcoded names)."""
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
revision = '8c62d78f82bb'
down_revision = 'a1c2d3e4f5a6'
branch_labels = None
depends_on = None

INDEX_NAME = 'ix_entitlement_events_one_terminal_per_lineage'


def upgrade():
    if not index_exists('entitlement_events', INDEX_NAME):
        op.create_index(
            INDEX_NAME,
            'entitlement_events',
            ['entitlement_id', 'class_id'],
            unique=True,
            postgresql_where=sa.text("event_type IN ('CONSUMED', 'EXPIRED', 'REVOKED')"),
        )
        print(f"✅ Created unique partial index {INDEX_NAME}")
    else:
        print(f"⚠️  Index {INDEX_NAME} already exists, skipping...")


def downgrade():
    if index_exists('entitlement_events', INDEX_NAME):
        op.drop_index(
            INDEX_NAME,
            table_name='entitlement_events',
            postgresql_where=sa.text("event_type IN ('CONSUMED', 'EXPIRED', 'REVOKED')"),
        )
        print(f"❌ Dropped index {INDEX_NAME}")
    else:
        print(f"⚠️  Index {INDEX_NAME} does not exist, skipping...")
