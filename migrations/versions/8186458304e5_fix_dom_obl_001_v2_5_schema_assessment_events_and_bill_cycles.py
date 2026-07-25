"""Fix: DOM-OBL-001 v2.5 schema compliance for assessment_events and bill_cycles

Per DOM-OBL-001 Section VII, the canonical schema for:
- assessment_events: timestamp (NOT created_at/assessed_at/viewable_at/due_at)
- bill_cycles: NO created_at (use assessment_event timestamp as reference)

Revision ID: 8186458304e5
Revises: 8a7b6c5d4e3f
Create Date: 2026-07-25 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime, timezone

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

# ============================================================================
# MIGRATION
# ============================================================================

revision = '8186458304e5'
down_revision = '8a7b6c5d4e3f'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrate assessment_events and bill_cycles to DOM-OBL-001 v2.5 canonical schema.
    """

    # ========================================================================
    # PHASE 1: assessment_events table corrections
    # ========================================================================

    if table_exists('assessment_events'):
        # Step 1: Add new 'timestamp' column (consolidates created_at + assessed_at)
        # Use COALESCE to prefer created_at if it exists, otherwise assessed_at
        if not column_exists('assessment_events', 'timestamp'):
            op.add_column(
                'assessment_events',
                sa.Column(
                    'timestamp',
                    sa.DateTime(timezone=True),
                    nullable=True,  # Temporary, will be made NOT NULL after backfill
                    server_default=sa.func.now()
                )
            )
            print("✅ Added 'timestamp' column to assessment_events")
        else:
            print("⚠️  Column 'timestamp' already exists on 'assessment_events', skipping...")

        # Step 2: Backfill timestamp from created_at or assessed_at
        if column_exists('assessment_events', 'created_at') and column_exists('assessment_events', 'timestamp'):
            op.execute("""
                UPDATE assessment_events
                SET timestamp = COALESCE(created_at, assessed_at, NOW())
                WHERE timestamp IS NULL
            """)
            print("✅ Backfilled 'timestamp' from created_at/assessed_at")

        # Step 3: Make timestamp NOT NULL
        op.alter_column('assessment_events', 'timestamp', nullable=False)
        print("✅ Made 'timestamp' NOT NULL")

        # Step 4: Remove obsolete columns (per DOM-OBL-001 v2.5)
        if column_exists('assessment_events', 'due_at'):
            op.drop_column('assessment_events', 'due_at')
            print("❌ Dropped 'due_at' column (belongs on bill_cycles)")

        if column_exists('assessment_events', 'viewable_at'):
            op.drop_column('assessment_events', 'viewable_at')
            print("❌ Dropped 'viewable_at' column (belongs on Class Configuration)")

        if column_exists('assessment_events', 'assessed_at'):
            op.drop_column('assessment_events', 'assessed_at')
            print("❌ Dropped 'assessed_at' column (covered by 'timestamp')")

        if column_exists('assessment_events', 'created_at'):
            op.drop_column('assessment_events', 'created_at')
            print("❌ Dropped 'created_at' column (covered by 'timestamp')")

    # ========================================================================
    # PHASE 2: bill_cycles table corrections
    # ========================================================================

    if table_exists('bill_cycles'):
        # Step 1: Remove created_at (timestamp on assessment_event serves as reference)
        if column_exists('bill_cycles', 'created_at'):
            op.drop_column('bill_cycles', 'created_at')
            print("❌ Dropped 'created_at' column from bill_cycles (use assessment_event.timestamp as reference)")
        else:
            print("⚠️  Column 'created_at' does not exist on 'bill_cycles', skipping...")


def downgrade():
    """
    Restore pre-v2.5 schema (for rollback).
    """

    # ========================================================================
    # PHASE 1: Restore assessment_events columns
    # ========================================================================

    if table_exists('assessment_events'):
        # Restore created_at from timestamp
        if not column_exists('assessment_events', 'created_at'):
            op.add_column(
                'assessment_events',
                sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            )
            op.execute("UPDATE assessment_events SET created_at = timestamp WHERE created_at IS NULL")
            print("↩️  Restored 'created_at' column")

        # Restore assessed_at from timestamp
        if not column_exists('assessment_events', 'assessed_at'):
            op.add_column(
                'assessment_events',
                sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            )
            op.execute("UPDATE assessment_events SET assessed_at = timestamp WHERE assessed_at IS NULL")
            print("↩️  Restored 'assessed_at' column")

        # Restore viewable_at as NULL (no historical data)
        if not column_exists('assessment_events', 'viewable_at'):
            op.add_column(
                'assessment_events',
                sa.Column('viewable_at', sa.DateTime(timezone=True), nullable=True)
            )
            print("↩️  Restored 'viewable_at' column")

        # Restore due_at as NULL (no historical data)
        if not column_exists('assessment_events', 'due_at'):
            op.add_column(
                'assessment_events',
                sa.Column('due_at', sa.DateTime(timezone=True), nullable=True)
            )
            print("↩️  Restored 'due_at' column")

        # Remove timestamp
        if column_exists('assessment_events', 'timestamp'):
            op.drop_column('assessment_events', 'timestamp')
            print("↩️  Removed 'timestamp' column")

    # ========================================================================
    # PHASE 2: Restore bill_cycles columns
    # ========================================================================

    if table_exists('bill_cycles'):
        # Restore created_at
        if not column_exists('bill_cycles', 'created_at'):
            op.add_column(
                'bill_cycles',
                sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            )
            print("↩️  Restored 'created_at' column to bill_cycles")
