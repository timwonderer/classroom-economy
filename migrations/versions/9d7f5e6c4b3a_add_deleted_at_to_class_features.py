"""Add deleted_at soft deletion column to ClassFeature

Revision ID: 9d7f5e6c4b3a
Revises: 9c6d5e4f3a2b
Create Date: 2026-08-09 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


revision = '9d7f5e6c4b3a'
down_revision = '9c6d5e4f3a2b'
branch_labels = None
depends_on = None


def upgrade():
    """Add deleted_at column to class_features table."""
    if not column_exists('class_features', 'deleted_at'):
        op.add_column(
            'class_features',
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
        )
        print("✅ Added deleted_at column to class_features")
    else:
        print("⚠️  Column deleted_at already exists on class_features, skipping...")


def downgrade():
    """Remove deleted_at column from class_features table."""
    if column_exists('class_features', 'deleted_at'):
        op.drop_column('class_features', 'deleted_at')
        print("❌ Dropped deleted_at column from class_features")
    else:
        print("⚠️  Column deleted_at does not exist on class_features, skipping...")
