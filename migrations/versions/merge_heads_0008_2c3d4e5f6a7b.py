"""Merge migration to consolidate parallel migration branches

Revision ID: merge_heads_0008_2c3d4e5f6a7b
Revises: 0008, 2c3d4e5f6a7b
Create Date: 2026-07-24

This merge migration consolidates two parallel migration branches that developed
during concurrent work. Since there's no schema data to protect, this is a no-op.

"""
from alembic import op


revision = 'merge_heads_0008_2c3d4e5f6a7b'
down_revision = ('0008', '2c3d4e5f6a7b')
branch_labels = None
depends_on = None


def upgrade():
    # No-op merge: both branches independently modify separate tables
    pass


def downgrade():
    # No-op merge downgrade
    pass
