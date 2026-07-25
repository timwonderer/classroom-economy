"""Remove legacy bridge columns from assessment_events table.

Revision ID: a0b1c2d3e4f5
Revises: merge_heads_0008_2c3d4e5f6a7b
Create Date: 2026-07-25 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0b1c2d3e4f5'
down_revision = 'merge_heads_0008_2c3d4e5f6a7b'
branch_labels = None
depends_on = None


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


def upgrade():
    """Remove legacy bridge columns per DOM-IDEN-007.

    NOTE: coverage_start_time and coverage_end_time are retained for WAIVED events
    to record the waived period (DOM-OBL-001 §VII.2).
    """

    # Remove indexes before dropping columns
    if index_exists('assessment_events', 'ix_assessment_events_join_code'):
        op.drop_index('ix_assessment_events_join_code', table_name='assessment_events')
        print("✅ Dropped index ix_assessment_events_join_code")

    if index_exists('assessment_events', 'ix_assessment_events_period'):
        op.drop_index('ix_assessment_events_period', table_name='assessment_events')
        print("✅ Dropped index ix_assessment_events_period")

    if index_exists('assessment_events', 'ix_assessment_events_coverage_start'):
        op.drop_index('ix_assessment_events_coverage_start', table_name='assessment_events')
        print("✅ Dropped index ix_assessment_events_coverage_start")

    if index_exists('assessment_events', 'ix_assessment_events_cycle_idempotency'):
        op.drop_index('ix_assessment_events_cycle_idempotency', table_name='assessment_events')
        print("✅ Dropped index ix_assessment_events_cycle_idempotency")

    # Drop bridge columns (but NOT coverage_start_time/coverage_end_time — those are domain data for WAIVED)
    if column_exists('assessment_events', 'join_code'):
        op.drop_column('assessment_events', 'join_code')
        print("✅ Dropped column join_code")

    if column_exists('assessment_events', 'period'):
        op.drop_column('assessment_events', 'period')
        print("✅ Dropped column period")

    if column_exists('assessment_events', 'period_key'):
        op.drop_column('assessment_events', 'period_key')
        print("✅ Dropped column period_key")

    if column_exists('assessment_events', 'period_month'):
        op.drop_column('assessment_events', 'period_month')
        print("✅ Dropped column period_month")

    if column_exists('assessment_events', 'period_year'):
        op.drop_column('assessment_events', 'period_year')
        print("✅ Dropped column period_year")

    if column_exists('assessment_events', 'coverage_month'):
        op.drop_column('assessment_events', 'coverage_month')
        print("✅ Dropped column coverage_month")

    if column_exists('assessment_events', 'coverage_year'):
        op.drop_column('assessment_events', 'coverage_year')
        print("✅ Dropped column coverage_year")

    print("Migration complete: Legacy bridge columns removed from assessment_events")


def downgrade():
    """Restore legacy bridge columns (rollback)."""

    # Re-add bridge columns (but NOT coverage_start_time/coverage_end_time — those were retained)
    if not column_exists('assessment_events', 'join_code'):
        op.add_column('assessment_events', sa.Column('join_code', sa.String(20), nullable=True))
        op.create_index('ix_assessment_events_join_code', 'assessment_events', ['join_code'])
        print("❌ Restored column join_code")

    if not column_exists('assessment_events', 'period'):
        op.add_column('assessment_events', sa.Column('period', sa.String(10), nullable=True))
        op.create_index('ix_assessment_events_period', 'assessment_events', ['period'])
        print("❌ Restored column period")

    if not column_exists('assessment_events', 'period_key'):
        op.add_column('assessment_events', sa.Column('period_key', sa.String(20), nullable=True))
        print("❌ Restored column period_key")

    if not column_exists('assessment_events', 'period_month'):
        op.add_column('assessment_events', sa.Column('period_month', sa.Integer(), nullable=True))
        print("❌ Restored column period_month")

    if not column_exists('assessment_events', 'period_year'):
        op.add_column('assessment_events', sa.Column('period_year', sa.Integer(), nullable=True))
        print("❌ Restored column period_year")

    if not column_exists('assessment_events', 'coverage_month'):
        op.add_column('assessment_events', sa.Column('coverage_month', sa.Integer(), nullable=True))
        print("❌ Restored column coverage_month")

    if not column_exists('assessment_events', 'coverage_year'):
        op.add_column('assessment_events', sa.Column('coverage_year', sa.Integer(), nullable=True))
        print("❌ Restored column coverage_year")
