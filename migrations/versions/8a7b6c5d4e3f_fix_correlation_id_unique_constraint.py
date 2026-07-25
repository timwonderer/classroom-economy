"""Fix: Make correlation_id non-unique on assessment_events per DOM-OBL-001

Revision ID: 8a7b6c5d4e3f
Revises: merge_heads_0009_5a98_a0b1
Create Date: 2026-07-25 19:10:00.000000

Per DOM-OBL-001, assessment_events can have multiple rows with the same
correlation_id (ASSESSMENT, WAIVED, PAYMENT events for the same obligation).
The unique index must be changed to non-unique to allow this.
"""
from alembic import op
import sqlalchemy as sa


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


revision = '8a7b6c5d4e3f'
down_revision = 'merge_heads_0009_5a98_a0b1'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the unique index on correlation_id (allows only 1 value per correlation)
    # and replace with non-unique index (allows multiple values per correlation)
    if index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.drop_index('ix_assessment_events_correlation_id', table_name='assessment_events')
        print("✅ Dropped unique index ix_assessment_events_correlation_id")

    # Create non-unique index for performance on correlation_id queries
    if not index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.create_index(
            'ix_assessment_events_correlation_id',
            'assessment_events',
            ['correlation_id'],
            unique=False
        )
        print("✅ Created non-unique index ix_assessment_events_correlation_id")


def downgrade():
    # Restore the unique index
    if index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.drop_index('ix_assessment_events_correlation_id', table_name='assessment_events')
        print("✅ Dropped non-unique index ix_assessment_events_correlation_id")

    if not index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.create_index(
            op.f('ix_assessment_events_correlation_id'),
            'assessment_events',
            ['correlation_id'],
            unique=True
        )
        print("✅ Recreated unique index ix_assessment_events_correlation_id")
