"""Jobs feature removed (stub migration for database compatibility)

Revision ID: aa1bb2cc3dd4
Revises: merge_heads_001
Create Date: 2025-12-10 08:00:00.000000

This is a stub migration that was previously used for the jobs feature.
The jobs feature has been removed from the codebase, but this migration
file is retained to maintain compatibility with databases that were
upgraded to this revision.

Original migration: aa1bb2cc3dd4_add_jobs_feature_tables.py
- Added job_templates, jobs, job_applications, employee_job_assignments,
  employee_job_warnings, contract_job_claims, job_application_bans,
  jobs_settings tables
- Added jobs_enabled column to feature_settings

This stub ensures that databases at revision aa1bb2cc3dd4 can continue
to be managed by Alembic without errors. The tables created by the original
migration will remain in the database but will not be used by the application.

"""




# revision identifiers, used by Alembic.
revision = 'aa1bb2cc3dd4'
down_revision = 'merge_heads_001'
branch_labels = None
depends_on = None


def upgrade():
    # This function runs when upgrading from merge_heads_001 to aa1bb2cc3dd4.
    # Since the jobs feature has been removed, this does nothing.
    # Databases already at aa1bb2cc3dd4 won't run this function -
    # Alembic will simply recognize the revision exists.
    pass


def downgrade():
    # Downgrade is not supported for this stub migration.
    # WARNING: If your database previously had the jobs feature migration applied,
    # the job-related tables (e.g., job_templates, jobs, job_applications, etc.) will remain
    # in the database after downgrade. This stub does NOT remove those tables.
    # For databases that never had the jobs tables, downgrade is a no-op.
    # If you wish to remove the job tables, you must do so manually.
    raise NotImplementedError("Downgrade from this stub is not supported as the original migration is removed.")
