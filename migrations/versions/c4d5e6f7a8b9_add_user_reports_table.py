"""Add user_reports table for help and support submissions

Revision ID: c4d5e6f7a8b9
Revises: 8a4ca17f506f
Create Date: 2025-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = '8a4ca17f506f'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_reports table (skip if already exists)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    if 'user_reports' in inspector.get_table_names():
        # Table already exists, skip creation
        return

    op.create_table(
        'user_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('anonymous_code', sa.String(length=64), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('report_type', sa.String(length=20), server_default='bug', nullable=False),
        sa.Column('error_code', sa.String(length=10), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('steps_to_reproduce', sa.Text(), nullable=True),
        sa.Column('expected_behavior', sa.Text(), nullable=True),
        sa.Column('page_url', sa.String(length=500), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by_sysadmin_id', sa.Integer(), nullable=True),
        sa.Column('reward_amount', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('reward_sent_at', sa.DateTime(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['reviewed_by_sysadmin_id'], ['system_admins.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_reports_anonymous_code'), 'user_reports', ['anonymous_code'], unique=False)
    op.create_index(op.f('ix_user_reports_submitted_at'), 'user_reports', ['submitted_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_reports_submitted_at'), table_name='user_reports')
    op.drop_index(op.f('ix_user_reports_anonymous_code'), table_name='user_reports')
    op.drop_table('user_reports')
