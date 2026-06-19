"""Drop RentSettings legacy scope columns

Revision ID: 3c7d9e1f2a43
Revises: 2a4f6c8d0e21
Create Date: 2026-06-05 12:05:00.000000

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
revision = "3c7d9e1f2a43"
down_revision = "2a4f6c8d0e21"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("rent_settings"):
        return

    op.execute("DROP POLICY IF EXISTS rent_settings_tenant_isolation_select ON rent_settings")
    op.execute("DROP POLICY IF EXISTS rent_settings_tenant_isolation_insert ON rent_settings")
    op.execute("DROP POLICY IF EXISTS rent_settings_tenant_isolation_update ON rent_settings")
    op.execute("DROP POLICY IF EXISTS rent_settings_tenant_isolation_delete ON rent_settings")

    if index_exists("rent_settings", "ix_rent_settings_join_code"):
        op.drop_index(op.f("ix_rent_settings_join_code"), table_name="rent_settings")
    if index_exists("rent_settings", "ix_rent_settings_teacher_id"):
        op.drop_index(op.f("ix_rent_settings_teacher_id"), table_name="rent_settings")

    for fk in get_foreign_keys_by_column("rent_settings", "teacher_id"):
        op.drop_constraint(fk["name"], "rent_settings", type_="foreignkey")

    if column_exists("rent_settings", "class_id"):
        op.alter_column("rent_settings", "class_id", existing_type=sa.String(length=36), nullable=False)

    if column_exists("rent_settings", "join_code"):
        op.drop_column("rent_settings", "join_code")
    if column_exists("rent_settings", "teacher_id"):
        op.drop_column("rent_settings", "teacher_id")


def downgrade():
    if not table_exists("rent_settings"):
        return

    if not column_exists("rent_settings", "teacher_id"):
        op.add_column(
            "rent_settings",
            sa.Column("teacher_id", sa.INTEGER(), autoincrement=False, nullable=True),
        )
    if not column_exists("rent_settings", "join_code"):
        op.add_column(
            "rent_settings",
            sa.Column("join_code", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        )

    if column_exists("rent_settings", "class_id"):
        op.alter_column("rent_settings", "class_id", existing_type=sa.String(length=36), nullable=True)

    if not index_exists("rent_settings", "ix_rent_settings_teacher_id"):
        op.create_index(op.f("ix_rent_settings_teacher_id"), "rent_settings", ["teacher_id"], unique=False)
    if not index_exists("rent_settings", "ix_rent_settings_join_code"):
        op.create_index(op.f("ix_rent_settings_join_code"), "rent_settings", ["join_code"], unique=False)

    if not get_foreign_keys_by_column("rent_settings", "teacher_id"):
        op.create_foreign_key(
            op.f("fk_rent_settings_teacher_id_teachers"),
            "rent_settings",
            "teachers",
            ["teacher_id"],
            ["id"],
        )
