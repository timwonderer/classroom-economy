"""add entitlement lineage to redemption events

Revision ID: 2c3d4e5f6a7b
Revises: 7a9b8c6d5e4f
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa


revision = "2c3d4e5f6a7b"
down_revision = "7a9b8c6d5e4f"
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade():
    if not column_exists("redemption_events", "entitlement_id"):
        with op.batch_alter_table("redemption_events", schema=None) as batch_op:
            batch_op.add_column(sa.Column("entitlement_id", sa.String(length=36), nullable=True))
            batch_op.create_foreign_key(
                "fk_redemption_events_entitlement_id",
                "entitlements",
                ["entitlement_id"],
                ["entitlement_id"],
            )
            batch_op.create_index("ix_redemption_events_entitlement_id", ["entitlement_id"], unique=False)


def downgrade():
    if column_exists("redemption_events", "entitlement_id"):
        with op.batch_alter_table("redemption_events", schema=None) as batch_op:
            batch_op.drop_index("ix_redemption_events_entitlement_id")
            batch_op.drop_constraint("fk_redemption_events_entitlement_id", type_="foreignkey")
            batch_op.drop_column("entitlement_id")
