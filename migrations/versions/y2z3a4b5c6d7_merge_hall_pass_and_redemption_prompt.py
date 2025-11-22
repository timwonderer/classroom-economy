"""Merge hall_pass_settings and redemption_prompt migrations

Revision ID: y2z3a4b5c6d7
Revises: h1p2s3t4u5v6, x1y2z3a4b5c6
Create Date: 2025-11-22 02:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y2z3a4b5c6d7'
down_revision = ('h1p2s3t4u5v6', 'x1y2z3a4b5c6')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no changes needed
    pass


def downgrade():
    # This is a merge migration - no changes needed
    pass
