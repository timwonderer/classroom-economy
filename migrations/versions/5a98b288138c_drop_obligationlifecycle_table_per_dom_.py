"""Drop ObligationLifecycle table per DOM-OBL-001

Revision ID: 5a98b288138c
Revises: merge_0008_2c3d4e5f6a7b
Create Date: 2026-07-24 21:55:44.282834

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
revision = '5a98b288138c'
down_revision = 'merge_0008_2c3d4e5f6a7b'
branch_labels = None
depends_on = None


def upgrade():
    # Per DOM-OBL-001 §VI, obligation_lifecycle is not canonical and must be dropped
    # The class was removed from the ORM model in Phase 9

    if table_exists('obligation_lifecycle'):
        # Drop indexes first
        if index_exists('obligation_lifecycle', 'ix_obligation_lifecycle_assessment_id'):
            op.drop_index('ix_obligation_lifecycle_assessment_id', table_name='obligation_lifecycle')
            print("✅ Dropped index ix_obligation_lifecycle_assessment_id")
        else:
            print("⚠️  Index ix_obligation_lifecycle_assessment_id does not exist, skipping...")

        if index_exists('obligation_lifecycle', 'ix_obligation_lifecycle_status'):
            op.drop_index('ix_obligation_lifecycle_status', table_name='obligation_lifecycle')
            print("✅ Dropped index ix_obligation_lifecycle_status")
        else:
            print("⚠️  Index ix_obligation_lifecycle_status does not exist, skipping...")

        # Drop table
        op.drop_table('obligation_lifecycle')
        print("✅ Dropped obligation_lifecycle table")
    else:
        print("⚠️  Table obligation_lifecycle does not exist, skipping...")


def downgrade():
    # Recreate obligation_lifecycle table (for rollback/testing purposes)

    if not table_exists('obligation_lifecycle'):
        op.create_table(
            'obligation_lifecycle',
            sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
            sa.Column('assessment_id', sa.INTEGER(), autoincrement=False, nullable=False),
            sa.Column('status', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
            sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
            sa.ForeignKeyConstraint(['assessment_id'], ['assessment_events.id'], name='obligation_lifecycle_assessment_id_fkey', ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id', name='obligation_lifecycle_pkey')
        )
        print("✅ Recreated obligation_lifecycle table")

        # Create indexes
        op.create_index('ix_obligation_lifecycle_status', 'obligation_lifecycle', ['status'], unique=False)
        op.create_index('ix_obligation_lifecycle_assessment_id', 'obligation_lifecycle', ['assessment_id'], unique=True)
        print("✅ Recreated obligation_lifecycle indexes")
    else:
        print("⚠️  Table obligation_lifecycle already exists, skipping...")
