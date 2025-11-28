"""Add FeatureSettings and TeacherOnboarding models

Revision ID: z2a3b4c5d6e7
Revises: x3y4z5a6b7c8
Create Date: 2025-11-28 08:00:00.000000

This migration adds two new tables:

1. feature_settings: Per-period/block feature toggle settings for teachers
   - Allows teachers to enable/disable major features on a per-period basis
   - Features: payroll, insurance, banking, rent, hall_pass, store, bug_reports

2. teacher_onboarding: Tracks onboarding progress for new teachers
   - Guides new teachers through initial setup
   - Tracks step completion and allows resume/skip

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z2a3b4c5d6e7'
down_revision = 'x3y4z5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    # Create feature_settings table
    op.create_table(
        'feature_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=True),
        sa.Column('payroll_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('insurance_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('banking_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('rent_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('hall_pass_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('store_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('bug_reports_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('bug_rewards_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', 'block', name='uq_feature_settings_teacher_block')
    )

    # Create indexes for feature_settings
    op.create_index('ix_feature_settings_teacher_id', 'feature_settings', ['teacher_id'])

    # Create teacher_onboarding table
    op.create_table(
        'teacher_onboarding',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_skipped', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('current_step', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('steps_completed', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('skipped_at', sa.DateTime(), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', name='uq_teacher_onboarding_teacher_id')
    )

    # Add RLS policy for feature_settings (PostgreSQL only)
    # This uses exception handling to gracefully handle non-PostgreSQL databases
    op.execute("""
        DO $$
        BEGIN
            -- Enable RLS on feature_settings (only works on PostgreSQL)
            ALTER TABLE feature_settings ENABLE ROW LEVEL SECURITY;
            
            -- Create policy for feature_settings
            CREATE POLICY teacher_isolation_policy ON feature_settings
                USING (teacher_id = NULLIF(current_setting('app.current_teacher_id', true), '')::integer);
        EXCEPTION WHEN OTHERS THEN
            -- Non-PostgreSQL databases or errors are silently ignored
            NULL;
        END $$;
    """)


def downgrade():
    # Drop RLS policies (PostgreSQL only)
    op.execute("""
        DO $$
        BEGIN
            IF current_setting('server_version_num')::integer > 0 THEN
                DROP POLICY IF EXISTS teacher_isolation_policy ON feature_settings;
                ALTER TABLE feature_settings DISABLE ROW LEVEL SECURITY;
            END IF;
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END $$;
    """)

    # Drop tables
    op.drop_table('teacher_onboarding')
    op.drop_index('ix_feature_settings_teacher_id', table_name='feature_settings')
    op.drop_table('feature_settings')
