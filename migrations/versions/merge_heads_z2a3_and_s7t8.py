"""Merge migration heads: z2a3b4c5d6e7 and s7t8u9v0w1x2

Revision ID: merge_heads_001
Revises: z2a3b4c5d6e7, s7t8u9v0w1x2
Create Date: 2025-12-10 08:00:00.000000

This merge migration combines two parallel migration heads:
1. z2a3b4c5d6e7 - Add FeatureSettings and TeacherOnboarding models
2. s7t8u9v0w1x2 - Add expected_weekly_hours to PayrollSettings

No schema changes are made in this migration - it simply merges the branches.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_heads_001'
down_revision = ('z2a3b4c5d6e7', 's7t8u9v0w1x2')
branch_labels = None
depends_on = None


def upgrade():
    # No schema changes needed for merge migration
    pass


def downgrade():
    # No schema changes to revert
    pass
