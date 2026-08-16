"""Rename teacher_id to teacher_user_id in classes table

Revision ID: f1a2b3c4d5e6
Revises: 9d7f5e6c4b3a
Create Date: 2026-08-13 04:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '9d7f5e6c4b3a'
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


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    # Step 1: Drop FK on old column name (teacher_id or user_id)
    if foreign_key_exists('classes', 'fk_classes_teacher_id_users'):
        op.drop_constraint('fk_classes_teacher_id_users', 'classes', type_='foreignkey')
        print("✅ Dropped FK fk_classes_teacher_id_users")

    # Step 2: Drop old index
    if index_exists('classes', 'ix_classes_teacher_id'):
        op.drop_index('ix_classes_teacher_id', table_name='classes')
        print("✅ Dropped index ix_classes_teacher_id")
    if index_exists('classes', 'ix_classes_user_id'):
        op.drop_index('ix_classes_user_id', table_name='classes')
        print("✅ Dropped index ix_classes_user_id")

    # Step 3: Rename column
    if column_exists('classes', 'teacher_id'):
        op.alter_column('classes', 'teacher_id', new_column_name='teacher_user_id')
        print("✅ Renamed teacher_id -> teacher_user_id")
    elif column_exists('classes', 'user_id'):
        op.alter_column('classes', 'user_id', new_column_name='teacher_user_id')
        print("✅ Renamed user_id -> teacher_user_id")
    elif column_exists('classes', 'teacher_user_id'):
        print("⚠️  Column teacher_user_id already exists, skipping rename")
    else:
        raise RuntimeError("No recognized teacher column found on classes table")

    # Step 4: Create new index
    if not index_exists('classes', 'ix_classes_teacher_user_id'):
        op.create_index('ix_classes_teacher_user_id', 'classes', ['teacher_user_id'], unique=False)
        print("✅ Created index ix_classes_teacher_user_id")

    # Step 5: Create FK on new column name
    if not foreign_key_exists('classes', 'fk_classes_teacher_user_id_users'):
        op.create_foreign_key(
            'fk_classes_teacher_user_id_users',
            'classes', 'users',
            ['teacher_user_id'], ['id'],
            ondelete='CASCADE',
        )
        print("✅ Created FK fk_classes_teacher_user_id_users")


def downgrade():
    # Reverse: teacher_user_id -> teacher_id
    if foreign_key_exists('classes', 'fk_classes_teacher_user_id_users'):
        op.drop_constraint('fk_classes_teacher_user_id_users', 'classes', type_='foreignkey')

    if index_exists('classes', 'ix_classes_teacher_user_id'):
        op.drop_index('ix_classes_teacher_user_id', table_name='classes')

    if column_exists('classes', 'teacher_user_id'):
        op.alter_column('classes', 'teacher_user_id', new_column_name='teacher_id')

    if not index_exists('classes', 'ix_classes_teacher_id'):
        op.create_index('ix_classes_teacher_id', 'classes', ['teacher_id'], unique=False)

    if not foreign_key_exists('classes', 'fk_classes_teacher_id_users'):
        op.create_foreign_key(
            'fk_classes_teacher_id_users',
            'classes', 'users',
            ['teacher_id'], ['id'],
            ondelete='CASCADE',
        )
