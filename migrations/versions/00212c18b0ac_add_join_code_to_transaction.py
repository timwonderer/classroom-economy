"""Add join_code to transaction table for period-level isolation

Revision ID: 00212c18b0ac
Revises: b6bc11a3a665
Create Date: 2025-11-29

CRITICAL: This migration enables proper isolation between different periods
taught by the same teacher. Each join_code represents a distinct class economy.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00212c18b0ac'
down_revision = 'b6bc11a3a665'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    """Add join_code column to transaction table."""

    # Add join_code column (nullable initially for backfill) - only if it doesn't exist
    if not column_exists('transaction', 'join_code'):
        op.add_column('transaction',
            sa.Column('join_code', sa.String(20), nullable=True)
        )
        print("✅ Added join_code column to transaction table")
    else:
        print("⚠️  Column 'join_code' already exists on 'transaction', skipping...")

    # Add index for performance - only if it doesn't exist
    if not index_exists('transaction', 'ix_transaction_join_code'):
        op.create_index(
            'ix_transaction_join_code',
            'transaction',
            ['join_code']
        )
        print("✅ Added index ix_transaction_join_code")
    else:
        print("⚠️  Index 'ix_transaction_join_code' already exists, skipping...")

    # Add composite index for common query pattern - only if it doesn't exist
    if not index_exists('transaction', 'ix_transaction_student_join_code'):
        op.create_index(
            'ix_transaction_student_join_code',
            'transaction',
            ['student_id', 'join_code']
        )
        print("✅ Added index ix_transaction_student_join_code")
    else:
        print("⚠️  Index 'ix_transaction_student_join_code' already exists, skipping...")

    print("⚠️  WARNING: Existing transactions may have NULL join_code")
    print("⚠️  Run backfill script to populate join_code for historical data")


def downgrade():
    """Remove join_code column from transaction table."""

    # Drop indexes first - only if they exist
    if index_exists('transaction', 'ix_transaction_student_join_code'):
        op.drop_index('ix_transaction_student_join_code', table_name='transaction')
        print("❌ Dropped index ix_transaction_student_join_code")
    else:
        print("⚠️  Index 'ix_transaction_student_join_code' does not exist, skipping...")

    if index_exists('transaction', 'ix_transaction_join_code'):
        op.drop_index('ix_transaction_join_code', table_name='transaction')
        print("❌ Dropped index ix_transaction_join_code")
    else:
        print("⚠️  Index 'ix_transaction_join_code' does not exist, skipping...")

    # Drop column - only if it exists
    if column_exists('transaction', 'join_code'):
        op.drop_column('transaction', 'join_code')
        print("❌ Removed join_code column from transaction table")
    else:
        print("⚠️  Column 'join_code' does not exist on 'transaction', skipping...")
