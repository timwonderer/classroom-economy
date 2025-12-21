"""Add join_code to student_blocks table

Revision ID: a1b2c3d4e5f8
Revises: z2a3b4c5d6e7
Create Date: 2025-12-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f8'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def table_exists(table_name):
    """Check if a table exists in the current database."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    table_name = 'student_blocks'
    column_name = 'join_code'
    index_name = op.f('ix_student_blocks_join_code')

    if not table_exists(table_name):
        print(f"⚠️  Table '{table_name}' does not exist; skipping join_code addition.")
        return

    if not column_exists(table_name, column_name):
        op.add_column(table_name, sa.Column(column_name, sa.String(length=20), nullable=True))
        print(f"✅ Added {column_name} column to {table_name} table")
    else:
        print(f"⚠️  Column '{column_name}' already exists on '{table_name}', skipping...")

    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, [column_name], unique=False)
        print(f"✅ Created index {index_name}")
    else:
        print(f"⚠️  Index '{index_name}' already exists on '{table_name}', skipping...")


def downgrade():
    table_name = 'student_blocks'
    column_name = 'join_code'
    index_name = op.f('ix_student_blocks_join_code')

    if not table_exists(table_name):
        print(f"⚠️  Table '{table_name}' does not exist; skipping downgrade steps.")
        return

    if index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
        print(f"❌ Dropped index {index_name}")
    else:
        print(f"⚠️  Index '{index_name}' does not exist on '{table_name}', skipping...")

    if column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)
        print(f"❌ Removed {column_name} column from {table_name} table")
    else:
        print(f"⚠️  Column '{column_name}' does not exist on '{table_name}', skipping...")
