"""Merge user_reports and has_assigned_students migrations.

This merge resolves the duplicate `user_reports` table creation that was
introduced when `q4r5s6t7u8v9_add_user_reports_table` was created alongside
`c4d5e6f7a8b9_add_user_reports_table`. The duplicate migration has been removed,
and this merge keeps the Alembic history linear without generating multiple
heads.

Revision ID: r5s6t7u8v9w0
Revises: q4r5s6t7u8v9, c5f3a8d9e1b4
Create Date: 2025-11-21 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r5s6t7u8v9w0'
down_revision = ('q4r5s6t7u8v9', 'c5f3a8d9e1b4')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no changes needed
    pass


def downgrade():
    # This is a merge migration - no changes needed
    pass
