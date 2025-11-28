"""Merge insurance feature heads

This merge migration consolidates two parallel insurance feature branches:
- b3c4d5e6f7g8: Add marketing badge to insurance
- c5d6e7f8g9h0: Add insurance tiers and settings mode

Revision ID: d6e7f8g9h0i1
Revises: b3c4d5e6f7g8, c5d6e7f8g9h0
Create Date: 2025-11-23 14:00:00.000000

"""


# revision identifiers, used by Alembic.
revision = 'd6e7f8g9h0i1'
down_revision = ('b3c4d5e6f7g8', 'c5d6e7f8g9h0')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no schema changes needed
    # Both parent migrations have already applied their respective changes
    pass


def downgrade():
    # This is a merge migration - no schema changes needed
    pass
