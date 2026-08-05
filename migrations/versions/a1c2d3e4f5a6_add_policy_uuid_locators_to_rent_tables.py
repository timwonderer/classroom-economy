"""Add policy UUID locators to rent tables.

Revision ID: a1c2d3e4f5a6
Revises: e13a59b6aa6b
Create Date: 2026-08-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4


revision = "a1c2d3e4f5a6"
down_revision = "e13a59b6aa6b"
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


def _add_column_if_missing(table_name, column):
    if table_exists(table_name) and not column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade():
    if not table_exists("rent_settings"):
        return

    _add_column_if_missing(
        "rent_settings",
        sa.Column("policy_uuid", sa.String(length=36), nullable=True, index=True),
    )
    _add_column_if_missing(
        "bill_cycles",
        sa.Column("policy_uuid", sa.String(length=36), nullable=True, index=True),
    )
    _add_column_if_missing(
        "assessment_events",
        sa.Column("policy_uuid", sa.String(length=36), nullable=True, index=True),
    )

    conn = op.get_bind()
    rent_settings = sa.table(
        "rent_settings",
        sa.column("id", sa.Integer),
        sa.column("class_id", sa.String),
        sa.column("policy_uuid", sa.String),
    )
    bill_cycles = sa.table(
        "bill_cycles",
        sa.column("class_id", sa.String),
        sa.column("policy_uuid", sa.String),
    )
    assessment_events = sa.table(
        "assessment_events",
        sa.column("class_id", sa.String),
        sa.column("policy_uuid", sa.String),
    )

    rows = conn.execute(sa.select(rent_settings.c.class_id, rent_settings.c.policy_uuid)).all()
    class_policy_uuids = {}
    for class_id, policy_uuid in rows:
        if class_id and policy_uuid:
            class_policy_uuids[class_id] = policy_uuid

    for class_id, policy_uuid in list(class_policy_uuids.items()):
        conn.execute(
            sa.update(rent_settings)
            .where(rent_settings.c.class_id == class_id)
            .values(policy_uuid=policy_uuid)
        )

    for class_id in conn.execute(sa.select(rent_settings.c.class_id)).scalars().all():
        if class_id in class_policy_uuids:
            continue
        policy_uuid = str(uuid4())
        class_policy_uuids[class_id] = policy_uuid
        conn.execute(
            sa.update(rent_settings)
            .where(rent_settings.c.class_id == class_id)
            .values(policy_uuid=policy_uuid)
        )

    for class_id, policy_uuid in class_policy_uuids.items():
        conn.execute(
            sa.update(bill_cycles)
            .where(bill_cycles.c.class_id == class_id)
            .values(policy_uuid=policy_uuid)
        )
        conn.execute(
            sa.update(assessment_events)
            .where(assessment_events.c.class_id == class_id)
            .values(policy_uuid=policy_uuid)
        )

    if column_exists("rent_settings", "policy_uuid") and not index_exists("rent_settings", "ix_rent_settings_policy_uuid"):
        op.create_index("ix_rent_settings_policy_uuid", "rent_settings", ["policy_uuid"])
    if column_exists("bill_cycles", "policy_uuid") and not index_exists("bill_cycles", "ix_bill_cycles_policy_uuid"):
        op.create_index("ix_bill_cycles_policy_uuid", "bill_cycles", ["policy_uuid"])
    if column_exists("assessment_events", "policy_uuid") and not index_exists("assessment_events", "ix_assessment_events_policy_uuid"):
        op.create_index("ix_assessment_events_policy_uuid", "assessment_events", ["policy_uuid"])


def downgrade():
    if table_exists("assessment_events") and column_exists("assessment_events", "policy_uuid") and index_exists("assessment_events", "ix_assessment_events_policy_uuid"):
        op.drop_index("ix_assessment_events_policy_uuid", table_name="assessment_events")
        op.drop_column("assessment_events", "policy_uuid")

    if table_exists("bill_cycles") and column_exists("bill_cycles", "policy_uuid") and index_exists("bill_cycles", "ix_bill_cycles_policy_uuid"):
        op.drop_index("ix_bill_cycles_policy_uuid", table_name="bill_cycles")
        op.drop_column("bill_cycles", "policy_uuid")

    if table_exists("rent_settings") and column_exists("rent_settings", "policy_uuid") and index_exists("rent_settings", "ix_rent_settings_policy_uuid"):
        op.drop_index("ix_rent_settings_policy_uuid", table_name="rent_settings")
        op.drop_column("rent_settings", "policy_uuid")
