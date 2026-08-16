"""Drop unique index ix_attendance_sessions_target_user_id_active for append-only compliance

Revision ID: 93de308c02c0
Revises: c7d8e9f0a1b2
Create Date: 2026-08-15 03:29:36.045593

"""
from alembic import op
import sqlalchemy as sa


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


# revision identifiers, used by Alembic.
revision = '93de308c02c0'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    if index_exists('attendance_sessions', 'ix_attendance_sessions_target_user_id_active'):
        op.drop_index(
            'ix_attendance_sessions_target_user_id_active',
            table_name='attendance_sessions',
            postgresql_where="(((status)::text = 'active'::text) AND (target_user_id IS NOT NULL))",
        )


def downgrade():
    if not index_exists('attendance_sessions', 'ix_attendance_sessions_target_user_id_active'):
        op.create_index(
            'ix_attendance_sessions_target_user_id_active',
            'attendance_sessions',
            ['target_user_id'],
            unique=True,
            postgresql_where="(((status)::text = 'active'::text) AND (target_user_id IS NOT NULL))",
        )
