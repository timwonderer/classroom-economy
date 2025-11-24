"""Add teacher_id to settings tables for multi-tenancy isolation

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2025-11-24 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'w2x3y4z5a6b7'
down_revision = 'v1w2x3y4z5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Add teacher_id to BankingSettings
    op.add_column(
        'banking_settings',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_banking_settings_teacher_id',
        'banking_settings', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to RentSettings
    op.add_column(
        'rent_settings',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_rent_settings_teacher_id',
        'rent_settings', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to PayrollSettings
    op.add_column(
        'payroll_settings',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_payroll_settings_teacher_id',
        'payroll_settings', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to PayrollReward
    op.add_column(
        'payroll_rewards',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_payroll_rewards_teacher_id',
        'payroll_rewards', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to PayrollFine
    op.add_column(
        'payroll_fines',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_payroll_fines_teacher_id',
        'payroll_fines', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to StoreItem
    op.add_column(
        'store_items',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_store_items_teacher_id',
        'store_items', 'admins',
        ['teacher_id'], ['id']
    )

    # Add teacher_id to HallPassSettings
    op.add_column(
        'hall_pass_settings',
        sa.Column('teacher_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_hall_pass_settings_teacher_id',
        'hall_pass_settings', 'admins',
        ['teacher_id'], ['id']
    )

    # Data migration: assign all existing records to the first admin
    # This prevents immediate breakage, but teachers should be notified to set up their own settings
    conn = op.get_bind()

    # Get the first admin ID
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.fetchone()

    if first_admin_id:
        first_admin_id = first_admin_id[0]

        # Update all existing settings to belong to the first admin (using parameterized queries)
        conn.execute(sa.text("UPDATE banking_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE rent_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE payroll_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE payroll_rewards SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE payroll_fines SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE store_items SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        conn.execute(sa.text("UPDATE hall_pass_settings SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        
        # Also backfill insurance_policies if they have NULL teacher_id
        # This ensures insurance policies are ready for RLS in the next migration
        conn.execute(sa.text("UPDATE insurance_policies SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})

    # Make teacher_id NOT NULL after data migration
    op.alter_column('banking_settings', 'teacher_id', nullable=False)
    op.alter_column('rent_settings', 'teacher_id', nullable=False)
    op.alter_column('payroll_settings', 'teacher_id', nullable=False)
    op.alter_column('payroll_rewards', 'teacher_id', nullable=False)
    op.alter_column('payroll_fines', 'teacher_id', nullable=False)
    op.alter_column('store_items', 'teacher_id', nullable=False)
    op.alter_column('hall_pass_settings', 'teacher_id', nullable=False)


def downgrade():
    # Remove foreign keys first
    op.drop_constraint('fk_hall_pass_settings_teacher_id', 'hall_pass_settings', type_='foreignkey')
    op.drop_constraint('fk_store_items_teacher_id', 'store_items', type_='foreignkey')
    op.drop_constraint('fk_payroll_fines_teacher_id', 'payroll_fines', type_='foreignkey')
    op.drop_constraint('fk_payroll_rewards_teacher_id', 'payroll_rewards', type_='foreignkey')
    op.drop_constraint('fk_payroll_settings_teacher_id', 'payroll_settings', type_='foreignkey')
    op.drop_constraint('fk_rent_settings_teacher_id', 'rent_settings', type_='foreignkey')
    op.drop_constraint('fk_banking_settings_teacher_id', 'banking_settings', type_='foreignkey')

    # Drop columns
    op.drop_column('hall_pass_settings', 'teacher_id')
    op.drop_column('store_items', 'teacher_id')
    op.drop_column('payroll_fines', 'teacher_id')
    op.drop_column('payroll_rewards', 'teacher_id')
    op.drop_column('payroll_settings', 'teacher_id')
    op.drop_column('rent_settings', 'teacher_id')
    op.drop_column('banking_settings', 'teacher_id')
