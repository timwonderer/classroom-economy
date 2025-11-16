"""Add rent system with per-period tracking

Revision ID: a1b2c3d4e5f6
Revises: merge_001
Create Date: 2025-11-16 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'merge_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create rent_settings table
    op.create_table('rent_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rent_amount', sa.Float(), nullable=True),
        sa.Column('due_day_of_month', sa.Integer(), nullable=True),
        sa.Column('late_fee', sa.Float(), nullable=True),
        sa.Column('grace_period_days', sa.Integer(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create rent_payments table with period tracking
    op.create_table('rent_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=10), nullable=False),  # e.g., 'A', 'B', 'C'
        sa.Column('amount_paid', sa.Float(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),  # Month (1-12)
        sa.Column('period_year', sa.Integer(), nullable=False),  # Year (e.g., 2025)
        sa.Column('payment_date', sa.DateTime(), nullable=True),
        sa.Column('was_late', sa.Boolean(), nullable=True),
        sa.Column('late_fee_charged', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Insert default rent settings
    op.execute(
        text(
            """
            INSERT INTO rent_settings (rent_amount, due_day_of_month, late_fee, grace_period_days, is_enabled, updated_at)
            VALUES (:rent_amount, :due_day, :late_fee, :grace_period, :enabled, CURRENT_TIMESTAMP)
            """
        ),
        {
            "rent_amount": 50.0,
            "due_day": 1,
            "late_fee": 10.0,
            "grace_period": 3,
            "enabled": True,
        },
    )


def downgrade():
    # Drop tables
    op.drop_table('rent_payments')
    op.drop_table('rent_settings')
