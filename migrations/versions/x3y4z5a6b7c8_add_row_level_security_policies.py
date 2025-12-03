"""Add Row Level Security (RLS) policies for multi-tenancy

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: [keep original timestamp]

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'x3y4z5a6b7c8'
down_revision = 'w2x3y4z5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get list of tables that actually have teacher_id column
    tables_with_teacher_id = []
    for table_name in ['rent_settings', 'payroll_settings', 'banking_settings', 
                       'hall_pass_settings', 'store_items', 'insurance_policies']:
        try:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            if 'teacher_id' in columns:
                tables_with_teacher_id.append(table_name)
        except Exception:
            # Table doesn't exist, skip it
            continue
    
    # Enable RLS and create policies only for tables that have teacher_id
    for table_name in tables_with_teacher_id:
        # Enable RLS
        conn.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))
        
        # Create SELECT policy
        conn.execute(sa.text(f'''
            CREATE POLICY "{table_name}_tenant_isolation_select" ON "{table_name}"
            FOR SELECT
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        '''))
        
        # Create INSERT policy
        conn.execute(sa.text(f'''
            CREATE POLICY "{table_name}_tenant_isolation_insert" ON "{table_name}"
            FOR INSERT
            WITH CHECK (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        '''))
        
        # Create UPDATE policy
        conn.execute(sa.text(f'''
            CREATE POLICY "{table_name}_tenant_isolation_update" ON "{table_name}"
            FOR UPDATE
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
            WITH CHECK (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        '''))
        
        # Create DELETE policy
        conn.execute(sa.text(f'''
            CREATE POLICY "{table_name}_tenant_isolation_delete" ON "{table_name}"
            FOR DELETE
            USING (
                teacher_id = NULLIF(current_setting('app.current_teacher_id', TRUE), '')::integer
            )
        '''))


def downgrade():
    conn = op.get_bind()
    
    # Drop policies and disable RLS for all tables
    for table_name in ['rent_settings', 'payroll_settings', 'banking_settings', 
                       'hall_pass_settings', 'store_items', 'insurance_policies']:
        try:
            # Drop policies (ignore errors if they don't exist)
            for operation in ['select', 'insert', 'update', 'delete']:
                try:
                    conn.execute(sa.text(f'DROP POLICY IF EXISTS "{table_name}_tenant_isolation_{operation}" ON "{table_name}"'))
                except Exception:
                    pass
            
            # Disable RLS
            conn.execute(sa.text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY'))
        except Exception:
            # Table doesn't exist, skip it
            continue
