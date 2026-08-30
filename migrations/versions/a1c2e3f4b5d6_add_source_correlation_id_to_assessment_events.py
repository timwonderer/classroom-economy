"""Add source_correlation_id to assessment_events

Adds a lawful lineage reference to obligation events. When an obligation ARISES
FROM another obligation — canonically, a LATE_FEE assessed against a delinquent
RENT — ``assessment_events.source_correlation_id`` points to the source
obligation's ``correlation_id``.

This replaces any string-parsing scheme for establishing lineage: the
relationship is now an explicit persisted reference, per the requirement that a
derived correlation string must never be parsed to infer a relationship.

The column is nullable (NULL for primary obligations) with no server default; no
backfill is required. A plain (non-unique) index supports lineage lookups
("all late fees arising from rent obligation X").

Revision ID: a1c2e3f4b5d6
Revises: e1f2a3b4c5d6
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2e3f4b5d6'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if table_exists('assessment_events') and not column_exists('assessment_events', 'source_correlation_id'):
        op.add_column('assessment_events', sa.Column('source_correlation_id', sa.String(length=200), nullable=True))
        print("✅ Added column assessment_events.source_correlation_id")
    else:
        print("⚠️  Column 'source_correlation_id' already exists on 'assessment_events' (or table missing), skipping...")

    if table_exists('assessment_events') and not index_exists('assessment_events', 'ix_assessment_events_source_correlation_id'):
        op.create_index('ix_assessment_events_source_correlation_id', 'assessment_events', ['source_correlation_id'])
        print("✅ Created index ix_assessment_events_source_correlation_id")
    else:
        print("⚠️  Index 'ix_assessment_events_source_correlation_id' already exists (or table missing), skipping...")


def downgrade():
    if index_exists('assessment_events', 'ix_assessment_events_source_correlation_id'):
        op.drop_index('ix_assessment_events_source_correlation_id', table_name='assessment_events')
        print("❌ Dropped index ix_assessment_events_source_correlation_id")
    else:
        print("⚠️  Index 'ix_assessment_events_source_correlation_id' does not exist, skipping...")

    if column_exists('assessment_events', 'source_correlation_id'):
        op.drop_column('assessment_events', 'source_correlation_id')
        print("❌ Dropped column assessment_events.source_correlation_id")
    else:
        print("⚠️  Column 'source_correlation_id' does not exist on 'assessment_events', skipping...")
