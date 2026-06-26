"""Merge migration heads.

Revision ID: 9c8b7a6d5e4f
Revises: a9b8c7d6e5f4, f1f1f1f1f1f1
Create Date: 2026-06-20 00:00:02.000000
"""

from alembic import op


revision = '9c8b7a6d5e4f'
down_revision = ('a9b8c7d6e5f4', 'f1f1f1f1f1f1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
