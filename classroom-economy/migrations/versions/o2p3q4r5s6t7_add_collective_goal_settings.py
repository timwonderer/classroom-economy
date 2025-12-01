"""Add collective goal settings to store items

Revision ID: o2p3q4r5s6t7
Revises: n1o2p3q4r5s6
Create Date: 2025-11-20 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o2p3q4r5s6t7'
down_revision = 'n1o2p3q4r5s6'
branch_labels = None
depends_on = None


def upgrade():
    # Add collective goal fields to store_items table
    op.add_column('store_items', sa.Column('collective_goal_type', sa.String(20), nullable=True))  # 'fixed' or 'whole_class'
    op.add_column('store_items', sa.Column('collective_goal_target', sa.Integer(), nullable=True))  # Fixed number of purchases needed


def downgrade():
    # Remove collective goal fields from store_items table
    op.drop_column('store_items', 'collective_goal_type')
    op.drop_column('store_items', 'collective_goal_target')
