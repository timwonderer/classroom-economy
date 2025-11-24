"""Migration: b4c5d6e7f8g9_add_deletion_request_model.py

Add DeletionRequest model for teacher-initiated deletion requests
Revision ID: b4c5d6e7f8g9
Revises: z1a2b3c4d5e6
Create Date: 2025-11-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8g9'
down_revision = 'c5d6e7f8g9h0'
branch_labels = None
depends_on = None


def upgrade():
    # Create deletion_requests table
    op.create_table(
        'deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=20), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('requested_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['system_admins.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_deletion_requests_admin_id', 'deletion_requests', ['admin_id'])
    op.create_index('ix_deletion_requests_status', 'deletion_requests', ['status'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_deletion_requests_status', table_name='deletion_requests')
    op.drop_index('ix_deletion_requests_admin_id', table_name='deletion_requests')

    # Drop table
    op.drop_table('deletion_requests')
