"""Add join_code to student_blocks table

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2025-12-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    # Add join_code column to student_blocks table
    op.add_column('student_blocks', sa.Column('join_code', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_student_blocks_join_code'), 'student_blocks', ['join_code'], unique=False)


def downgrade():
    # Remove the index and column
    op.drop_index(op.f('ix_student_blocks_join_code'), table_name='student_blocks')
    op.drop_column('student_blocks', 'join_code')
