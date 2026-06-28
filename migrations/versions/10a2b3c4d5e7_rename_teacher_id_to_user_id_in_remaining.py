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

def upgrade():
    # Rename teacher_id to user_id in 4 tables
    op.alter_column('ledger_transaction', 'teacher_id', new_column_name='user_id')
    op.alter_column('store_items', 'teacher_id', new_column_name='user_id')
    op.alter_column('issues', 'teacher_id', new_column_name='user_id')
    op.alter_column('announcements', 'teacher_id', new_column_name='user_id')

def downgrade():
    op.alter_column('ledger_transaction', 'user_id', new_column_name='teacher_id')
    op.alter_column('store_items', 'user_id', new_column_name='teacher_id')
    op.alter_column('issues', 'user_id', new_column_name='teacher_id')
    op.alter_column('announcements', 'user_id', new_column_name='teacher_id')
