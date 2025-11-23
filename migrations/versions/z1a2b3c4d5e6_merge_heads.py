"""Merge multi-tenancy and other branches

Revision ID: z1a2b3c4d5e6
Revises: f2g3h4i5j6k7, y2z3a4b5c6d7
Create Date: 2025-11-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z1a2b3c4d5e6'
down_revision = ('f2g3h4i5j6k7', 'y2z3a4b5c6d7')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no schema changes needed
    pass


def downgrade():
    # This is a merge migration - no schema changes needed
    pass
