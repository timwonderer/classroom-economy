"""Add payroll settings, rewards, and fines tables

Revision ID: i6j7k8l9m0n1
Revises: merge_staging_and_hall_pass_branches
Create Date: 2025-11-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i6j7k8l9m0n1'
down_revision = 'merge_staging_and_hall_pass_branches'
branch_labels = None
depends_on = None


def upgrade():
    # Create payroll_settings table
    op.create_table('payroll_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('block', sa.String(length=10), nullable=True),
        sa.Column('pay_rate', sa.Float(), nullable=False),
        sa.Column('payroll_frequency_days', sa.Integer(), nullable=False),
        sa.Column('next_payroll_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('overtime_multiplier', sa.Float(), nullable=True),
        sa.Column('bonus_rate', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create payroll_rewards table
    op.create_table('payroll_rewards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create payroll_fines table
    op.create_table('payroll_fines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('payroll_fines')
    op.drop_table('payroll_rewards')
    op.drop_table('payroll_settings')
