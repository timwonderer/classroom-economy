"""Create unified passkey_credentials table.

Revision ID: 6b7c8d9e0f11
Revises: c8f1e2d3a4b5
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "6b7c8d9e0f11"
down_revision = "c8f1e2d3a4b5"
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


def upgrade():
    if not table_exists("passkey_credentials"):
        op.create_table(
            "passkey_credentials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("credential_id", sa.Text(), nullable=True),
            sa.Column("authenticator_name", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_passkey_credentials_user_id", "passkey_credentials", ["user_id"])

    if table_exists("teacher_credentials") and column_exists("teacher_credentials", "user_id"):
        op.execute(
            sa.text(
                """
                INSERT INTO passkey_credentials (user_id, credential_id, authenticator_name, created_at, last_used)
                SELECT user_id, credential_id, authenticator_name, created_at, last_used
                FROM teacher_credentials
                WHERE user_id IS NOT NULL
                """
            )
        )

    if table_exists("system_admin_credentials") and column_exists("system_admin_credentials", "user_id"):
        op.execute(
            sa.text(
                """
                INSERT INTO passkey_credentials (user_id, credential_id, authenticator_name, created_at, last_used)
                SELECT user_id, credential_id, authenticator_name, created_at, last_used
                FROM system_admin_credentials
                WHERE user_id IS NOT NULL
                """
            )
        )


def downgrade():
    if table_exists("passkey_credentials"):
        op.drop_index("ix_passkey_credentials_user_id", table_name="passkey_credentials")
        op.drop_table("passkey_credentials")
