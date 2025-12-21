"""Add StudentBlock model and tap deletion fields

Revision ID: a1b2c3d4e5f7
Revises: 1n7bslh69u6x
Create Date: 2025-12-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '1n7bslh69u6x'
branch_labels = None
depends_on = None


def upgrade():
    # Create student_blocks table
    op.create_table('student_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=False),
        sa.Column('tap_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('done_for_day_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'period', name='uq_student_blocks_student_period')
    )

    # Create indexes for student_blocks
    op.create_index('ix_student_blocks_student_id', 'student_blocks', ['student_id'])
    op.create_index('ix_student_blocks_period', 'student_blocks', ['period'])

    # Add deletion tracking fields to tap_events
    op.add_column('tap_events', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('tap_events', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('tap_events', sa.Column('deleted_by', sa.Integer(), nullable=True))

    # Add foreign key for deleted_by
    op.create_foreign_key('fk_tap_events_deleted_by', 'tap_events', 'admins', ['deleted_by'], ['id'], ondelete='SET NULL')


def downgrade():
    # Remove foreign key and columns from tap_events
    op.drop_constraint('fk_tap_events_deleted_by', 'tap_events', type_='foreignkey')
    op.drop_column('tap_events', 'deleted_by')
    op.drop_column('tap_events', 'deleted_at')
    op.drop_column('tap_events', 'is_deleted')

    # Drop indexes and table for student_blocks
    op.drop_index('ix_student_blocks_period', 'student_blocks')
    op.drop_index('ix_student_blocks_student_id', 'student_blocks')
    op.drop_table('student_blocks')
