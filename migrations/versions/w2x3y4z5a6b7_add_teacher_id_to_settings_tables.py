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


def upgrade():
    # Step 1: Add teacher_id columns as NULLABLE first
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
    
    # Step 2: Backfill existing rows with the first admin's ID
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.scalar()
    
    if first_admin_id:
        # Update NULL values with the first admin's ID
        conn.execute(sa.text("UPDATE rent_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE payroll_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE banking_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE hall_pass_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
    
    # Step 3: Now make columns NOT NULL (only if we have data)
    if first_admin_id:
        with op.batch_alter_table('rent_settings', schema=None) as batch_op:
            batch_op.alter_column('teacher_id', nullable=False)
        
        with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
            batch_op.alter_column('teacher_id', nullable=False)
        
        with op.batch_alter_table('banking_settings', schema=None) as batch_op:
            batch_op.alter_column('teacher_id', nullable=False)
        
        with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
            batch_op.alter_column('teacher_id', nullable=False)
    
    # Step 4: Add foreign key constraints
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_rent_settings_teacher', 'admins', ['teacher_id'], ['id'])
    
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_payroll_settings_teacher', 'admins', ['teacher_id'], ['id'])
    
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_banking_settings_teacher', 'admins', ['teacher_id'], ['id'])
    
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_hall_pass_settings_teacher', 'admins', ['teacher_id'], ['id'])


def downgrade():
    # Drop foreign key constraints
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_hall_pass_settings_teacher', type_='foreignkey')
    
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_banking_settings_teacher', type_='foreignkey')
    
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_payroll_settings_teacher', type_='foreignkey')
    
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_rent_settings_teacher', type_='foreignkey')
    
    # Drop columns
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.drop_column('teacher_id')
    
    with op.batch_alter_table('banking_settings', schema=None) as batch_op:
        batch_op.drop_column('teacher_id')
    
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        batch_op.drop_column('teacher_id')
    
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.drop_column('teacher_id')
