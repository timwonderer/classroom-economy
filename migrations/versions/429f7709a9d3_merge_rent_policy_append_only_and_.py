"""Merge rent policy append-only and ledger persistence

Revision ID: 429f7709a9d3
Revises: d5e6f7a8b9c0, e6f7a8b9c0d1
Create Date: 2026-09-04 18:43:38.984435

Two migrations were authored in parallel off the same parent (``c4d5e6f7a8b9``):
``d5e6f7a8b9c0`` made ``rent_settings`` an append-only policy repository, and
``e6f7a8b9c0d1`` canonicalized Ledger persistence. They touch disjoint tables and
have no ordering relationship, so this merge simply rejoins the graph to a single
head. It performs no schema work of its own — ``upgrade`` and ``downgrade`` are
intentionally empty.

Worth recording, because it cost time to diagnose: the shared development
database was stamped at ``e6f7a8b9c0d1`` while that revision existed only as an
untracked file in the ledger worktree. From any other worktree alembic could not
resolve the stamp, and ``flask db current`` failed with "Can't locate revision" —
real schema, applied and stamped, from a file no branch had. Committing the
migration is what made the situation legible; this merge is what makes it
linear again.
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
revision = '429f7709a9d3'
down_revision = ('d5e6f7a8b9c0', 'e6f7a8b9c0d1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
