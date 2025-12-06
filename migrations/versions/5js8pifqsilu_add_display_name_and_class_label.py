"""Add display_name to admins and class_label to teacher_blocks

Revision ID: 5js8pifqsilu
Revises:
Create Date: 2025-12-06

This migration adds:
- display_name column to admins table (teacher's customizable display name)
- class_label column to teacher_blocks table (teacher's customizable class label)

Both columns are nullable to maintain backward compatibility, with fallback logic
in the model methods get_display_name() and get_class_label().

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5js8pifqsilu'
down_revision = None
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    """Add display_name and class_label columns."""

    # Add display_name to admins table
    if not column_exists('admins', 'display_name'):
        op.add_column('admins',
            sa.Column('display_name', sa.String(100), nullable=True)
        )
        print("✅ Added display_name column to admins table")
    else:
        print("⚠️  Column 'display_name' already exists on 'admins', skipping...")

    # Add class_label to teacher_blocks table
    if not column_exists('teacher_blocks', 'class_label'):
        op.add_column('teacher_blocks',
            sa.Column('class_label', sa.String(50), nullable=True)
        )
        print("✅ Added class_label column to teacher_blocks table")
    else:
        print("⚠️  Column 'class_label' already exists on 'teacher_blocks', skipping...")


def downgrade():
    """Remove display_name and class_label columns."""

    # Remove class_label from teacher_blocks
    if column_exists('teacher_blocks', 'class_label'):
        op.drop_column('teacher_blocks', 'class_label')
        print("✅ Removed class_label column from teacher_blocks table")

    # Remove display_name from admins
    if column_exists('admins', 'display_name'):
        op.drop_column('admins', 'display_name')
        print("✅ Removed display_name column from admins table")
