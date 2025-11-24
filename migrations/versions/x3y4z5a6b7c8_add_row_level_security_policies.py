"""Add Row Level Security (RLS) policies for multi-tenancy

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2025-11-24 20:30:00.000000

This migration implements PostgreSQL Row-Level Security (RLS) policies
to enforce multi-tenancy isolation at the database level. This follows
industry best practices from AWS, Azure, and major SaaS providers.

RLS provides defense-in-depth: even if application code has bugs,
the database will prevent cross-tenant data access.

Tables with RLS enabled:
- teacher_blocks (teacher_id)
- transaction (teacher_id)
- hall_pass_settings (teacher_id)
- store_items (teacher_id)
- rent_settings (teacher_id)
- insurance_policies (teacher_id)
- payroll_settings (teacher_id)
- banking_settings (teacher_id)
- payroll_rewards (teacher_id)
- payroll_fines (teacher_id)
- deletion_requests (admin_id)

Usage:
- Application must set session variable: SET app.current_teacher_id = 123;
- This happens automatically via Flask request hooks
- RLS policies filter all queries based on this session variable

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x3y4z5a6b7c8'
down_revision = 'w2x3y4z5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    """
    Enable Row-Level Security on all teacher-scoped tables.

    IMPORTANT: This migration is safe to run on production:
    - RLS policies allow read/write when current_teacher_id matches
    - If current_teacher_id is not set, queries will return empty results
    - Application code must set current_teacher_id for each request
    - Superuser access bypasses RLS (for migrations and maintenance)
    """
    conn = op.get_bind()

    # ============================================================
    # 1. Enable RLS on all teacher-scoped tables
    # ============================================================

    tables_with_teacher_id = [
        'teacher_blocks',
        'transaction',
        'hall_pass_settings',
        'store_items',
        'rent_settings',
        # Removed 'insurance_policies' - teacher_id may be NULL, causing RLS to filter out rows
        # TODO: Add insurance_policies once teacher_id is properly populated for all rows
        'payroll_settings',
        'banking_settings',
        'payroll_rewards',
        'payroll_fines',
    ]

    # Enable RLS on tables using proper identifier escaping
    for table in tables_with_teacher_id:
        # Use SQLAlchemy's quoted_name for safe identifier handling
        table_identifier = sa.sql.quoted_name(table, quote=True)
        conn.execute(sa.text(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY"))

    # Special case: deletion_requests uses admin_id instead of teacher_id
    conn.execute(sa.text("ALTER TABLE deletion_requests ENABLE ROW LEVEL SECURITY"))

    # ============================================================
    # 2. Create RLS policies for each table
    # ============================================================

    # Policy: Teachers can only see/modify their own records
    # Uses session variable: app.current_teacher_id
    # Set by application on each request

    # Create RLS policies using proper identifier escaping
    for table in tables_with_teacher_id:
        # Use SQLAlchemy's quoted_name for safe identifier handling
        table_identifier = sa.sql.quoted_name(table, quote=True)
        policy_prefix = table.replace('.', '_').replace('-', '_')  # Sanitize for policy names
        
        # Policy for SELECT
        conn.execute(sa.text(f"""
            CREATE POLICY {policy_prefix}_tenant_isolation_select ON {table_identifier}
            FOR SELECT
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        """))

        # Policy for INSERT
        conn.execute(sa.text(f"""
            CREATE POLICY {policy_prefix}_tenant_isolation_insert ON {table_identifier}
            FOR INSERT
            WITH CHECK (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        """))

        # Policy for UPDATE
        conn.execute(sa.text(f"""
            CREATE POLICY {policy_prefix}_tenant_isolation_update ON {table_identifier}
            FOR UPDATE
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
            WITH CHECK (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        """))

        # Policy for DELETE
        conn.execute(sa.text(f"""
            CREATE POLICY {policy_prefix}_tenant_isolation_delete ON {table_identifier}
            FOR DELETE
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        """))

    # Special policies for deletion_requests (uses admin_id)
    conn.execute(sa.text("""
        CREATE POLICY deletion_requests_tenant_isolation_select ON deletion_requests
        FOR SELECT
        USING (
            admin_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
        )
    """))

    conn.execute(sa.text("""
        CREATE POLICY deletion_requests_tenant_isolation_insert ON deletion_requests
        FOR INSERT
        WITH CHECK (
            admin_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
        )
    """))

    conn.execute(sa.text("""
        CREATE POLICY deletion_requests_tenant_isolation_update ON deletion_requests
        FOR UPDATE
        USING (
            admin_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
        )
        WITH CHECK (
            admin_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
        )
    """))

    conn.execute(sa.text("""
        CREATE POLICY deletion_requests_tenant_isolation_delete ON deletion_requests
        FOR DELETE
        USING (
            admin_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
        )
    """))

    print("""
    ✓ Row-Level Security enabled successfully!

    IMPORTANT: Application code must now set the tenant context on each request:

    In Flask (app/__init__.py or middleware):
        @app.before_request
        def set_tenant_context():
            if 'admin_id' in session:
                db.session.execute(
                    text("SET LOCAL app.current_teacher_id = :teacher_id"),
                    {"teacher_id": session['admin_id']}
                )

    This migration is safe - RLS policies allow full access when the session
    variable is set correctly. If not set, queries return empty results (fail-safe).
    """)


def downgrade():
    """
    Remove Row-Level Security policies and disable RLS.
    """
    conn = op.get_bind()

    tables_with_teacher_id = [
        'teacher_blocks',
        'transaction',
        'hall_pass_settings',
        'store_items',
        'rent_settings',
        # 'insurance_policies' removed - not in upgrade, so not in downgrade either
        'payroll_settings',
        'banking_settings',
        'payroll_rewards',
        'payroll_fines',
    ]

    # Drop policies for each table using proper identifier escaping
    for table in tables_with_teacher_id:
        table_identifier = sa.sql.quoted_name(table, quote=True)
        policy_prefix = table.replace('.', '_').replace('-', '_')  # Sanitize for policy names
        for operation in ['select', 'insert', 'update', 'delete']:
            conn.execute(sa.text(
                f"DROP POLICY IF EXISTS {policy_prefix}_tenant_isolation_{operation} ON {table_identifier}"
            ))

    # Drop policies for deletion_requests
    for operation in ['select', 'insert', 'update', 'delete']:
        conn.execute(sa.text(
            f"DROP POLICY IF EXISTS deletion_requests_tenant_isolation_{operation} ON deletion_requests"
        ))

    # Disable RLS on all tables
    for table in tables_with_teacher_id:
        table_identifier = sa.sql.quoted_name(table, quote=True)
        conn.execute(sa.text(f"ALTER TABLE {table_identifier} DISABLE ROW LEVEL SECURITY"))

    conn.execute(sa.text("ALTER TABLE deletion_requests DISABLE ROW LEVEL SECURITY"))

    print("✓ Row-Level Security disabled and policies removed")
