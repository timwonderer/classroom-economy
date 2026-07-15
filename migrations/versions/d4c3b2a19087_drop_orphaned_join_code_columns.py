"""Drop orphaned join_code columns from v2 runtime tables.

Revision ID: d4c3b2a19087
Revises: 7c8d9e0f1122
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "d4c3b2a19087"
down_revision = "7c8d9e0f1122"
branch_labels = None
depends_on = None


TABLES_WITH_JOIN_CODE = (
    "saved_adjustments",
    "store_items",
    "store_item_blocks",
    "announcements",
    "issues",
    "issue_status_history",
    "issue_resolution_actions",
    "user_reports",
)


def table_exists(table_name):
    conn = op.get_bind()
    return table_name in sa.inspect(conn).get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}
    except Exception:
        return False


def drop_join_code_index(table_name):
    index_name = f"ix_{table_name}_join_code"
    if index_exists(table_name, index_name):
        op.drop_index(op.f(index_name), table_name=table_name)


def upgrade():
    for table_name in TABLES_WITH_JOIN_CODE:
        if not table_exists(table_name):
            continue

        drop_join_code_index(table_name)

        if column_exists(table_name, "join_code"):
            op.drop_column(table_name, "join_code")


def downgrade():
    for table_name in TABLES_WITH_JOIN_CODE:
        if not table_exists(table_name):
            continue

        if not column_exists(table_name, "join_code"):
            op.add_column(table_name, sa.Column("join_code", sa.String(length=20), nullable=True))

        drop_join_code_index(table_name)
        if column_exists(table_name, "join_code") and not index_exists(table_name, f"ix_{table_name}_join_code"):
            op.create_index(op.f(f"ix_{table_name}_join_code"), table_name, ["join_code"], unique=False)
