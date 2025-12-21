"""add student teacher association table for shared students

Revision ID: c1c6f7e5e3a0
Revises: b73c4d92eadd
Create Date: 2024-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1c6f7e5e3a0'
down_revision = 'b73c4d92eadd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'admin_id', name='uq_student_teachers_student_admin'),
    )
    op.create_index('ix_student_teachers_admin_id', 'student_teachers', ['admin_id'], unique=False)
    op.create_index('ix_student_teachers_student_id', 'student_teachers', ['student_id'], unique=False)

    connection = op.get_bind()
    students_table = sa.table(
        'students',
        sa.column('id', sa.Integer()),
        sa.column('teacher_id', sa.Integer()),
    )
    student_teachers_table = sa.table(
        'student_teachers',
        sa.column('student_id', sa.Integer()),
        sa.column('admin_id', sa.Integer()),
        sa.column('created_at', sa.DateTime()),
    )

    insert_stmt = student_teachers_table.insert().from_select(
        ['student_id', 'admin_id', 'created_at'],
        sa.select(
            students_table.c.id,
            students_table.c.teacher_id,
            sa.func.now(),
        ).where(students_table.c.teacher_id.isnot(None)),
    )
    connection.execute(insert_stmt)


def downgrade():
    op.drop_index('ix_student_teachers_student_id', table_name='student_teachers')
    op.drop_index('ix_student_teachers_admin_id', table_name='student_teachers')
    op.drop_table('student_teachers')
