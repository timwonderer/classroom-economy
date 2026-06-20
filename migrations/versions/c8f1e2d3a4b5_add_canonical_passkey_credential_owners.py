"""Add canonical user owners to passkey credential metadata.

Revision ID: c8f1e2d3a4b5
Revises: b7e4c1d9a2f6
Create Date: 2026-06-04

Passkey credentials are authentication capability metadata. Their canonical
owner is users.id; legacy teacher/sysadmin IDs remain route compatibility
shadows during the v2 identity cutover.
"""

from alembic import op
import sqlalchemy as sa


revision = "c8f1e2d3a4b5"
down_revision = "b7e4c1d9a2f6"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def foreign_key_exists(table_name: str, fk_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def index_exists(table_name: str, index_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _execute(query: str) -> None:
    op.get_bind().execute(sa.text(query))


def _unmapped_count(table_name: str) -> int:
    return int(
        op.get_bind()
        .execute(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE user_id IS NULL
                """
            )
        )
        .scalar_one()
    )


def upgrade():
    if table_exists("teacher_credentials") and not column_exists("teacher_credentials", "user_id"):
        op.add_column("teacher_credentials", sa.Column("user_id", sa.Integer(), nullable=True))
    if table_exists("system_admin_credentials") and not column_exists("system_admin_credentials", "user_id"):
        op.add_column("system_admin_credentials", sa.Column("user_id", sa.Integer(), nullable=True))

    if table_exists("teacher_credentials") and not index_exists("teacher_credentials", "ix_teacher_credentials_user_id"):
        op.create_index("ix_teacher_credentials_user_id", "teacher_credentials", ["user_id"])
    if table_exists("system_admin_credentials") and not index_exists("system_admin_credentials", "ix_system_admin_credentials_user_id"):
        op.create_index("ix_system_admin_credentials_user_id", "system_admin_credentials", ["user_id"])

    if table_exists("teacher_credentials") and not foreign_key_exists("teacher_credentials", "fk_teacher_credentials_user_id_users"):
        op.create_foreign_key(
            "fk_teacher_credentials_user_id_users",
            "teacher_credentials",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    if table_exists("system_admin_credentials") and not foreign_key_exists("system_admin_credentials", "fk_system_admin_credentials_user_id_users"):
        op.create_foreign_key(
            "fk_system_admin_credentials_user_id_users",
            "system_admin_credentials",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    if table_exists("teacher_credentials") and column_exists("teacher_credentials", "teacher_id"):
        _execute(
            """
            UPDATE teacher_credentials tc
            SET user_id = u.id
            FROM teachers t
            JOIN users u
              ON u.username_lookup_hash = t.username_lookup_hash
             AND u.user_role = 'teacher'
            WHERE tc.teacher_id = t.id
              AND tc.user_id IS NULL
            """
        )
        if _unmapped_count("teacher_credentials"):
            raise RuntimeError(
                "Canonical passkey credential migration found teacher credentials "
                "without a canonical teacher user."
            )

    if table_exists("system_admin_credentials"):
        _execute(
            """
            UPDATE system_admin_credentials sac
            SET user_id = u.id
            FROM system_admins sa
            JOIN users u
              ON u.username_lookup_hash = sa.username_lookup_hash
             AND u.user_role = 'sysadmin'
            WHERE sac.sysadmin_id = sa.id
              AND sac.user_id IS NULL
            """
        )
        if _unmapped_count("system_admin_credentials"):
            raise RuntimeError(
                "Canonical passkey credential migration found system-admin credentials "
                "without a canonical sysadmin user."
            )


def downgrade():
    if table_exists("system_admin_credentials") and foreign_key_exists("system_admin_credentials", "fk_system_admin_credentials_user_id_users"):
        op.drop_constraint("fk_system_admin_credentials_user_id_users", "system_admin_credentials", type_="foreignkey")
    if table_exists("teacher_credentials") and foreign_key_exists("teacher_credentials", "fk_teacher_credentials_user_id_users"):
        op.drop_constraint("fk_teacher_credentials_user_id_users", "teacher_credentials", type_="foreignkey")

    if table_exists("system_admin_credentials") and index_exists("system_admin_credentials", "ix_system_admin_credentials_user_id"):
        op.drop_index("ix_system_admin_credentials_user_id", table_name="system_admin_credentials")
    if table_exists("teacher_credentials") and index_exists("teacher_credentials", "ix_teacher_credentials_user_id"):
        op.drop_index("ix_teacher_credentials_user_id", table_name="teacher_credentials")

    if table_exists("system_admin_credentials") and column_exists("system_admin_credentials", "user_id"):
        op.drop_column("system_admin_credentials", "user_id")
    if table_exists("teacher_credentials") and column_exists("teacher_credentials", "user_id"):
        op.drop_column("teacher_credentials", "user_id")
# CI trigger
