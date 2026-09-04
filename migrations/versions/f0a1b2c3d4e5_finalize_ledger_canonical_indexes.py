"""Finalize physical Ledger canonical indexes after e6f7a8b9c0d1."""

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns("ledger_transaction")}
    key_column = columns.get("idempotency_key")
    if key_column is not None and getattr(key_column["type"], "length", None) != 128:
        op.alter_column(
            "ledger_transaction", "idempotency_key",
            existing_type=key_column["type"], type_=sa.String(length=128),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("ledger_transaction")}
    if "uq_transaction_idempotency_scope" in indexes:
        op.drop_index("uq_transaction_idempotency_scope", table_name="ledger_transaction")
    if "ix_ledger_transaction_reconstruction_scope" not in indexes:
        op.create_index(
            "ix_ledger_transaction_reconstruction_scope", "ledger_transaction",
            ["class_id", "seat_id", "account_type", "posting_sequence", "status"],
        )


def downgrade():
    raise RuntimeError("Ledger canonical indexes are not safely reversible.")
