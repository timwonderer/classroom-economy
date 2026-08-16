"""Make teacher_user_id nullable on classes table

Revision ID: c7d8e9f0a1b2
Revises: 4b1c1053b69e
Create Date: 2026-08-13 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7d8e9f0a1b2'
down_revision = '4b1c1053b69e'
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


def upgrade():
    if column_exists('classes', 'teacher_user_id'):
        op.alter_column('classes', 'teacher_user_id',
                        existing_type=sa.Integer(),
                        nullable=True)
        print("✅ Made teacher_user_id nullable on classes")
    else:
        print("⚠️  Column teacher_user_id does not exist on classes, skipping")


def downgrade():
    if column_exists('classes', 'teacher_user_id'):
        # Backfill NULLs before making NOT NULL (safety)
        op.execute("DELETE FROM classes WHERE teacher_user_id IS NULL")
        op.alter_column('classes', 'teacher_user_id',
                        existing_type=sa.Integer(),
                        nullable=False)
        print("✅ Made teacher_user_id NOT NULL on classes (deleted orphaned rows)")
