"""Store domain canonical schema — create store_purchases, redemption_events, store_item_visibility

Creates the canonical v2 store tables per DOM-CORE-002 and DOM-STORE-001 v2.0:
- store_purchases (replaces student_items for purchase tracking)
- redemption_events (replaces redemption_audit_logs for redemption history)
- store_item_visibility (replaces store_item_blocks for per-seat visibility)

Legacy tables (student_items, store_item_blocks, redemption_audit_logs) are NOT
dropped in this migration. They remain as read-only shadows until all route-level
callers are migrated to the canonical service layer. Physical drop is a follow-up.

Revision ID: 0009a1b2c3d4
Revises: 0008a1b2c3d4
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa


revision = '0009a1b2c3d4'
down_revision = '0008a1b2c3d4'
branch_labels = None
depends_on = None


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
    if not table_exists('store_purchases'):
        op.create_table(
            'store_purchases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=False),
            sa.Column('store_item_id', sa.Integer(), sa.ForeignKey('store_items.id'), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('price_at_purchase', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('total_price', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='purchased'),
            sa.Column('idempotency_key', sa.String(100), nullable=True),
            sa.Column('ledger_tx_id', sa.Integer(), sa.ForeignKey('ledger_transaction.id'), nullable=True),
            sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_from_bundle', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('bundle_remaining', sa.Integer(), nullable=True),
            sa.Column('uses_remaining', sa.Integer(), nullable=True),
            sa.Column('collective_goal_instance_code', sa.String(36), nullable=True),
        )
        print("✅ Created store_purchases table")
    else:
        print("⚠️  store_purchases already exists, skipping")

    if not table_exists('redemption_events'):
        op.create_table(
            'redemption_events',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('purchase_id', sa.Integer(), sa.ForeignKey('store_purchases.id', ondelete='CASCADE'), nullable=False),
            sa.Column('seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='SET NULL'), nullable=True),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True),
            sa.Column('action', sa.Enum('request', 'approved', 'rejected', name='redemption_event_action_enum'), nullable=False),
            sa.Column('source', sa.Enum('live', name='redemption_event_source_enum'), nullable=False, server_default='live'),
            sa.Column('initiated_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('seat_display_name', sa.String(120), nullable=False),
            sa.Column('class_display_label', sa.String(120), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        print("✅ Created redemption_events table")
    else:
        print("⚠️  redemption_events already exists, skipping")

    if not table_exists('store_item_visibility'):
        op.create_table(
            'store_item_visibility',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('store_item_id', sa.Integer(), sa.ForeignKey('store_items.id', ondelete='CASCADE'), nullable=False),
            sa.Column('seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='CASCADE'), nullable=False),
            sa.UniqueConstraint('store_item_id', 'seat_id', name='uq_store_item_visibility_item_seat'),
        )
        print("✅ Created store_item_visibility table")
    else:
        print("⚠️  store_item_visibility already exists, skipping")

    # Indexes for store_purchases
    if table_exists('store_purchases'):
        if not index_exists('store_purchases', 'ix_store_purchases_seat_id'):
            op.create_index('ix_store_purchases_seat_id', 'store_purchases', ['seat_id'])
        if not index_exists('store_purchases', 'ix_store_purchases_class_id'):
            op.create_index('ix_store_purchases_class_id', 'store_purchases', ['class_id'])
        if not index_exists('store_purchases', 'ix_store_purchases_store_item_id'):
            op.create_index('ix_store_purchases_store_item_id', 'store_purchases', ['store_item_id'])
        if not index_exists('store_purchases', 'ix_store_purchases_idempotency_key'):
            op.create_index('ix_store_purchases_idempotency_key', 'store_purchases', ['idempotency_key'], unique=True)
        if not index_exists('store_purchases', 'ix_store_purchases_ledger_tx_id'):
            op.create_index('ix_store_purchases_ledger_tx_id', 'store_purchases', ['ledger_tx_id'])
        if not index_exists('store_purchases', 'ix_store_purchases_seat_class'):
            op.create_index('ix_store_purchases_seat_class', 'store_purchases', ['seat_id', 'class_id'])
        if not index_exists('store_purchases', 'ix_store_purchases_collective_goal'):
            op.create_index('ix_store_purchases_collective_goal', 'store_purchases', ['collective_goal_instance_code'])

    # Indexes for redemption_events
    if table_exists('redemption_events'):
        if not index_exists('redemption_events', 'ix_redemption_events_purchase_id'):
            op.create_index('ix_redemption_events_purchase_id', 'redemption_events', ['purchase_id'])
        if not index_exists('redemption_events', 'ix_redemption_events_seat_id'):
            op.create_index('ix_redemption_events_seat_id', 'redemption_events', ['seat_id'])
        if not index_exists('redemption_events', 'ix_redemption_events_class_id'):
            op.create_index('ix_redemption_events_class_id', 'redemption_events', ['class_id'])
        if not index_exists('redemption_events', 'ix_redemption_events_action'):
            op.create_index('ix_redemption_events_action', 'redemption_events', ['action'])
        if not index_exists('redemption_events', 'ix_redemption_events_initiated_by_timestamp'):
            op.create_index('ix_redemption_events_initiated_by_timestamp', 'redemption_events', ['initiated_by_user_id', 'timestamp'])

    # Indexes for store_item_visibility
    if table_exists('store_item_visibility'):
        if not index_exists('store_item_visibility', 'ix_store_item_visibility_store_item_id'):
            op.create_index('ix_store_item_visibility_store_item_id', 'store_item_visibility', ['store_item_id'])
        if not index_exists('store_item_visibility', 'ix_store_item_visibility_seat_id'):
            op.create_index('ix_store_item_visibility_seat_id', 'store_item_visibility', ['seat_id'])


def downgrade():
    if table_exists('store_item_visibility'):
        op.drop_table('store_item_visibility')
        print("❌ Dropped store_item_visibility table")

    if table_exists('redemption_events'):
        op.drop_table('redemption_events')
        print("❌ Dropped redemption_events table")

    if table_exists('store_purchases'):
        op.drop_table('store_purchases')
        print("❌ Dropped store_purchases table")

    # Clean up enum types
    op.execute("DROP TYPE IF EXISTS redemption_event_action_enum")
    op.execute("DROP TYPE IF EXISTS redemption_event_source_enum")
