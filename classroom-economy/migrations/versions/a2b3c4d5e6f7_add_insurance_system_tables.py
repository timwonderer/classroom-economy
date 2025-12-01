"""Add insurance system tables

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-16 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Create insurance_policies table
    op.create_table('insurance_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('premium', sa.Float(), nullable=False),
        sa.Column('charge_frequency', sa.String(length=20), nullable=True),
        sa.Column('autopay', sa.Boolean(), nullable=True),
        sa.Column('waiting_period_days', sa.Integer(), nullable=True),
        sa.Column('max_claims_count', sa.Integer(), nullable=True),
        sa.Column('max_claims_period', sa.String(length=20), nullable=True),
        sa.Column('max_claim_amount', sa.Float(), nullable=True),
        sa.Column('no_repurchase_after_cancel', sa.Boolean(), nullable=True),
        sa.Column('repurchase_wait_days', sa.Integer(), nullable=True),
        sa.Column('auto_cancel_nonpay_days', sa.Integer(), nullable=True),
        sa.Column('claim_time_limit_days', sa.Integer(), nullable=True),
        sa.Column('bundle_with_policy_ids', sa.Text(), nullable=True),
        sa.Column('bundle_discount_percent', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create student_insurance table
    op.create_table('student_insurance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('purchase_date', sa.DateTime(), nullable=True),
        sa.Column('cancel_date', sa.DateTime(), nullable=True),
        sa.Column('last_payment_date', sa.DateTime(), nullable=True),
        sa.Column('next_payment_due', sa.DateTime(), nullable=True),
        sa.Column('coverage_start_date', sa.DateTime(), nullable=True),
        sa.Column('payment_current', sa.Boolean(), nullable=True),
        sa.Column('days_unpaid', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['policy_id'], ['insurance_policies.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create insurance_claims table
    op.create_table('insurance_claims',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_insurance_id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('incident_date', sa.DateTime(), nullable=False),
        sa.Column('filed_date', sa.DateTime(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('claim_amount', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('approved_amount', sa.Float(), nullable=True),
        sa.Column('processed_date', sa.DateTime(), nullable=True),
        sa.Column('processed_by_admin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['policy_id'], ['insurance_policies.id'], ),
        sa.ForeignKeyConstraint(['processed_by_admin_id'], ['admins.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.ForeignKeyConstraint(['student_insurance_id'], ['student_insurance.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('insurance_claims')
    op.drop_table('student_insurance')
    op.drop_table('insurance_policies')
