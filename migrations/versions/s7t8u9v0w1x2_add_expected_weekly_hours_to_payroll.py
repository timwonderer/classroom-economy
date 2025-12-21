"""Add expected_weekly_hours to PayrollSettings for economy balance

Revision ID: s7t8u9v0w1x2
Revises: aa5697e97c94
Create Date: 2025-12-08 08:00:00.000000

This field stores the expected hours per week that students attend class.
It is used ONLY for economy balance checking (CWI calculation), not for
actual payroll processing.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's7t8u9v0w1x2'
down_revision = 'aa5697e97c94'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add expected_weekly_hours column with default of 5.0 hours
    if not column_exists('payroll_settings', 'expected_weekly_hours'):
        with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('expected_weekly_hours', sa.Float(), nullable=True, server_default='5.0')
            )


def downgrade():
    # Remove expected_weekly_hours column
    if column_exists('payroll_settings', 'expected_weekly_hours'):
        with op.batch_alter_table('payroll_settings', schema=None) as batch_op:
            batch_op.drop_column('expected_weekly_hours')
