"""Add has_assigned_students column to admins table

Revision ID: c5f3a8d9e1b4
Revises: p3q4r5s6t7u8
Create Date: 2025-11-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5f3a8d9e1b4'
down_revision = 'p3q4r5s6t7u8'
branch_labels = None
depends_on = None


def upgrade():
    # Add has_assigned_students column with default False
    op.add_column('admins', sa.Column('has_assigned_students', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('admins', 'has_assigned_students')
