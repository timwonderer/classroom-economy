"""Add bundle and bulk discount fields to store items

Revision ID: m0n1o2p3q4r5
Revises: l9m0n1o2p3q4
Create Date: 2025-11-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm0n1o2p3q4r5'
down_revision = 'l9m0n1o2p3q4'
branch_labels = None
depends_on = None


def upgrade():
    # Add bundle fields to store_items table
    op.add_column('store_items', sa.Column('is_bundle', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('store_items', sa.Column('bundle_quantity', sa.Integer(), nullable=True))

    # Add bulk discount fields to store_items table
    op.add_column('store_items', sa.Column('bulk_discount_enabled', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('store_items', sa.Column('bulk_discount_quantity', sa.Integer(), nullable=True))
    op.add_column('store_items', sa.Column('bulk_discount_percentage', sa.Float(), nullable=True))

    # Add bundle tracking fields to student_items table
    op.add_column('student_items', sa.Column('is_from_bundle', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('student_items', sa.Column('bundle_remaining', sa.Integer(), nullable=True))
    op.add_column('student_items', sa.Column('quantity_purchased', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    # Remove bundle and bulk discount fields from store_items table
    op.drop_column('store_items', 'is_bundle')
    op.drop_column('store_items', 'bundle_quantity')
    op.drop_column('store_items', 'bulk_discount_enabled')
    op.drop_column('store_items', 'bulk_discount_quantity')
    op.drop_column('store_items', 'bulk_discount_percentage')

    # Remove bundle tracking fields from student_items table
    op.drop_column('student_items', 'is_from_bundle')
    op.drop_column('student_items', 'bundle_remaining')
    op.drop_column('student_items', 'quantity_purchased')
