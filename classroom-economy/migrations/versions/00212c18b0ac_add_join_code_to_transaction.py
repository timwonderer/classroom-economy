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


def upgrade():
    """Add join_code column to transaction table."""

    # Add join_code column (nullable initially for backfill)
    op.add_column('transaction',
        sa.Column('join_code', sa.String(20), nullable=True)
    )

    # Add index for performance
    op.create_index(
        'ix_transaction_join_code',
        'transaction',
        ['join_code']
    )

    # Add composite index for common query pattern
    op.create_index(
        'ix_transaction_student_join_code',
        'transaction',
        ['student_id', 'join_code']
    )

    print("✅ Added join_code column to transaction table")
    print("⚠️  WARNING: Existing transactions have NULL join_code")
    print("⚠️  Run backfill script to populate join_code for historical data")


def downgrade():
    """Remove join_code column from transaction table."""

    # Drop indexes first
    op.drop_index('ix_transaction_student_join_code', table_name='transaction')
    op.drop_index('ix_transaction_join_code', table_name='transaction')

    # Drop column
    op.drop_column('transaction', 'join_code')

    print("❌ Removed join_code column from transaction table")
