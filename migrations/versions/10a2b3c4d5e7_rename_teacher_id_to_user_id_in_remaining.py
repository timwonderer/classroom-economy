"""Rename teacher_id to user_id in remaining models

Revision ID: 10a2b3c4d5e7
Revises: 10a2b3c4d5e6
Create Date: 2026-06-27 19:43:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '10a2b3c4d5e7'
down_revision = 'e68f0effe3c6'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


_TABLES = ['ledger_transaction', 'store_items', 'issues', 'announcements']


def upgrade():
    for table in _TABLES:
        if column_exists(table, 'teacher_id'):
            op.alter_column(table, 'teacher_id', new_column_name='user_id')

def downgrade():
    for table in _TABLES:
        if column_exists(table, 'user_id'):
            op.alter_column(table, 'user_id', new_column_name='teacher_id')
