"""add teacher_id to transactions for per-teacher banking

Revision ID: d8e9f0a1b2c3
Revises: c1c6f7e5e3a0
Create Date: 2025-11-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c1c6f7e5e3a0'
branch_labels = None
depends_on = None


def upgrade():
    # Add teacher_id column to transactions table
    op.add_column('transactions',
        sa.Column('teacher_id', sa.Integer(), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_transactions_teacher_id_admins',
        'transactions', 'admins',
        ['teacher_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add index for performance
    op.create_index(
        'ix_transactions_teacher_id',
        'transactions',
        ['teacher_id']
    )

    # Backfill existing transactions with student's primary teacher
    # For students with a teacher_id, assign all their transactions to that teacher
    op.execute("""
        UPDATE transactions
        SET teacher_id = (
            SELECT teacher_id
            FROM students
            WHERE students.id = transactions.student_id
        )
        WHERE teacher_id IS NULL
        AND EXISTS (
            SELECT 1 FROM students
            WHERE students.id = transactions.student_id
            AND students.teacher_id IS NOT NULL
        )
    """)


def downgrade():
    op.drop_index('ix_transactions_teacher_id', table_name='transactions')
    op.drop_constraint('fk_transactions_teacher_id_admins', 'transactions', type_='foreignkey')
    op.drop_column('transactions', 'teacher_id')
