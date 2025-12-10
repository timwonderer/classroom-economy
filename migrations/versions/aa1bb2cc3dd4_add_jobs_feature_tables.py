"""Add jobs feature tables

Revision ID: aa1bb2cc3dd4
Revises: z2a3b4c5d6e7
Create Date: 2025-12-10 08:00:00.000000

This migration adds the jobs feature to the classroom economy system.

Jobs feature includes:
- Employee jobs: Long-term positions with regular pay, application-based
- Contract jobs: One-off bounties, first-come-first-served

New tables:
- job_templates: Reusable job templates in the teacher's job bank
- jobs: Instances of templates assigned to specific periods
- job_applications: Student applications for employee jobs
- employee_job_assignments: Active employee job assignments
- employee_job_warnings: Warning history for employee jobs
- contract_job_claims: Contract job claims and completion tracking
- job_application_bans: Penalties for improper quitting
- jobs_settings: Per-teacher, per-block settings for jobs

Also adds jobs_enabled column to feature_settings table.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aa1bb2cc3dd4'
down_revision = 's7t8u9v0w1x2'
branch_labels = None
depends_on = None


def upgrade():
    # Create job_templates table
    op.create_table('job_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('job_title', sa.String(length=100), nullable=False),
        sa.Column('job_description', sa.Text(), nullable=True),
        sa.Column('job_type', sa.String(length=20), nullable=False),
        sa.Column('salary_amount', sa.Float(), nullable=True),
        sa.Column('payment_frequency', sa.String(length=20), nullable=True),
        sa.Column('vacancies', sa.Integer(), nullable=True),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('notice_period_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_cooldown_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('improper_quit_penalty_type', sa.String(length=20), nullable=False, server_default='none'),
        sa.Column('improper_quit_penalty_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bounty_amount', sa.Float(), nullable=True),
        sa.Column('application_questions', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create jobs table
    op.create_table('jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=False),
        sa.Column('join_code', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['job_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_jobs_teacher_block', 'jobs', ['teacher_id', 'block'])
    op.create_index('ix_jobs_join_code', 'jobs', ['join_code'])

    # Create job_applications table
    op.create_table('job_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_applications_student', 'job_applications', ['student_id'])
    op.create_index('ix_job_applications_status', 'job_applications', ['status'])

    # Create employee_job_assignments table
    op.create_table('employee_job_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('warnings_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_warning_date', sa.DateTime(), nullable=True),
        sa.Column('termination_type', sa.String(length=20), nullable=True),
        sa.Column('termination_reason', sa.Text(), nullable=True),
        sa.Column('quit_notice_date', sa.DateTime(), nullable=True),
        sa.Column('quit_effective_date', sa.DateTime(), nullable=True),
        sa.Column('last_payment_date', sa.DateTime(), nullable=True),
        sa.Column('next_payment_due', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_employee_assignments_student', 'employee_job_assignments', ['student_id'])
    op.create_index('ix_employee_assignments_active', 'employee_job_assignments', ['is_active'])

    # Create employee_job_warnings table
    op.create_table('employee_job_warnings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('warning_text', sa.Text(), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.Column('issued_by_admin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['employee_job_assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issued_by_admin_id'], ['admins.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create contract_job_claims table
    op.create_table('contract_job_claims',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('claimed_at', sa.DateTime(), nullable=False),
        sa.Column('student_marked_complete_at', sa.DateTime(), nullable=True),
        sa.Column('teacher_reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='claimed'),
        sa.Column('student_notes', sa.Text(), nullable=True),
        sa.Column('teacher_notes', sa.Text(), nullable=True),
        sa.Column('payment_amount', sa.Float(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contract_claims_student', 'contract_job_claims', ['student_id'])
    op.create_index('ix_contract_claims_status', 'contract_job_claims', ['status'])

    # Create job_application_bans table
    op.create_table('job_application_bans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('join_code', sa.String(length=20), nullable=False),
        sa.Column('ban_type', sa.String(length=20), nullable=False),
        sa.Column('job_template_id', sa.Integer(), nullable=True),
        sa.Column('banned_at', sa.DateTime(), nullable=False),
        sa.Column('banned_until', sa.DateTime(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_template_id'], ['job_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_bans_student', 'job_application_bans', ['student_id'])
    op.create_index('ix_job_bans_active', 'job_application_bans', ['is_active'])
    op.create_index(op.f('ix_job_application_bans_join_code'), 'job_application_bans', ['join_code'])

    # Create jobs_settings table
    op.create_table('jobs_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=True),
        sa.Column('employee_jobs_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('contract_jobs_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('auto_post_new_jobs', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('require_application_approval', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('setup_completed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('setup_completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['teacher_id'], ['admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', 'block', name='uq_jobs_settings_teacher_block')
    )
    op.create_index('ix_jobs_settings_teacher_id', 'jobs_settings', ['teacher_id'])

    # Add jobs_enabled column to feature_settings
    op.add_column('feature_settings', sa.Column('jobs_enabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Remove jobs_enabled column from feature_settings
    op.drop_column('feature_settings', 'jobs_enabled')

    # Drop all jobs-related tables in reverse order
    op.drop_index('ix_jobs_settings_teacher_id', table_name='jobs_settings')
    op.drop_table('jobs_settings')

    op.drop_index('ix_job_bans_active', table_name='job_application_bans')
    op.drop_index('ix_job_bans_student', table_name='job_application_bans')
    op.drop_index(op.f('ix_job_application_bans_join_code'), table_name='job_application_bans')
    op.drop_table('job_application_bans')

    op.drop_index('ix_contract_claims_status', table_name='contract_job_claims')
    op.drop_index('ix_contract_claims_student', table_name='contract_job_claims')
    op.drop_table('contract_job_claims')

    op.drop_table('employee_job_warnings')

    op.drop_index('ix_employee_assignments_active', table_name='employee_job_assignments')
    op.drop_index('ix_employee_assignments_student', table_name='employee_job_assignments')
    op.drop_table('employee_job_assignments')

    op.drop_index('ix_job_applications_status', table_name='job_applications')
    op.drop_index('ix_job_applications_student', table_name='job_applications')
    op.drop_table('job_applications')

    op.drop_index('ix_jobs_join_code', table_name='jobs')
    op.drop_index('ix_jobs_teacher_block', table_name='jobs')
    op.drop_table('jobs')

    op.drop_table('job_templates')
