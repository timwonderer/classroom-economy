"""Rebuild Store/Entitlements schema to canonical event-based model.

Phase 2 Migration: Complete schema replacement per DOM-STORE-001 v3.0
- Delete forbidden tables: store_purchases, redemption_events, entitlements, entitlement_consumptions, old entitlement_events
- Create new canonical tables: entitlement_events (event-based), pending_actions (pending workflow)

Revision ID: 4aa06b69d65d
Revises: b3e8c7f9a1d2
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4aa06b69d65d'
down_revision = 'b3e8c7f9a1d2'
branch_labels = None
depends_on = None


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


def upgrade():
    """Delete old tables and create new canonical schema."""

    # =====================================================================
    # Phase 1: Drop forbidden old tables
    # =====================================================================

    # Drop old redemption_events table (forbidden per DOM-STORE-001 §VI)
    if table_exists('redemption_events'):
        op.drop_table('redemption_events', if_exists=True)
        print("✅ Dropped redemption_events table")

    # Drop old store_purchases table (forbidden per DOM-STORE-001 §VI)
    if table_exists('store_purchases'):
        op.drop_table('store_purchases', if_exists=True)
        print("✅ Dropped store_purchases table")

    # Drop old entitlement_consumptions table (replaced by event_type in new model)
    if table_exists('entitlement_consumptions'):
        op.drop_table('entitlement_consumptions', if_exists=True)
        print("✅ Dropped entitlement_consumptions table")

    # Drop old insurance_claims table (replaced by pending_actions + event_type=CONSUMED)
    if table_exists('insurance_claims'):
        op.drop_table('insurance_claims', if_exists=True)
        print("✅ Dropped insurance_claims table")

    # Drop old entitlements table (replaced by new event-based model)
    if table_exists('entitlements'):
        op.drop_table('entitlements', if_exists=True)
        print("✅ Dropped entitlements table")

    # Drop old entitlement_events table (used mutable quantity_delta, forbidden per §IV)
    if table_exists('entitlement_events'):
        op.drop_table('entitlement_events', if_exists=True)
        print("✅ Dropped old entitlement_events table (mutable hall-pass model)")

    # =====================================================================
    # Phase 2: Create new canonical tables
    # =====================================================================

    # Create new entitlement_events table (event-based immutable history)
    if not table_exists('entitlement_events'):
        op.create_table(
            'entitlement_events',
            sa.Column('event_id', sa.String(36), primary_key=True, default=sa.text("gen_random_uuid()::text")),
            sa.Column('class_id', sa.String(36), nullable=False, index=True),
            sa.Column('entitlement_id', sa.String(36), nullable=False, index=True),
            sa.Column('target_seat_id', sa.Integer, nullable=False, index=True),
            sa.Column('actor_seat_id', sa.Integer, nullable=False),
            sa.Column('product_id', sa.Integer, nullable=True),
            sa.Column('entitlement_type', sa.String(50), nullable=False),
            sa.Column('acquisition_type', sa.String(20), nullable=False),
            sa.Column('event_type', sa.String(20), nullable=False, index=True),
            sa.Column('correlation_id', sa.String(200), nullable=True, index=True),
            sa.Column('payload', sa.JSON, nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

        # Add foreign keys for class_id and seats
        op.create_foreign_key(
            'fk_entitlement_events_class_id',
            'entitlement_events', 'classes',
            ['class_id'], ['class_id'],
            ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_entitlement_events_target_seat_id',
            'entitlement_events', 'seats',
            ['target_seat_id'], ['id'],
            ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_entitlement_events_actor_seat_id',
            'entitlement_events', 'seats',
            ['actor_seat_id'], ['id'],
            ondelete='CASCADE'
        )

        # Create indexes
        op.create_index(
            'ix_entitlement_events_entitlement_id_class',
            'entitlement_events',
            ['entitlement_id', 'class_id']
        )
        op.create_index(
            'ix_entitlement_events_seat_class',
            'entitlement_events',
            ['target_seat_id', 'class_id']
        )

        print("✅ Created entitlement_events table (event-based canonical)")

    # Create pending_actions table (for unresolved entitlement actions)
    if not table_exists('pending_actions'):
        op.create_table(
            'pending_actions',
            sa.Column('pending_action_id', sa.String(36), primary_key=True, default=sa.text("gen_random_uuid()::text")),
            sa.Column('class_id', sa.String(36), nullable=False, index=True),
            sa.Column('seat_id', sa.Integer, nullable=False, index=True),
            sa.Column('entitlement_id', sa.String(36), nullable=False, index=True),
            sa.Column('correlation_id', sa.String(200), nullable=False, unique=True, index=True),
            sa.Column('authoritative_feat', sa.String(100), nullable=False, index=True),
            sa.Column('payload', sa.JSON, nullable=False),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

        # Add foreign keys
        op.create_foreign_key(
            'fk_pending_actions_class_id',
            'pending_actions', 'classes',
            ['class_id'], ['class_id'],
            ondelete='CASCADE'
        )
        op.create_foreign_key(
            'fk_pending_actions_seat_id',
            'pending_actions', 'seats',
            ['seat_id'], ['id'],
            ondelete='CASCADE'
        )

        print("✅ Created pending_actions table (for unresolved actions)")

    print("✅ Phase 2 Migration Complete: Store/Entitlements schema rebuilt to event-based canonical model")


def downgrade():
    """Downgrade: Drop new tables (restoration requires separate data migration)."""

    # Drop new tables
    if table_exists('pending_actions'):
        op.drop_table('pending_actions', if_exists=True)
        print("❌ Dropped pending_actions table")

    if table_exists('entitlement_events'):
        op.drop_table('entitlement_events', if_exists=True)
        print("❌ Dropped entitlement_events table")

    print("⚠️  Downgrade complete. Old tables (store_purchases, redemption_events, etc.) were deleted and cannot be automatically restored.")
    print("    If rollback is required, restore from database backup.")
