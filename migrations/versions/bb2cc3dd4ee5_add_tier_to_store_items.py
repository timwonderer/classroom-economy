"""Add tier field to store_items

Revision ID: bb2cc3dd4ee5
Revises: aa1bb2cc3dd4
Create Date: 2025-12-11 12:00:00.000000

This migration adds an optional tier field to store_items table.

The tier field allows teachers to categorize store items into
pricing tiers for better organization:
- basic: 2-5% of CWI
- standard: 5-10% of CWI
- premium: 10-25% of CWI
- luxury: 25-50% of CWI

This is a teacher-only organizational label that is not visible to students.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb2cc3dd4ee5'
down_revision = 'aa1bb2cc3dd4'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add tier column to store_items table
    if not column_exists('store_items', 'tier'):
        op.add_column('store_items', sa.Column('tier', sa.String(length=20), nullable=True))


def downgrade():
    # Remove tier column from store_items table
    if column_exists('store_items', 'tier'):
        op.drop_column('store_items', 'tier')
