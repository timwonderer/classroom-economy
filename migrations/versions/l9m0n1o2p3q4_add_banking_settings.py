"""Add BankingSettings model for interest and overdraft features

Revision ID: l9m0n1o2p3q4
Revises: k8l9m0n1o2p3
Create Date: 2025-11-19 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l9m0n1o2p3q4'
down_revision = 'k8l9m0n1o2p3'
branch_labels = None
depends_on = None


def upgrade():
    # Create banking_settings table
    op.create_table('banking_settings',
        sa.Column('id', sa.Integer(), nullable=False),

        # Interest settings for savings
        sa.Column('savings_apy', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('savings_monthly_rate', sa.Float(), nullable=True, server_default='0.0'),

        # Interest payout schedule
        sa.Column('interest_schedule_type', sa.String(20), nullable=True, server_default='monthly'),
        sa.Column('interest_schedule_cycle_days', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('interest_payout_start_date', sa.DateTime(), nullable=True),

        # Overdraft protection
        sa.Column('overdraft_protection_enabled', sa.Boolean(), nullable=True, server_default='0'),

        # Overdraft/NSF fees
        sa.Column('overdraft_fee_enabled', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('overdraft_fee_type', sa.String(20), nullable=True, server_default='flat'),
        sa.Column('overdraft_fee_flat_amount', sa.Float(), nullable=True, server_default='0.0'),

        # Progressive fee settings
        sa.Column('overdraft_fee_progressive_1', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('overdraft_fee_progressive_2', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('overdraft_fee_progressive_3', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('overdraft_fee_progressive_cap', sa.Float(), nullable=True),

        # Metadata
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop banking_settings table
    op.drop_table('banking_settings')
