"""Restrict payroll event policy version deletion.

Revision ID: f6a7b8c9d0e2
Revises: e5f6a7b8c9d0
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))
    except sa.exc.NoSuchTableError:
        return False


def foreign_keys_for_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk
            for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk.get("constrained_columns", [])
        ]
    except sa.exc.NoSuchTableError:
        return []


def upgrade():
    if not (
        table_exists("payroll_event")
        and table_exists("policy_versions")
        and column_exists("payroll_event", "policy_version_id")
    ):
        return

    for fk in foreign_keys_for_column("payroll_event", "policy_version_id"):
        op.drop_constraint(fk["name"], "payroll_event", type_="foreignkey")

    if "fk_payroll_event_policy_version_id" not in {
        fk["name"]
        for fk in foreign_keys_for_column("payroll_event", "policy_version_id")
        if fk.get("name")
    }:
        op.create_foreign_key(
            "fk_payroll_event_policy_version_id",
            "payroll_event",
            "policy_versions",
            ["policy_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade():
    if not (
        table_exists("payroll_event")
        and table_exists("policy_versions")
        and column_exists("payroll_event", "policy_version_id")
    ):
        return

    for fk in foreign_keys_for_column("payroll_event", "policy_version_id"):
        op.drop_constraint(fk["name"], "payroll_event", type_="foreignkey")

    if "fk_payroll_event_policy_version_id" not in {
        fk["name"]
        for fk in foreign_keys_for_column("payroll_event", "policy_version_id")
        if fk.get("name")
    }:
        op.create_foreign_key(
            "fk_payroll_event_policy_version_id",
            "payroll_event",
            "policy_versions",
            ["policy_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
