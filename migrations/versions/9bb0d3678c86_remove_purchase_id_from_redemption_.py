"""Remove purchase_id from redemption_events make entitlement_id non-nullable

Revision ID: 9bb0d3678c86
Revises: 0006
Create Date: 2026-07-24 02:49:46.185761

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
revision = '9bb0d3678c86'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Make entitlement_id non-nullable (must have data backfilled first).
    #    Any redemption_events rows with NULL entitlement_id are orphaned legacy
    #    data — delete them before applying the constraint.
    if column_exists('redemption_events', 'entitlement_id'):
        op.execute(
            "DELETE FROM redemption_events WHERE entitlement_id IS NULL"
        )
        op.alter_column(
            'redemption_events', 'entitlement_id',
            existing_type=sa.VARCHAR(length=36),
            nullable=False,
        )
        print("✅ Made redemption_events.entitlement_id non-nullable")
    else:
        print("⚠️  Column entitlement_id does not exist on redemption_events, skipping")

    # 2. Drop purchase_id FK constraint, index, and column.
    if column_exists('redemption_events', 'purchase_id'):
        # Drop FK dynamically
        for fk in get_foreign_keys_by_column('redemption_events', 'purchase_id'):
            if fk['name']:
                op.drop_constraint(fk['name'], 'redemption_events', type_='foreignkey')
                print(f"✅ Dropped FK constraint {fk['name']}")

        # Drop index if present
        if index_exists('redemption_events', 'ix_redemption_events_purchase_id'):
            op.drop_index('ix_redemption_events_purchase_id', table_name='redemption_events')
            print("✅ Dropped index ix_redemption_events_purchase_id")

        op.drop_column('redemption_events', 'purchase_id')
        print("✅ Dropped column redemption_events.purchase_id")
    else:
        print("⚠️  Column purchase_id does not exist on redemption_events, skipping")


def downgrade():
    # Re-add purchase_id as nullable (data cannot be restored)
    if not column_exists('redemption_events', 'purchase_id'):
        op.add_column(
            'redemption_events',
            sa.Column('purchase_id', sa.INTEGER(), nullable=True),
        )
        op.create_index(
            'ix_redemption_events_purchase_id',
            'redemption_events',
            ['purchase_id'],
        )
        op.create_foreign_key(
            'redemption_events_purchase_id_fkey',
            'redemption_events', 'store_purchases',
            ['purchase_id'], ['id'],
            ondelete='CASCADE',
        )
        print("✅ Re-added redemption_events.purchase_id (nullable — data lost)")

    # Make entitlement_id nullable again
    if column_exists('redemption_events', 'entitlement_id'):
        op.alter_column(
            'redemption_events', 'entitlement_id',
            existing_type=sa.VARCHAR(length=36),
            nullable=True,
        )
        print("✅ Made redemption_events.entitlement_id nullable again")
