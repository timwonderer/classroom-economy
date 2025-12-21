"""add_partial_progress_to_recovery_requests

Revision ID: b484581f2fc9
Revises: dd4ee5ff6aa7
Create Date: 2025-12-12 03:21:41.515605

Adds partial progress support to allow teachers to save recovery codes
and resume later with a temporary PIN.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b484581f2fc9'
down_revision = 'dd4ee5ff6aa7'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add partial progress fields to recovery_requests table
    if not column_exists('recovery_requests', 'partial_codes'):
        op.add_column('recovery_requests', sa.Column('partial_codes', sa.JSON(), nullable=True))

    if not column_exists('recovery_requests', 'resume_pin_hash'):
        op.add_column('recovery_requests', sa.Column('resume_pin_hash', sa.String(length=64), nullable=True))

    if not column_exists('recovery_requests', 'resume_new_username'):
        op.add_column('recovery_requests', sa.Column('resume_new_username', sa.String(length=100), nullable=True))


def downgrade():
    # Remove partial progress fields
    if column_exists('recovery_requests', 'resume_new_username'):
        op.drop_column('recovery_requests', 'resume_new_username')

    if column_exists('recovery_requests', 'resume_pin_hash'):
        op.drop_column('recovery_requests', 'resume_pin_hash')

    if column_exists('recovery_requests', 'partial_codes'):
        op.drop_column('recovery_requests', 'partial_codes')
