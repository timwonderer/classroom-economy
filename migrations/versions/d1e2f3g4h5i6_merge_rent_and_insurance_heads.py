"""Merge rent and insurance migration heads

Revision ID: d1e2f3g4h5i6
Revises: a1b2c3d4e5f6, cf7a5cda2d0a
Create Date: 2025-12-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3g4h5i6'
down_revision = ('a1b2c3d4e5f6', 'cf7a5cda2d0a')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no schema changes needed
    pass


def downgrade():
    # This is a merge migration - no schema changes needed
    pass
