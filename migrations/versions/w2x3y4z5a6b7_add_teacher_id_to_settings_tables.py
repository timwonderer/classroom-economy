"""Add teacher_id to settings tables for multi-tenancy isolation

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: [original timestamp]

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'w2x3y4z5a6b7'
down_revision = 'v1w2x3y4z5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add teacher_id columns as NULLABLE
    op.add_column('rent_settings', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.add_column('payroll_settings', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.add_column('banking_settings', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.add_column('hall_pass_settings', sa.Column('teacher_id', sa.Integer(), nullable=True))
    
    # Step 2: Backfill existing rows with first admin's ID
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.scalar()
    
    if first_admin_id:
        # Update all NULL values
        conn.execute(sa.text(f"UPDATE rent_settings SET teacher_id = {first_admin_id} WHERE teacher_id IS NULL"))
        conn.execute(sa.text(f"UPDATE payroll_settings SET teacher_id = {first_admin_id} WHERE teacher_id IS NULL"))
        conn.execute(sa.text(f"UPDATE banking_settings SET teacher_id = {first_admin_id} WHERE teacher_id IS NULL"))
        conn.execute(sa.text(f"UPDATE hall_pass_settings SET teacher_id = {first_admin_id} WHERE teacher_id IS NULL"))
    
    # Step 3: Now make columns NOT NULL
    op.alter_column('rent_settings', 'teacher_id', nullable=False)
    op.alter_column('payroll_settings', 'teacher_id', nullable=False)
    op.alter_column('banking_settings', 'teacher_id', nullable=False)
    op.alter_column('hall_pass_settings', 'teacher_id', nullable=False)
    
    # Step 4: Add foreign key constraints
    op.create_foreign_key('fk_rent_settings_teacher', 'rent_settings', 'admins', ['teacher_id'], ['id'])
    op.create_foreign_key('fk_payroll_settings_teacher', 'payroll_settings', 'admins', ['teacher_id'], ['id'])
    op.create_foreign_key('fk_banking_settings_teacher', 'banking_settings', 'admins', ['teacher_id'], ['id'])
    op.create_foreign_key('fk_hall_pass_settings_teacher', 'hall_pass_settings', 'admins', ['teacher_id'], ['id'])


def downgrade():
    # Drop foreign key constraints
    op.drop_constraint('fk_hall_pass_settings_teacher', 'hall_pass_settings', type_='foreignkey')
    op.drop_constraint('fk_banking_settings_teacher', 'banking_settings', type_='foreignkey')
    op.drop_constraint('fk_payroll_settings_teacher', 'payroll_settings', type_='foreignkey')
    op.drop_constraint('fk_rent_settings_teacher', 'rent_settings', type_='foreignkey')
    
    # Drop columns
    op.drop_column('hall_pass_settings', 'teacher_id')
    op.drop_column('banking_settings', 'teacher_id')
    op.drop_column('payroll_settings', 'teacher_id')
    op.drop_column('rent_settings', 'teacher_id')
