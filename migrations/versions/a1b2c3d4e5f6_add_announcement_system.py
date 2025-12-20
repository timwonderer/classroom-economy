"""Add announcement system tables

Revision ID: a1b2c3d4e5f6
Revises: 00212c18b0ac
Create Date: 2025-12-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '00212c18b0ac'
branch_labels = None
depends_on = None


def upgrade():
    # Create announcements table
    op.create_table('announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('announcement_type', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_sysadmin_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_sysadmin_id'], ['system_admins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_announcements_is_active'), 'announcements', ['is_active'], unique=False)

    # Create announcement_dismissals table
    op.create_table('announcement_dismissals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('announcement_id', sa.Integer(), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['announcement_id'], ['announcements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('announcement_id', 'user_type', 'user_id', name='uq_announcement_user_dismissal')
    )
    op.create_index('ix_announcement_dismissals_user', 'announcement_dismissals', ['user_type', 'user_id'], unique=False)


def downgrade():
    # Drop announcement_dismissals table
    op.drop_index('ix_announcement_dismissals_user', table_name='announcement_dismissals')
    op.drop_table('announcement_dismissals')

    # Drop announcements table
    op.drop_index(op.f('ix_announcements_is_active'), table_name='announcements')
    op.drop_table('announcements')
