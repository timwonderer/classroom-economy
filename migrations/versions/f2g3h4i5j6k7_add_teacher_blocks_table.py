"""add teacher_blocks table for join code system

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2025-11-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f2g3h4i5j6k7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    # Create teacher_blocks table for join code-based account claiming
    op.create_table(
        'teacher_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),

        # Student identifiers (encrypted/hashed)
        sa.Column('first_name', sa.LargeBinary(), nullable=False),  # PIIEncryptedType stored as LargeBinary
        sa.Column('last_initial', sa.String(length=1), nullable=False),
        sa.Column('last_name_hash_by_part', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('dob_sum', sa.Integer(), nullable=False),
        sa.Column('salt', sa.LargeBinary(length=16), nullable=False),
        sa.Column('first_half_hash', sa.String(length=64), nullable=False),

        # Join code
        sa.Column('join_code', sa.String(length=20), nullable=False),

        # Claim status
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('is_claimed', sa.Boolean(), nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='SET NULL'),
    )

    # Create indexes for efficient lookups
    op.create_index('ix_teacher_blocks_join_code', 'teacher_blocks', ['join_code'])
    op.create_index('ix_teacher_blocks_teacher_block', 'teacher_blocks', ['teacher_id', 'block'])
    op.create_index('ix_teacher_blocks_claimed', 'teacher_blocks', ['is_claimed'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_teacher_blocks_claimed', table_name='teacher_blocks')
    op.drop_index('ix_teacher_blocks_teacher_block', table_name='teacher_blocks')
    op.drop_index('ix_teacher_blocks_join_code', table_name='teacher_blocks')

    # Drop table
    op.drop_table('teacher_blocks')
