"""Add teacher_id to settings tables for multi-tenancy isolation

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: [keep original timestamp]

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'w2x3y4z5a6b7'
down_revision = 'v1w2x3y4z5a6'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Step 1: Add teacher_id columns as NULLABLE first (only if they don't exist)
    tables = ['rent_settings', 'payroll_settings', 'banking_settings', 'hall_pass_settings']
    
    for table in tables:
        if not column_exists(table, 'teacher_id'):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
            print(f"✅ Added teacher_id column to {table}")
        else:
            print(f"⚠️  Column 'teacher_id' already exists on '{table}', skipping...")
    
    # Step 2: Backfill existing rows with the first admin's ID
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.scalar()
    
    if first_admin_id:
        # Update NULL values with the first admin's ID
        # NOTE: table names are from a hardcoded list, not user input - safe from SQL injection
        for table in tables:
            # Using text() with bound parameters for safe execution
            result = conn.execute(sa.text(f"UPDATE {table} SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
            if result.rowcount > 0:
                print(f"✅ Backfilled {result.rowcount} rows in {table} with teacher_id = {first_admin_id}")
    
    # Step 3: Now make columns NOT NULL (only if we have data and they're currently nullable)
    if first_admin_id:
        for table in tables:
            columns = inspector.get_columns(table)
            teacher_id_col = next((col for col in columns if col['name'] == 'teacher_id'), None)
            if teacher_id_col and teacher_id_col.get('nullable', True):
                with op.batch_alter_table(table, schema=None) as batch_op:
                    batch_op.alter_column('teacher_id', nullable=False)
                print(f"✅ Set teacher_id to NOT NULL on {table}")
            else:
                print(f"⚠️  Column 'teacher_id' is already NOT NULL on '{table}', skipping...")
    
    # Step 4: Add foreign key constraints (only if they don't exist)
    fk_names = {
        'rent_settings': 'fk_rent_settings_teacher',
        'payroll_settings': 'fk_payroll_settings_teacher',
        'banking_settings': 'fk_banking_settings_teacher',
        'hall_pass_settings': 'fk_hall_pass_settings_teacher'
    }
    
    for table, fk_name in fk_names.items():
        if not foreign_key_exists(table, fk_name):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.create_foreign_key(fk_name, 'admins', ['teacher_id'], ['id'])
            print(f"✅ Added foreign key constraint {fk_name} on {table}")
        else:
            print(f"⚠️  Foreign key '{fk_name}' already exists on '{table}', skipping...")


def downgrade():
    tables = ['hall_pass_settings', 'banking_settings', 'payroll_settings', 'rent_settings']
    fk_names = {
        'hall_pass_settings': 'fk_hall_pass_settings_teacher',
        'banking_settings': 'fk_banking_settings_teacher',
        'payroll_settings': 'fk_payroll_settings_teacher',
        'rent_settings': 'fk_rent_settings_teacher'
    }
    
    # Drop foreign key constraints (only if they exist)
    for table in tables:
        fk_name = fk_names[table]
        if foreign_key_exists(table, fk_name):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            print(f"✅ Dropped foreign key constraint {fk_name} from {table}")
        else:
            print(f"⚠️  Foreign key '{fk_name}' does not exist on '{table}', skipping...")
    
    # Drop columns (only if they exist)
    for table in tables:
        if column_exists(table, 'teacher_id'):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_column('teacher_id')
            print(f"✅ Dropped teacher_id column from {table}")
        else:
            print(f"⚠️  Column 'teacher_id' does not exist on '{table}', skipping...")
