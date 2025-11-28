"""Add block association tables for store items and insurance policies

This migration implements proper many-to-many relationships for block visibility
instead of using comma-separated strings. This follows database best practices
(First Normal Form) and provides:
- Efficient queries: Can use indexed lookups instead of LIKE queries
- Data integrity: Block names are stored in separate rows
- Maintainability: No string parsing needed in application code

Revision ID: d1e2f3a4b5c6
Revises: f9fbd037a0f1
Create Date: 2025-11-28

Changes:
- Create store_item_blocks association table
- Create insurance_policy_blocks association table
- Add indexes for efficient querying by item/policy ID and block name

Note: The old blocks string columns in store_items and insurance_policies
tables remain but are no longer used. A future migration can drop them
after verifying the data migration is complete.

Limitations:
- This migration only updates the data structure and admin interface.
- Student-facing queries in app/routes/student.py (e.g., student shop and insurance marketplace)
  still need to be updated to use the new association tables for filtering by block visibility.
  Currently, all students can see all items/policies regardless of their block assignment.
- Application logic for block-based filtering will be updated in a future migration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'f9fbd037a0f1'
branch_labels = None
depends_on = None


def upgrade():
    # Create store_item_blocks association table
    op.create_table(
        'store_item_blocks',
        sa.Column('store_item_id', sa.Integer(), sa.ForeignKey('store_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('store_item_id', 'block')
    )
    op.create_index('ix_store_item_blocks_item', 'store_item_blocks', ['store_item_id'])
    op.create_index('ix_store_item_blocks_block', 'store_item_blocks', ['block'])

    # Create insurance_policy_blocks association table
    op.create_table(
        'insurance_policy_blocks',
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('insurance_policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('policy_id', 'block')
    )
    op.create_index('ix_insurance_policy_blocks_policy', 'insurance_policy_blocks', ['policy_id'])
    op.create_index('ix_insurance_policy_blocks_block', 'insurance_policy_blocks', ['block'])

    # Migrate existing data from comma-separated strings (if any exist)
    # Get connection for data migration
    connection = op.get_bind()

    # Migrate store_item blocks
    # Check if the blocks column exists in store_items
    try:
        result = connection.execute(sa.text(
            "SELECT id, blocks FROM store_items WHERE blocks IS NOT NULL AND blocks != ''"
        ))
        for row in result:
            item_id = row[0]
            blocks_str = row[1]
            if blocks_str:
                for block in blocks_str.split(','):
                    block = block.strip().upper()
                    if block:
                        # Check if entry already exists before inserting (database-agnostic)
                        exists = connection.execute(sa.text(
                            "SELECT 1 FROM store_item_blocks WHERE store_item_id = :item_id AND block = :block"
                        ), {'item_id': item_id, 'block': block}).fetchone()
                        if not exists:
                            connection.execute(sa.text(
                                "INSERT INTO store_item_blocks (store_item_id, block) VALUES (:item_id, :block)"
                            ), {'item_id': item_id, 'block': block})
    except Exception:
        # Column may not exist if this is a fresh database
        pass

    # Migrate insurance_policy blocks
    try:
        result = connection.execute(sa.text(
            "SELECT id, blocks FROM insurance_policies WHERE blocks IS NOT NULL AND blocks != ''"
        ))
        for row in result:
            policy_id = row[0]
            blocks_str = row[1]
            if blocks_str:
                for block in blocks_str.split(','):
                    block = block.strip().upper()
                    if block:
                        # Check if entry already exists before inserting (database-agnostic)
                        exists = connection.execute(sa.text(
                            "SELECT 1 FROM insurance_policy_blocks WHERE policy_id = :policy_id AND block = :block"
                        ), {'policy_id': policy_id, 'block': block}).fetchone()
                        if not exists:
                            connection.execute(sa.text(
                                "INSERT INTO insurance_policy_blocks (policy_id, block) VALUES (:policy_id, :block)"
                            ), {'policy_id': policy_id, 'block': block})
    except Exception:
        # Column may not exist if this is a fresh database
        pass


def downgrade():
    # Drop the association tables
    op.drop_index('ix_insurance_policy_blocks_block', table_name='insurance_policy_blocks')
    op.drop_index('ix_insurance_policy_blocks_policy', table_name='insurance_policy_blocks')
    op.drop_table('insurance_policy_blocks')

    op.drop_index('ix_store_item_blocks_block', table_name='store_item_blocks')
    op.drop_index('ix_store_item_blocks_item', table_name='store_item_blocks')
    op.drop_table('store_item_blocks')
