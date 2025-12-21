"""Add max_payout_per_period to insurance_policies

Revision ID: g1h2i3j4k5l6
Revises: d8e9f0a1b2c3
Create Date: 2025-11-23 02:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade():
    # Add max_payout_per_period column to insurance_policies table
    op.add_column('insurance_policies', sa.Column('max_payout_per_period', sa.Float(), nullable=True))


def downgrade():
    # Remove max_payout_per_period column from insurance_policies table
    op.drop_column('insurance_policies', 'max_payout_per_period')
