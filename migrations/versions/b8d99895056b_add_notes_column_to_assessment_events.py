"""Add notes column to assessment_events

Adds an optional TEXT column `notes` to `assessment_events` per
DOM-OBL-001 §VII.1 (notes column contract). Free-text teacher-entered
metadata, immutable after insert, not consulted by any legality check.
Populated by FEAT-OBL-003 (satisfy obligation) when a waiver reason is
supplied via the admin waivers UI; NULL for all pre-existing rows and
for events without a note.

Revision ID: b8d99895056b
Revises: 2978fdba914a
Create Date: 2026-08-16 21:31:16.319616

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
revision = 'b8d99895056b'
down_revision = '2978fdba914a'
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists('assessment_events', 'notes'):
        op.add_column(
            'assessment_events',
            sa.Column('notes', sa.Text(), nullable=True),
        )
        print("✅ Added assessment_events.notes")
    else:
        print("⚠️  assessment_events.notes already exists, skipping")


def downgrade():
    if column_exists('assessment_events', 'notes'):
        op.drop_column('assessment_events', 'notes')
        print("❌ Dropped assessment_events.notes")
    else:
        print("⚠️  assessment_events.notes already absent, skipping")
