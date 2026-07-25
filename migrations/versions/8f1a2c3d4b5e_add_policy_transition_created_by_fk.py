"""add fk for policy_transitions.created_by

Revision ID: 8f1a2c3d4b5e
Revises: c4e36a4ab2f1
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8f1a2c3d4b5e"
down_revision = "c4e36a4ab2f1"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def upgrade():
    if table_exists("policy_transitions") and not foreign_key_exists(
        "policy_transitions",
        "fk_policy_transitions_created_by",
    ):
        with op.batch_alter_table("policy_transitions", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_policy_transitions_created_by",
                "users",
                ["created_by"],
                ["id"],
            )


def downgrade():
    if table_exists("policy_transitions") and foreign_key_exists(
        "policy_transitions",
        "fk_policy_transitions_created_by",
    ):
        with op.batch_alter_table("policy_transitions", schema=None) as batch_op:
            batch_op.drop_constraint("fk_policy_transitions_created_by", type_="foreignkey")
