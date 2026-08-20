"""Drop payroll_settings.expected_weekly_hours (moved to economic_engine)

Revision ID: a4e8f19d7c31
Revises: 93de308c02c0
Create Date: 2026-08-15 11:00:00

Per DOM-CLASS-002, `expected_weekly_hours` is a CWI parameter that lives on the
canonical, immutable `economic_engine` table, not on `payroll_settings`. Mutation
occurs via FEAT-CLASS-005 (new engine version). This migration drops the duplicate
column from payroll_settings WITHOUT backfill. EconomicEngine is append-only, so
backfill would require new engine versions. This is pre-launch cleanup; teachers
re-enter the value through the EconomicEngine-backed UI.
"""
from alembic import op
import sqlalchemy as sa


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


revision = 'a4e8f19d7c31'
down_revision = '93de308c02c0'
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists('payroll_settings', 'expected_weekly_hours'):
        return

    # v2 pre-launch: no production data to migrate. The `economic_engine` table
    # enforces DB-level immutability (append-only), so backfill would require
    # inserting new versions. Since teachers must re-set the value through the
    # new EconomicEngine-backed UI anyway, we drop the column without backfill.
    with op.batch_alter_table('payroll_settings') as batch_op:
        batch_op.drop_column('expected_weekly_hours')


def downgrade():
    if column_exists('payroll_settings', 'expected_weekly_hours'):
        return

    with op.batch_alter_table('payroll_settings') as batch_op:
        batch_op.add_column(
            sa.Column('expected_weekly_hours', sa.Float(), nullable=True, server_default='5.0')
        )
