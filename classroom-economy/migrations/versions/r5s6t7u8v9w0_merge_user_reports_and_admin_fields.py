"""Merge user_reports and has_assigned_students migrations.

This 3-way merge resolves the duplicate user_reports table creation from two
different branches:
- c4d5e6f7a8b9: user_reports table from main branch
- q4r5s6t7u8v9: user_reports table from feature branch (conditional creation)
- c5f3a8d9e1b4: has_assigned_students column

The q4r5s6t7u8v9 migration checks if the table exists before creating it,
preventing conflicts.

Revision ID: r5s6t7u8v9w0
Revises: c4d5e6f7a8b9, q4r5s6t7u8v9, c5f3a8d9e1b4
Create Date: 2025-11-21 08:00:00.000000

"""


# revision identifiers, used by Alembic.
revision = 'r5s6t7u8v9w0'
down_revision = ('c4d5e6f7a8b9', 'q4r5s6t7u8v9', 'c5f3a8d9e1b4')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no changes needed
    pass


def downgrade():
    # This is a merge migration - no changes needed
    pass
