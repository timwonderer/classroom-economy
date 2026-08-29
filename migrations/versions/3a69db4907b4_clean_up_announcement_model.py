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


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


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
    if not column_exists('announcements', 'audience_type'):
        op.add_column('announcements', sa.Column('audience_type', sa.VARCHAR(length=30), autoincrement=False, nullable=False, server_default='class'))
    if not column_exists('announcements', 'created_by_user_id'):
        op.add_column('announcements', sa.Column('created_by_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    if not column_exists('announcements', 'target_user_id'):
        op.add_column('announcements', sa.Column('target_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    if not foreign_key_exists('announcements', 'fk_announcements_target_teacher_id_users'):
        op.create_foreign_key('fk_announcements_target_teacher_id_users', 'announcements', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
    if not foreign_key_exists('announcements', 'fk_announcements_system_admin_id_users'):
        op.create_foreign_key('fk_announcements_system_admin_id_users', 'announcements', 'users', ['created_by_user_id'], ['id'], ondelete='CASCADE')
    if not index_exists('announcements', 'ix_announcements_system_admin'):
        op.create_index(op.f('ix_announcements_system_admin'), 'announcements', ['created_by_user_id', 'is_active'], unique=False)
    if not index_exists('announcements', 'ix_announcements_audience_type'):
        op.create_index(op.f('ix_announcements_audience_type'), 'announcements', ['audience_type', 'is_active'], unique=False)
    op.alter_column('announcements', 'class_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)
    op.alter_column('announcements', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

