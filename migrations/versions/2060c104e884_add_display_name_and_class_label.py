"""add display_name and class_label

Revision ID: 2060c104e884
Revises: b1c2d3e4f5g6
Create Date: 2025-12-06 04:44:01.376826

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2060c104e884'
down_revision = 'b1c2d3e4f5g6'
branch_labels = None
depends_on = None


def upgrade():
    # Add display_name to admins table
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=100), nullable=True))

    # Add class_label to teacher_blocks table
    with op.batch_alter_table('teacher_blocks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('class_label', sa.String(length=50), nullable=True))


def downgrade():
    # Remove class_label from teacher_blocks table
    with op.batch_alter_table('teacher_blocks', schema=None) as batch_op:
        batch_op.drop_column('class_label')

    # Remove display_name from admins table
    with op.batch_alter_table('admins', schema=None) as batch_op:
        batch_op.drop_column('display_name')
