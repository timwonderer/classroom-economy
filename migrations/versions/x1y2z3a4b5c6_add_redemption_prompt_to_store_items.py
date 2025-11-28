"""Add redemption_prompt column to store_items

Revision ID: x1y2z3a4b5c6
Revises: r5s6t7u8v9w0
Create Date: 2025-11-22 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x1y2z3a4b5c6'
down_revision = 'r5s6t7u8v9w0'
branch_labels = None
depends_on = None


def upgrade():
    # Add redemption_prompt column to store_items table
    op.add_column('store_items', sa.Column('redemption_prompt', sa.Text(), nullable=True))


def downgrade():
    # Remove redemption_prompt column from store_items table
    op.drop_column('store_items', 'redemption_prompt')
