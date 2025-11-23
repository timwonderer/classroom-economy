"""add insurance tiers and settings mode

Revision ID: c5d6e7f8g9h0
Revises: z1a2b3c4d5e6
Create Date: 2025-11-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8g9h0'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Add tier and settings mode columns to insurance_policies table
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tier_category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('tier_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('tier_color', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('settings_mode', sa.String(length=20), nullable=True, server_default='advanced'))


def downgrade():
    # Remove tier and settings mode columns
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.drop_column('settings_mode')
        batch_op.drop_column('tier_color')
        batch_op.drop_column('tier_name')
        batch_op.drop_column('tier_category_id')
