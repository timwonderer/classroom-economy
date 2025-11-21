"""Add teacher_id column to students for tenancy

Revision ID: b73c4d92eadd
Revises: ('8a4ca17f506f', 'f5a1e3e4d7c8', 'n1o2p3q4r5s6')
Create Date: 2025-01-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b73c4d92eadd'
down_revision = ('8a4ca17f506f', 'f5a1e3e4d7c8', 'n1o2p3q4r5s6')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('students', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_students_teacher', 'students', 'admins', ['teacher_id'], ['id'])
    op.create_index('ix_students_teacher_id', 'students', ['teacher_id'])


def downgrade():
    op.drop_index('ix_students_teacher_id', table_name='students')
    op.drop_constraint('fk_students_teacher', 'students', type_='foreignkey')
    op.drop_column('students', 'teacher_id')
