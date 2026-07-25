"""Add entitlement event correlation id.

Revision ID: f7c8d9e0f1a3
Revises: f6a7b8c9d0e2
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f7c8d9e0f1a3"
down_revision = "f6a7b8c9d0e2"
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


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))
    except sa.exc.NoSuchTableError:
        return False


def upgrade():
    if not table_exists("entitlement_events"):
        return

    if not column_exists("entitlement_events", "correlation_id"):
        op.add_column(
            "entitlement_events",
            sa.Column("correlation_id", sa.String(length=100), nullable=True),
        )

    if not index_exists("entitlement_events", "ix_entitlement_events_correlation_id"):
        op.create_index(
            "ix_entitlement_events_correlation_id",
            "entitlement_events",
            ["correlation_id"],
        )


def downgrade():
    if not table_exists("entitlement_events"):
        return

    if index_exists("entitlement_events", "ix_entitlement_events_correlation_id"):
        op.drop_index("ix_entitlement_events_correlation_id", table_name="entitlement_events")

    if column_exists("entitlement_events", "correlation_id"):
        op.drop_column("entitlement_events", "correlation_id")
