"""Add canonical actor/target ledger fields.

Revision ID: a1b2c3d4e5f7
Revises: 9f8e7d6c5b4a
Create Date: 2026-07-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "9f8e7d6c5b4a"
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


def upgrade():
    if table_exists("ledger_transaction"):
        if not column_exists("ledger_transaction", "target_seat_id"):
            op.add_column(
                "ledger_transaction",
                sa.Column("target_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="CASCADE"), nullable=True),
            )
        if not column_exists("ledger_transaction", "actor_seat_id"):
            op.add_column(
                "ledger_transaction",
                sa.Column("actor_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="CASCADE"), nullable=True),
            )
        if not column_exists("ledger_transaction", "mechanism"):
            op.add_column(
                "ledger_transaction",
                sa.Column("mechanism", sa.String(length=20), nullable=True, server_default="self"),
            )

        op.execute(
            sa.text(
                """
                UPDATE ledger_transaction
                SET target_seat_id = COALESCE(target_seat_id, seat_id),
                    actor_seat_id = COALESCE(actor_seat_id, seat_id),
                    mechanism = COALESCE(mechanism, 'self')
                """
            )
        )

        if not index_exists("ledger_transaction", "ix_transaction_class_scope"):
            op.create_index(
                "ix_transaction_class_scope",
                "ledger_transaction",
                ["class_id", "target_seat_id", "actor_seat_id", "account_type"],
                unique=False,
            )

        if index_exists("ledger_transaction", "uq_transaction_idempotency_scope"):
            op.drop_index("uq_transaction_idempotency_scope", table_name="ledger_transaction")
        op.create_index(
            "uq_transaction_idempotency_scope",
            "ledger_transaction",
            ["class_id", "target_seat_id", "feat_code", "idempotency_key", "type"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'"),
        )

        if not column_exists("ledger_transaction", "class_id"):
            op.add_column(
                "ledger_transaction",
                sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=True),
            )
        op.execute(
            sa.text(
                """
                UPDATE ledger_transaction
                SET class_id = COALESCE(
                    class_id,
                    (SELECT s.class_id FROM seats s WHERE s.id = ledger_transaction.target_seat_id LIMIT 1)
                )
                """
            )
        )

        with op.batch_alter_table("ledger_transaction") as batch_op:
            batch_op.alter_column("target_seat_id", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("actor_seat_id", existing_type=sa.Integer(), nullable=False)

    if table_exists("ledger_balance_snapshot"):
        if not column_exists("ledger_balance_snapshot", "reconciled_through_transaction_id"):
            op.add_column(
                "ledger_balance_snapshot",
                sa.Column("reconciled_through_transaction_id", sa.Integer(), nullable=True),
            )
        if not foreign_key_exists("ledger_balance_snapshot", "fk_ledger_balance_snapshot_reconciled_through_transaction_id"):
            with op.batch_alter_table("ledger_balance_snapshot") as batch_op:
                batch_op.create_foreign_key(
                    "fk_ledger_balance_snapshot_reconciled_through_transaction_id",
                    "ledger_transaction",
                    ["reconciled_through_transaction_id"],
                    ["id"],
                )


def downgrade():
    if table_exists("ledger_balance_snapshot"):
        if foreign_key_exists("ledger_balance_snapshot", "fk_ledger_balance_snapshot_reconciled_through_transaction_id"):
            with op.batch_alter_table("ledger_balance_snapshot") as batch_op:
                batch_op.drop_constraint(
                    "fk_ledger_balance_snapshot_reconciled_through_transaction_id",
                    type_="foreignkey",
                )
        if column_exists("ledger_balance_snapshot", "reconciled_through_transaction_id"):
            op.drop_column("ledger_balance_snapshot", "reconciled_through_transaction_id")

    if table_exists("ledger_transaction"):
        if index_exists("ledger_transaction", "uq_transaction_idempotency_scope"):
            op.drop_index("uq_transaction_idempotency_scope", table_name="ledger_transaction")
        if index_exists("ledger_transaction", "ix_transaction_class_scope"):
            op.drop_index("ix_transaction_class_scope", table_name="ledger_transaction")

        if column_exists("ledger_transaction", "mechanism"):
            op.drop_column("ledger_transaction", "mechanism")
        if column_exists("ledger_transaction", "actor_seat_id"):
            op.drop_column("ledger_transaction", "actor_seat_id")
        if column_exists("ledger_transaction", "target_seat_id"):
            op.drop_column("ledger_transaction", "target_seat_id")

        if not index_exists("ledger_transaction", "uq_transaction_idempotency_scope"):
            op.create_index(
                "uq_transaction_idempotency_scope",
                "ledger_transaction",
                ["class_id", "seat_id", "feat_code", "idempotency_key", "type"],
                unique=True,
                postgresql_where=sa.text("idempotency_key IS NOT NULL AND status != 'VOID'"),
            )
