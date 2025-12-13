"""Add is_long_term_goal column to store_items

Revision ID: a7b8c9d0e1f2
Revises: beb004b
Create Date: 2025-12-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'beb004b'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_long_term_goal column to store_items table
    # This column allows teachers to mark items that shouldn't be validated against CWI
    # (e.g., expensive rewards students save for long-term)
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_long_term_goal', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove is_long_term_goal column from store_items table
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.drop_column('is_long_term_goal')
