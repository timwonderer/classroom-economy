"""Add dob_sum column to admins table for account recovery

Revision ID: cc3dd4ee5ff6
Revises: bb2cc3dd4ee5
Create Date: 2025-12-12

This migration adds a dob_sum field to the admins table to enable
teacher account recovery. The DOB sum is calculated as MM + DD + YYYY
(similar to the student system) and allows teachers to recover their
account by providing student usernames from each class they teach
plus their DOB sum.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc3dd4ee5ff6'
down_revision = 'bb2cc3dd4ee5'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add dob_sum column to admins table (nullable for existing accounts)
    if not column_exists('admins', 'dob_sum'):
        op.add_column('admins', sa.Column('dob_sum', sa.Integer(), nullable=True))


def downgrade():
    # Remove dob_sum column from admins table
    if column_exists('admins', 'dob_sum'):
        op.drop_column('admins', 'dob_sum')
