"""repoint obligation assessment policy version to policy_versions

Revision ID: a1b2c3d4e5f6
Revises: 7c3d4e5f6a7b
Create Date: 2026-07-16

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "7c3d4e5f6a7b"
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
        return column_name in [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx["name"] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
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


def upgrade():
    if not table_exists("assessment_events"):
        return

    for fk in get_foreign_keys_by_column("assessment_events", "rent_policy_version_id"):
        if fk.get("name"):
            op.drop_constraint(fk["name"], "assessment_events", type_="foreignkey")

    if column_exists("assessment_events", "rent_policy_version_id") and not column_exists("assessment_events", "policy_version_id"):
        with op.batch_alter_table("assessment_events", schema=None) as batch_op:
            batch_op.alter_column(
                "rent_policy_version_id",
                new_column_name="policy_version_id",
            )
    elif not column_exists("assessment_events", "policy_version_id"):
        with op.batch_alter_table("assessment_events", schema=None) as batch_op:
            batch_op.add_column(sa.Column("policy_version_id", sa.Integer(), nullable=True))

    if column_exists("assessment_events", "policy_version_id") and not index_exists("assessment_events", "ix_assessment_events_policy_version_id"):
        op.create_index(
            "ix_assessment_events_policy_version_id",
            "assessment_events",
            ["policy_version_id"],
            unique=False,
        )

    if column_exists("assessment_events", "policy_version_id") and not foreign_key_exists("assessment_events", "fk_assessment_events_policy_version_id"):
        with op.batch_alter_table("assessment_events", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_assessment_events_policy_version_id",
                "policy_versions",
                ["policy_version_id"],
                ["id"],
            )


def downgrade():
    raise NotImplementedError(
        "Downgrade is intentionally unsupported for this constitutional schema "
        "remediation. Reverting this change would require a full code rollback."
    )
