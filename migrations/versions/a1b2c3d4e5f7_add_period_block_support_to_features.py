"""Add period/block support to store items, insurance policies, and settings

Revision ID: a1b2c3d4e5f7
Revises: 02f217d8b08e
Create Date: 2025-11-28 12:00:00.000000

This migration adds period/block filtering support to enable teachers to:
1. Make store items visible only to specific periods/blocks
2. Make insurance policies available only to specific periods/blocks
3. Configure rent, banking, and hall pass settings per period/block

Changes:
- Add `blocks` column (String 255, nullable) to store_items table
  (comma-separated list like "A,B,C" or NULL for all periods)
- Add `blocks` column (String 255, nullable) to insurance_policies table
  (comma-separated list like "A,B,C" or NULL for all periods)
- Add `block` column (String 10, nullable) to rent_settings table
  (NULL = global default, otherwise period/block identifier)
- Add `block` column (String 10, nullable) to banking_settings table
  (NULL = global default, otherwise period/block identifier)
- Add `block` column (String 10, nullable) to hall_pass_settings table
  (NULL = global default, otherwise period/block identifier)

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '02f217d8b08e'
branch_labels = None
depends_on = None


def upgrade():
    # Add blocks column to store_items (for visibility filtering)
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('blocks', sa.String(length=255), nullable=True))

    # Add blocks column to insurance_policies (for visibility filtering)
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('blocks', sa.String(length=255), nullable=True))

    # Add block column to rent_settings (for period-specific settings)
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('block', sa.String(length=10), nullable=True))

    # Add block column to banking_settings (for period-specific settings)
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('block', sa.String(length=10), nullable=True))

    # Add block column to hall_pass_settings (for period-specific settings)
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('block', sa.String(length=10), nullable=True))


def downgrade():
    # Remove block column from hall_pass_settings
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.drop_column('block')

    # Remove block column from banking_settings
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.drop_column('block')

    # Remove block column from rent_settings
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.drop_column('block')

    # Remove blocks column from insurance_policies
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.drop_column('blocks')

    # Remove blocks column from store_items
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.drop_column('blocks')
