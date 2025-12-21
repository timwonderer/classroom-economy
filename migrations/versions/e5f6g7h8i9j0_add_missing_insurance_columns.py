"""Add missing insurance columns

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2025-11-17 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    # Add enable_repurchase_cooldown column to insurance_policies table
    # This enables temporary cooldown period after cancellation (separate from permanent block)
    op.add_column('insurance_policies',
        sa.Column('enable_repurchase_cooldown', sa.Boolean(), nullable=True))

    # Add bundle_discount_amount column to insurance_policies table
    # This provides a flat dollar amount discount for bundled policies
    op.add_column('insurance_policies',
        sa.Column('bundle_discount_amount', sa.Float(), nullable=True))

    # Set default values for existing records
    op.execute("UPDATE insurance_policies SET enable_repurchase_cooldown = FALSE WHERE enable_repurchase_cooldown IS NULL")
    op.execute("UPDATE insurance_policies SET bundle_discount_amount = 0 WHERE bundle_discount_amount IS NULL")

    # Make columns non-nullable after setting defaults
    op.alter_column('insurance_policies', 'enable_repurchase_cooldown', nullable=False)
    op.alter_column('insurance_policies', 'bundle_discount_amount', nullable=False)


def downgrade():
    # Remove the added columns
    op.drop_column('insurance_policies', 'bundle_discount_amount')
    op.drop_column('insurance_policies', 'enable_repurchase_cooldown')
