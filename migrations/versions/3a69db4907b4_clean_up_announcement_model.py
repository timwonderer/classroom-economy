"""Clean up Announcement model

Revision ID: 3a69db4907b4
Revises: 8c62d78f82bb
Create Date: 2026-08-07 01:02:48.516780

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a69db4907b4'
down_revision = '8c62d78f82bb'
branch_labels = None
depends_on = None

def upgrade():
    # Backfill: delete legacy system announcements that lack a class_id or user_id
    op.execute('DELETE FROM announcements WHERE class_id IS NULL OR user_id IS NULL')

    op.alter_column('announcements', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('announcements', 'class_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
    op.drop_index('ix_announcements_audience_type', table_name='announcements', if_exists=True)
    op.drop_index('ix_announcements_system_admin', table_name='announcements', if_exists=True)
    op.execute('ALTER TABLE announcements DROP CONSTRAINT IF EXISTS fk_announcements_system_admin_id_users')
    op.execute('ALTER TABLE announcements DROP CONSTRAINT IF EXISTS fk_announcements_target_teacher_id_users')
    op.execute('ALTER TABLE announcements DROP COLUMN IF EXISTS target_user_id')
    op.execute('ALTER TABLE announcements DROP COLUMN IF EXISTS created_by_user_id')
    op.execute('ALTER TABLE announcements DROP COLUMN IF EXISTS audience_type')


def downgrade():
    op.add_column('announcements', sa.Column('audience_type', sa.VARCHAR(length=30), autoincrement=False, nullable=False, server_default='class'))
    op.add_column('announcements', sa.Column('created_by_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('announcements', sa.Column('target_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('fk_announcements_target_teacher_id_users', 'announcements', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_announcements_system_admin_id_users', 'announcements', 'users', ['created_by_user_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_announcements_system_admin'), 'announcements', ['created_by_user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_announcements_audience_type'), 'announcements', ['audience_type', 'is_active'], unique=False)
    op.alter_column('announcements', 'class_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)
    op.alter_column('announcements', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

