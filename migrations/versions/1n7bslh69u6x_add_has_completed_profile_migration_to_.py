"""add has_completed_profile_migration to students

Revision ID: 1n7bslh69u6x
Revises: z2a3b4c5d6e7, fa40lzegx5tq
Create Date: 2025-12-02 06:00:00.000000

This migration merges three migration branches and adds has_completed_profile_migration field.
Merges:
- z2a3b4c5d6e7 (feature settings and onboarding)
- fa40lzegx5tq (DeletionRequestStatus enum fix) which comes after 5esz32blgjej (enum lowercase)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1n7bslh69u6x'
down_revision = ('z2a3b4c5d6e7', 'fa40lzegx5tq')
branch_labels = None
depends_on = None


def upgrade():
    # Add has_completed_profile_migration column to students table
    op.add_column('students', sa.Column('has_completed_profile_migration', sa.Boolean(), nullable=True))
    
    # Set default to False for all existing students
    op.execute('UPDATE students SET has_completed_profile_migration = FALSE WHERE has_completed_profile_migration IS NULL')
    
    # Make column non-nullable after setting defaults
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.alter_column('has_completed_profile_migration',
                              existing_type=sa.Boolean(),
                              nullable=False,
                              server_default=sa.false())


def downgrade():
    # Remove has_completed_profile_migration column
    op.drop_column('students', 'has_completed_profile_migration')
