"""Revamp rent feature with new settings and remove homeownership

Revision ID: k8l9m0n1o2p3
Revises: j7k8l9m0n1o2
Create Date: 2025-11-19 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k8l9m0n1o2p3'
down_revision = 'j7k8l9m0n1o2'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to rent_settings table
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        # Add frequency settings
        batch_op.add_column(sa.Column('frequency_type', sa.String(20), nullable=False, server_default='monthly'))
        batch_op.add_column(sa.Column('custom_frequency_value', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('custom_frequency_unit', sa.String(20), nullable=True))

        # Add first rent due date
        batch_op.add_column(sa.Column('first_rent_due_date', sa.DateTime(), nullable=True))

        # Rename late_fee to late_penalty_amount (keeping old column for compatibility)
        batch_op.add_column(sa.Column('late_penalty_amount', sa.Float(), nullable=False, server_default='10.0'))
        batch_op.add_column(sa.Column('late_penalty_type', sa.String(20), nullable=False, server_default='once'))
        batch_op.add_column(sa.Column('late_penalty_frequency_days', sa.Integer(), nullable=True))

        # Add bill preview and payment options
        batch_op.add_column(sa.Column('bill_preview_enabled', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('bill_preview_days', sa.Integer(), nullable=False, server_default='7'))
        batch_op.add_column(sa.Column('allow_incremental_payment', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('prevent_purchase_when_late', sa.Boolean(), nullable=False, server_default='0'))

    # Migrate data from late_fee to late_penalty_amount
    op.execute("""
        UPDATE rent_settings
        SET late_penalty_amount = COALESCE(late_fee, 10.0)
    """)

    # Create rent_waivers table
    op.create_table('rent_waivers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('waiver_start_date', sa.DateTime(), nullable=False),
        sa.Column('waiver_end_date', sa.DateTime(), nullable=False),
        sa.Column('periods_count', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_by_admin_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.ForeignKeyConstraint(['created_by_admin_id'], ['admins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Remove homeownership columns from students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('is_property_tax_enabled')
        batch_op.drop_column('owns_seat')


def downgrade():
    # Restore homeownership columns to students table
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owns_seat', sa.Boolean(), server_default='0'))
        batch_op.add_column(sa.Column('is_property_tax_enabled', sa.Boolean(), server_default='0'))

    # Drop rent_waivers table
    op.drop_table('rent_waivers')

    # Remove new columns from rent_settings table
    with op.batch_alter_table('rent_settings', schema=None) as batch_op:
        batch_op.drop_column('prevent_purchase_when_late')
        batch_op.drop_column('allow_incremental_payment')
        batch_op.drop_column('bill_preview_days')
        batch_op.drop_column('bill_preview_enabled')
        batch_op.drop_column('late_penalty_frequency_days')
        batch_op.drop_column('late_penalty_type')
        batch_op.drop_column('late_penalty_amount')
        batch_op.drop_column('first_rent_due_date')
        batch_op.drop_column('custom_frequency_unit')
        batch_op.drop_column('custom_frequency_value')
        batch_op.drop_column('frequency_type')
