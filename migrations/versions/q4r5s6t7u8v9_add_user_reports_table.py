"""Add user_reports table for bug reporting system

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
Create Date: 2025-11-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'q4r5s6t7u8v9'
down_revision = 'p3q4r5s6t7u8'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_reports table
    op.create_table('user_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('anonymous_code', sa.String(length=64), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('report_type', sa.String(length=20), nullable=False),
        sa.Column('error_code', sa.String(length=10), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('steps_to_reproduce', sa.Text(), nullable=True),
        sa.Column('expected_behavior', sa.Text(), nullable=True),
        sa.Column('page_url', sa.String(length=500), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by_sysadmin_id', sa.Integer(), nullable=True),
        sa.Column('reward_amount', sa.Float(), nullable=True),
        sa.Column('reward_sent_at', sa.DateTime(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_sysadmin_id'], ['system_admins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('ix_user_reports_anonymous_code', 'user_reports', ['anonymous_code'])
    op.create_index('ix_user_reports_submitted_at', 'user_reports', ['submitted_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_user_reports_submitted_at', table_name='user_reports')
    op.drop_index('ix_user_reports_anonymous_code', table_name='user_reports')

    # Drop table
    op.drop_table('user_reports')
