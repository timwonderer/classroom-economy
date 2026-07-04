"""Drop legacy students table

Revision ID: 9c1d2e3f4a5b
Revises: f84c7ad2c1aa
Create Date: 2026-07-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "9c1d2e3f4a5b"
down_revision = "f84c7ad2c1aa"
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
    except Exception:
        return False


def get_foreign_keys_referencing_table(target_table):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    refs = []
    for table_name in inspector.get_table_names():
        if table_name == target_table:
            continue
        try:
            for fk in inspector.get_foreign_keys(table_name):
                if fk.get("referred_table") == target_table and fk.get("name"):
                    refs.append((table_name, fk["name"]))
        except Exception:
            continue
    return refs


def drop_foreign_keys_referencing_table(target_table):
    for table_name, fk_name in get_foreign_keys_referencing_table(target_table):
        try:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")
        except Exception:
            pass


def upgrade():
    if table_exists("students"):
        drop_foreign_keys_referencing_table("students")
        op.drop_table("students")


def downgrade():
    if not table_exists("students"):
        op.create_table(
            "students",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("first_name", sa.LargeBinary(), nullable=False),
            sa.Column("last_initial", sa.String(length=1), nullable=False),
            sa.Column("identity_id", sa.Integer(), nullable=False, index=True),
            sa.Column("block", sa.String(length=10), nullable=False),
            sa.Column("join_code", sa.String(length=20), nullable=True, index=True),
            sa.Column("class_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("salt", sa.LargeBinary(length=16), nullable=False),
            sa.Column("first_half_hash", sa.String(length=64), nullable=True, unique=True),
            sa.Column("second_half_hash", sa.String(length=64), nullable=True, unique=True),
            sa.Column("username_hash", sa.String(length=64), nullable=True, unique=True),
            sa.Column("username_lookup_hash", sa.String(length=64), nullable=True, unique=True),
            sa.Column("pin_hash", sa.Text(), nullable=True),
            sa.Column("passphrase_hash", sa.Text(), nullable=True),
            sa.Column("hall_passes", sa.Integer(), nullable=True),
            sa.Column("is_rent_enabled", sa.Boolean(), nullable=True),
            sa.Column("insurance_plan", sa.String(), nullable=True),
            sa.Column("insurance_last_paid", sa.DateTime(timezone=True), nullable=True),
            sa.Column("second_factor_type", sa.String(), nullable=True),
            sa.Column("second_factor_enabled", sa.Boolean(), nullable=True),
            sa.Column("has_completed_setup", sa.Boolean(), nullable=True),
            sa.Column("has_completed_profile_migration", sa.Boolean(), nullable=True),
            sa.Column("is_teacher", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reset_code", sa.String(length=8), nullable=True, unique=True),
            sa.Column("reset_code_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("money_action_cooldown_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recovery_status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("internal_reference", sa.String(length=64), nullable=False, index=True),
            sa.Column("opaque_reference", sa.String(length=64), nullable=False, index=True),
            sa.ForeignKeyConstraint(["identity_id"], ["identity_profiles.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
        )

