"""Add canonical identity profile last name and notes fields.

Revision ID: 0a1b2c3d4e5f
Revises: f7b8c9d0e1f2
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0a1b2c3d4e5f"
down_revision = "f7b8c9d0e1f2"
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [column["name"] for column in inspector.get_columns(table_name)]
    except Exception:
        return False
    return column_name in columns


def upgrade():
    if not column_exists("identity_profiles", "last_name"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.add_column(sa.Column("last_name", sa.LargeBinary(), nullable=False))

    if not column_exists("identity_profiles", "notes"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.add_column(sa.Column("notes", sa.LargeBinary(), nullable=True))

    if column_exists("identity_profiles", "last_initial"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.drop_column("last_initial")

    if column_exists("redemption_audit_logs", "student_display_name"):
        with op.batch_alter_table("redemption_audit_logs") as batch_op:
            batch_op.drop_column("student_display_name")

    with op.batch_alter_table("issues") as batch_op:
        if column_exists("issues", "student_first_name"):
            batch_op.drop_column("student_first_name")
        if column_exists("issues", "student_last_initial"):
            batch_op.drop_column("student_last_initial")


def downgrade():
    if not column_exists("redemption_audit_logs", "student_display_name"):
        with op.batch_alter_table("redemption_audit_logs") as batch_op:
            batch_op.add_column(sa.Column("student_display_name", sa.String(length=120), nullable=False))

    with op.batch_alter_table("issues") as batch_op:
        if not column_exists("issues", "student_first_name"):
            batch_op.add_column(sa.Column("student_first_name", sa.String(length=100), nullable=False))
        if not column_exists("issues", "student_last_initial"):
            batch_op.add_column(sa.Column("student_last_initial", sa.String(length=1), nullable=False))

    if column_exists("identity_profiles", "notes"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.drop_column("notes")

    if not column_exists("identity_profiles", "last_initial"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.add_column(sa.Column("last_initial", sa.String(length=1), nullable=False))

    if column_exists("identity_profiles", "last_name"):
        with op.batch_alter_table("identity_profiles") as batch_op:
            batch_op.drop_column("last_name")
