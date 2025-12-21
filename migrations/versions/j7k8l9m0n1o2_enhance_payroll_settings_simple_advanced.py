"""Enhance payroll settings with simple and advanced modes

Revision ID: j7k8l9m0n1o2
Revises: i6j7k8l9m0n1
Create Date: 2025-11-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j7k8l9m0n1o2'
down_revision = 'i6j7k8l9m0n1'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns for enhanced payroll settings
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        # Settings mode
        batch_op.add_column(sa.Column('settings_mode', sa.String(20), nullable=False, server_default='simple'))

        # Simple mode fields
        batch_op.add_column(sa.Column('daily_limit_hours', sa.Float(), nullable=True))

        # Advanced mode fields
        batch_op.add_column(sa.Column('time_unit', sa.String(20), nullable=False, server_default='minutes'))
        batch_op.add_column(sa.Column('overtime_enabled', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('overtime_threshold', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('overtime_threshold_unit', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('overtime_threshold_period', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('max_time_per_day', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('max_time_per_day_unit', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('pay_schedule_type', sa.String(20), nullable=False, server_default='biweekly'))
        batch_op.add_column(sa.Column('pay_schedule_custom_value', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pay_schedule_custom_unit', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('first_pay_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('rounding_mode', sa.String(20), nullable=False, server_default='down'))


def downgrade():
    with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
        batch_op.drop_column('rounding_mode')
        batch_op.drop_column('first_pay_date')
        batch_op.drop_column('pay_schedule_custom_unit')
        batch_op.drop_column('pay_schedule_custom_value')
        batch_op.drop_column('pay_schedule_type')
        batch_op.drop_column('max_time_per_day_unit')
        batch_op.drop_column('max_time_per_day')
        batch_op.drop_column('overtime_threshold_period')
        batch_op.drop_column('overtime_threshold_unit')
        batch_op.drop_column('overtime_threshold')
        batch_op.drop_column('overtime_enabled')
        batch_op.drop_column('time_unit')
        batch_op.drop_column('daily_limit_hours')
        batch_op.drop_column('settings_mode')
