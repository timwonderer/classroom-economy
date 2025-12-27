"""Add system admin announcement capabilities

Revision ID: f1g2h3i4j5k6
Revises: e3fbfe180e69
Create Date: 2025-12-26 21:00:00.000000

This migration extends the announcements table to support system admin announcements
with broader audience targeting capabilities.

Changes:
- Add system_admin_id for system admin-created announcements
- Add audience_type to support different targeting scopes
- Add target_teacher_id for 'teacher_all_classes' audience type
- Make teacher_id and join_code nullable (required for system admin announcements)
- Add new indexes for efficient querying
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1g2h3i4j5k6'
down_revision = 'e3fbfe180e69'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        # Add system admin support
        batch_op.add_column(sa.Column('system_admin_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('audience_type', sa.String(length=30), nullable=False, server_default='class'))
        batch_op.add_column(sa.Column('target_teacher_id', sa.Integer(), nullable=True))

        # Make teacher_id and join_code nullable for system admin announcements
        batch_op.alter_column('teacher_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('join_code', existing_type=sa.String(length=20), nullable=True)

        # Add foreign keys
        batch_op.create_foreign_key('fk_announcements_system_admin_id', 'system_admins', ['system_admin_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_announcements_target_teacher_id', 'admins', ['target_teacher_id'], ['id'], ondelete='CASCADE')

        # Add new indexes
        batch_op.create_index('ix_announcements_audience_type', ['audience_type', 'is_active'], unique=False)
        batch_op.create_index('ix_announcements_system_admin', ['system_admin_id', 'is_active'], unique=False)


def downgrade():
    # Remove new columns and indexes
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        # Drop indexes
        batch_op.drop_index('ix_announcements_system_admin')
        batch_op.drop_index('ix_announcements_audience_type')

        # Drop foreign keys
        batch_op.drop_constraint('fk_announcements_target_teacher_id', type_='foreignkey')
        batch_op.drop_constraint('fk_announcements_system_admin_id', type_='foreignkey')

        # Restore non-nullable constraints
        batch_op.alter_column('join_code', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('teacher_id', existing_type=sa.Integer(), nullable=False)

        # Drop new columns
        batch_op.drop_column('target_teacher_id')
        batch_op.drop_column('audience_type')
        batch_op.drop_column('system_admin_id')
