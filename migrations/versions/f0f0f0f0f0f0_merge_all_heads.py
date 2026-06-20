"""Merge all migration heads

Revision ID: f0f0f0f0f0f0
Revises: 0a1b2c3d4e5f, a2b3c4d5e6f7, d1e2f3a4b5c6
Create Date: 2026-06-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f0f0f0f0f0f0'
down_revision = ('0a1b2c3d4e5f', 'a2b3c4d5e6f7', 'd1e2f3a4b5c6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
