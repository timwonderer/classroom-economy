"""Add Announcement model for teacher-to-class announcements

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2025-12-26 19:30:00.000000

This migration adds the announcements table to support teacher-to-class
communication. Announcements are scoped by join_code for proper multi-tenancy
isolation and allow teachers to post messages to specific class periods.

Features:
- Title and message content
- Priority levels (low, normal, high, urgent)
- Active/inactive toggle
- Optional expiration dates
- Full multi-tenancy support via join_code

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    # Create announcements table
    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('join_code', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient querying
    op.create_index('ix_announcements_join_code', 'announcements', ['join_code'])
    op.create_index('ix_announcements_join_code_active', 'announcements', ['join_code', 'is_active'])
    op.create_index('ix_announcements_teacher_join_code', 'announcements', ['teacher_id', 'join_code'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_announcements_teacher_join_code', table_name='announcements')
    op.drop_index('ix_announcements_join_code_active', table_name='announcements')
    op.drop_index('ix_announcements_join_code', table_name='announcements')

    # Drop table
    op.drop_table('announcements')
