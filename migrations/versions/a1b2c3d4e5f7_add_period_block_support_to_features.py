"""Add period/block support to store items, insurance policies, and settings

Revision ID: a1b2c3d4e5f7
Revises: 02f217d8b08e
Create Date: 2025-11-28 12:00:00.000000

This migration adds period/block filtering support to enable teachers to:
1. Make store items visible only to specific periods/blocks
2. Make insurance policies available only to specific periods/blocks
3. Configure rent, banking, and hall pass settings per period/block

Changes:
- Create `store_item_blocks` association table for many-to-many relationship
- Create `insurance_policy_blocks` association table for many-to-many relationship
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
    # Create store_item_blocks association table
    op.create_table('store_item_blocks',
        sa.Column('store_item_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(['store_item_id'], ['store_items.id'], ),
        sa.PrimaryKeyConstraint('store_item_id', 'block')
    )
    op.create_index('ix_store_item_blocks_item', 'store_item_blocks', ['store_item_id'], unique=False)
    op.create_index('ix_store_item_blocks_block', 'store_item_blocks', ['block'], unique=False)

    # Create insurance_policy_blocks association table
    op.create_table('insurance_policy_blocks',
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['insurance_policies.id'], ),
        sa.PrimaryKeyConstraint('policy_id', 'block')
    )
    op.create_index('ix_insurance_policy_blocks_policy', 'insurance_policy_blocks', ['policy_id'], unique=False)
    op.create_index('ix_insurance_policy_blocks_block', 'insurance_policy_blocks', ['block'], unique=False)

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

    # Drop insurance_policy_blocks table
    op.drop_index('ix_insurance_policy_blocks_block', table_name='insurance_policy_blocks')
    op.drop_index('ix_insurance_policy_blocks_policy', table_name='insurance_policy_blocks')
    op.drop_table('insurance_policy_blocks')

    # Drop store_item_blocks table
    op.drop_index('ix_store_item_blocks_block', table_name='store_item_blocks')
    op.drop_index('ix_store_item_blocks_item', table_name='store_item_blocks')
    op.drop_table('store_item_blocks')
