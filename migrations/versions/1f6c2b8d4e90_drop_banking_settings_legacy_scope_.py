"""Drop BankingSettings legacy scope columns

Revision ID: 1f6c2b8d4e90
Revises: e0babef88934
Create Date: 2026-06-05 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


# revision identifiers, used by Alembic.
revision = "1f6c2b8d4e90"
down_revision = "e0babef88934"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("banking_settings"):
        return

    op.execute("DROP POLICY IF EXISTS banking_settings_tenant_isolation_select ON banking_settings")
    op.execute("DROP POLICY IF EXISTS banking_settings_tenant_isolation_insert ON banking_settings")
    op.execute("DROP POLICY IF EXISTS banking_settings_tenant_isolation_update ON banking_settings")
    op.execute("DROP POLICY IF EXISTS banking_settings_tenant_isolation_delete ON banking_settings")

    if index_exists("banking_settings", "ix_banking_settings_join_code"):
        op.drop_index(op.f("ix_banking_settings_join_code"), table_name="banking_settings")
    if index_exists("banking_settings", "ix_banking_settings_teacher_id"):
        op.drop_index(op.f("ix_banking_settings_teacher_id"), table_name="banking_settings")

    for fk in get_foreign_keys_by_column("banking_settings", "teacher_id"):
        op.drop_constraint(fk["name"], "banking_settings", type_="foreignkey")

    if column_exists("banking_settings", "join_code"):
        op.drop_column("banking_settings", "join_code")
    if column_exists("banking_settings", "teacher_id"):
        op.drop_column("banking_settings", "teacher_id")


def downgrade():
    if not table_exists("banking_settings"):
        return

    if not column_exists("banking_settings", "teacher_id"):
        op.add_column(
            "banking_settings",
            sa.Column("teacher_id", sa.INTEGER(), autoincrement=False, nullable=True),
        )
    if not column_exists("banking_settings", "join_code"):
        op.add_column(
            "banking_settings",
            sa.Column("join_code", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        )

    if not index_exists("banking_settings", "ix_banking_settings_teacher_id"):
        op.create_index(
            op.f("ix_banking_settings_teacher_id"),
            "banking_settings",
            ["teacher_id"],
            unique=False,
        )
    if not index_exists("banking_settings", "ix_banking_settings_join_code"):
        op.create_index(
            op.f("ix_banking_settings_join_code"),
            "banking_settings",
            ["join_code"],
            unique=False,
        )

    if not get_foreign_keys_by_column("banking_settings", "teacher_id"):
        op.create_foreign_key(
            op.f("fk_banking_settings_teacher_id_teachers"),
            "banking_settings",
            "teachers",
            ["teacher_id"],
            ["id"],
        )
