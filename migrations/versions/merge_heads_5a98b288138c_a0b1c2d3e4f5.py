"""Merge parallel obligation rewiring branches

Revision ID: merge_heads_5a98b288138c_a0b1c2d3e4f5
Revises: 5a98b288138c, a0b1c2d3e4f5
Create Date: 2026-07-25 12:00:00.000000

Consolidates two parallel migration branches that both descended from merge_heads_0008.
Both modifications are idempotent schema-only changes on separate tables (no data risk).

"""
from alembic import op


revision = 'merge_heads_5a98b288138c_a0b1c2d3e4f5'
down_revision = ('5a98b288138c', 'a0b1c2d3e4f5')
branch_labels = None
depends_on = None


def upgrade():
    # No-op merge: both branches modify separate tables independently
    pass


def downgrade():
    # No-op merge downgrade
    pass
