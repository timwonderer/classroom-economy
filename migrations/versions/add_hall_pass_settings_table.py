"""Add hall_pass_settings table

Revision ID: h1p2s3t4u5v6
Revises: c5f3a8d9e1b4
Create Date: 2025-11-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h1p2s3t4u5v6'
down_revision = 'c5f3a8d9e1b4'
branch_labels = None
depends_on = None


def upgrade():
    # Create hall_pass_settings table
    op.create_table(
        'hall_pass_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('queue_limit', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('hall_pass_settings')
