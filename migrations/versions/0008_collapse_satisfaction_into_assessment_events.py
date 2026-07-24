"""Collapse obligation_satisfaction and obligation_reversal into assessment_events with event_type.

This migration aligns the schema with DOM-OBL-001 which defines a single assessment_events table
with event_type discriminator (ASSESSMENT | PAYMENT | WAIVED | REVERSED) rather than separate tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
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


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    # Add event_type column (default ASSESSMENT for existing rows)
    if not column_exists('assessment_events', 'event_type'):
        op.add_column('assessment_events',
                      sa.Column('event_type', sa.String(20), nullable=False, server_default='ASSESSMENT', index=True))
        print("✅ Added event_type column to assessment_events")
    else:
        print("⚠️  Column 'event_type' already exists on 'assessment_events', skipping...")

    # Add ledger_transaction_id (FK to ledger_transaction)
    if not column_exists('assessment_events', 'ledger_transaction_id'):
        op.add_column('assessment_events',
                      sa.Column('ledger_transaction_id', sa.Integer,
                               sa.ForeignKey('ledger_transaction.id', ondelete='SET NULL'),
                               nullable=True, index=True))
        print("✅ Added ledger_transaction_id column to assessment_events")
    else:
        print("⚠️  Column 'ledger_transaction_id' already exists on 'assessment_events', skipping...")

    # Add reason column (for REVERSED events)
    if not column_exists('assessment_events', 'reason'):
        op.add_column('assessment_events',
                      sa.Column('reason', sa.Text, nullable=True))
        print("✅ Added reason column to assessment_events")
    else:
        print("⚠️  Column 'reason' already exists on 'assessment_events', skipping...")

    # Add reversed_by_seat_id (FK to seats)
    if not column_exists('assessment_events', 'reversed_by_seat_id'):
        op.add_column('assessment_events',
                      sa.Column('reversed_by_seat_id', sa.Integer,
                               sa.ForeignKey('seats.id', ondelete='SET NULL'),
                               nullable=True, index=True))
        print("✅ Added reversed_by_seat_id column to assessment_events")
    else:
        print("⚠️  Column 'reversed_by_seat_id' already exists on 'assessment_events', skipping...")

    # Remove amount_snap column (no amounts stored in assessment_events per DOM-OBL-001)
    if column_exists('assessment_events', 'amount_snap'):
        op.drop_column('assessment_events', 'amount_snap')
        print("✅ Removed amount_snap column from assessment_events")
    else:
        print("⚠️  Column 'amount_snap' does not exist on 'assessment_events', skipping...")

    # Drop obligation_satisfaction table (data collapsed into assessment_events)
    if table_exists('obligation_satisfaction'):
        op.drop_table('obligation_satisfaction')
        print("✅ Dropped obligation_satisfaction table")
    else:
        print("⚠️  Table 'obligation_satisfaction' does not exist, skipping...")

    # Drop obligation_reversal table (data collapsed into assessment_events)
    if table_exists('obligation_reversal'):
        op.drop_table('obligation_reversal')
        print("✅ Dropped obligation_reversal table")
    else:
        print("⚠️  Table 'obligation_reversal' does not exist, skipping...")

    # Create index on event_type if not present (already added above but be safe)
    if not index_exists('assessment_events', 'ix_assessment_events_event_type'):
        op.create_index('ix_assessment_events_event_type', 'assessment_events', ['event_type'])
        print("✅ Created index on event_type")
    else:
        print("⚠️  Index 'ix_assessment_events_event_type' already exists, skipping...")


def downgrade():
    # Recreate obligation_reversal table
    if not table_exists('obligation_reversal'):
        op.create_table(
            'obligation_reversal',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assessment_id', sa.Integer(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('reversed_by_seat_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['assessment_id'], ['assessment_events.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['reversed_by_seat_id'], ['seats.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('assessment_id', name='uq_obligation_reversal_assessment'),
        )
        if not index_exists('obligation_reversal', 'ix_obligation_reversal_assessment_id'):
            op.create_index('ix_obligation_reversal_assessment_id', 'obligation_reversal', ['assessment_id'])
        print("✅ Recreated obligation_reversal table")
    else:
        print("⚠️  Table 'obligation_reversal' already exists, skipping...")

    # Recreate obligation_satisfaction table
    if not table_exists('obligation_satisfaction'):
        op.create_table(
            'obligation_satisfaction',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assessment_id', sa.Integer(), nullable=False),
            sa.Column('method', sa.String(20), nullable=False),
            sa.Column('ledger_transaction_id', sa.Integer(), nullable=True),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['assessment_id'], ['assessment_events.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['ledger_transaction_id'], ['ledger_transaction.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        if not index_exists('obligation_satisfaction', 'ix_obligation_satisfaction_assessment'):
            op.create_index('ix_obligation_satisfaction_assessment', 'obligation_satisfaction', ['assessment_id'])
        print("✅ Recreated obligation_satisfaction table")
    else:
        print("⚠️  Table 'obligation_satisfaction' already exists, skipping...")

    # Restore amount_snap column
    if not column_exists('assessment_events', 'amount_snap'):
        op.add_column('assessment_events',
                      sa.Column('amount_snap', sa.Numeric(precision=12, scale=2), nullable=True))
        print("✅ Restored amount_snap column to assessment_events")
    else:
        print("⚠️  Column 'amount_snap' already exists on 'assessment_events', skipping...")

    # Remove the new columns
    if column_exists('assessment_events', 'reversed_by_seat_id'):
        op.drop_column('assessment_events', 'reversed_by_seat_id')
        print("✅ Removed reversed_by_seat_id column from assessment_events")

    if column_exists('assessment_events', 'reason'):
        op.drop_column('assessment_events', 'reason')
        print("✅ Removed reason column from assessment_events")

    if column_exists('assessment_events', 'ledger_transaction_id'):
        op.drop_column('assessment_events', 'ledger_transaction_id')
        print("✅ Removed ledger_transaction_id column from assessment_events")

    if column_exists('assessment_events', 'event_type'):
        op.drop_column('assessment_events', 'event_type')
        print("✅ Removed event_type column from assessment_events")
