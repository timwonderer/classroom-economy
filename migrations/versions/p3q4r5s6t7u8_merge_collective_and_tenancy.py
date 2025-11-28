"""Merge collective goal and tenancy migrations

Revision ID: p3q4r5s6t7u8
Revises: o2p3q4r5s6t7, b73c4d92eadd
Create Date: 2025-11-20 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p3q4r5s6t7u8'
down_revision = ('o2p3q4r5s6t7', 'b73c4d92eadd')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no changes needed
    pass


def downgrade():
    # This is a merge migration - no changes needed
    pass
