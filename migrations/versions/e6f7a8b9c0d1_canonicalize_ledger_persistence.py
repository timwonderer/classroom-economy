"""Canonicalize Ledger persistence (DOM-LED-001 / SPEC-LED-002).

The repository's development database is pre-production and currently contains
no Ledger data.  The upgrade remains conservative for any historical rows: the
legacy snapshot's checking row is retained as the canonical checking row and a
savings row is created only when its legacy savings projection is non-zero.
Historical transactions remain without a posting sequence or reservation link.
"""
from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def _columns(table_name):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade():
    tx_columns = _columns("ledger_transaction")
    tx_column_info = {
        column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("ledger_transaction")
    }
    idempotency_column = tx_column_info.get("idempotency_key")
    if idempotency_column is not None and getattr(idempotency_column["type"], "length", None) != 128:
        op.alter_column(
            "ledger_transaction", "idempotency_key",
            existing_type=idempotency_column["type"], type_=sa.String(length=128),
        )
    if "posting_sequence" not in tx_columns:
        op.add_column("ledger_transaction", sa.Column("posting_sequence", sa.BigInteger(), nullable=True))
    if "command_reservation_id" not in tx_columns:
        op.add_column("ledger_transaction", sa.Column("command_reservation_id", sa.Integer(), nullable=True))
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("ledger_transaction")}
    if "uq_transaction_idempotency_scope" in indexes:
        op.drop_index("uq_transaction_idempotency_scope", table_name="ledger_transaction")
        indexes.remove("uq_transaction_idempotency_scope")
    if "ix_ledger_transaction_posting_sequence" not in indexes:
        op.create_index("ix_ledger_transaction_posting_sequence", "ledger_transaction", ["posting_sequence"])
    if "ix_ledger_transaction_command_reservation_id" not in indexes:
        op.create_index("ix_ledger_transaction_command_reservation_id", "ledger_transaction", ["command_reservation_id"])
    if "ix_ledger_transaction_reconstruction_scope" not in indexes:
        op.create_index(
            "ix_ledger_transaction_reconstruction_scope", "ledger_transaction",
            ["class_id", "seat_id", "account_type", "posting_sequence", "status"],
        )
    if "ledger_command_reservation" not in inspector.get_table_names():
        op.create_table(
            "ledger_command_reservation",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("feat_code", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("replay_fingerprint", sa.String(length=128), nullable=False),
            sa.Column("fingerprint_version", sa.Integer(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
            sa.UniqueConstraint("class_id", "feat_code", "idempotency_key", name="uq_ledger_command_reservation_identity"),
        )
    foreign_keys = {fk.get("name") for fk in sa.inspect(op.get_bind()).get_foreign_keys("ledger_transaction")}
    if "fk_ledger_transaction_command_reservation" not in foreign_keys:
        op.create_foreign_key(
            "fk_ledger_transaction_command_reservation", "ledger_transaction",
            "ledger_command_reservation", ["command_reservation_id"], ["id"], ondelete="RESTRICT"
        )

    snapshot_columns = _columns("ledger_balance_snapshot")
    if "account_type" in snapshot_columns:
        constraints = {constraint.get("name") for constraint in sa.inspect(op.get_bind()).get_unique_constraints("ledger_balance_snapshot")}
        if "uq_balance_snapshot_scope" not in constraints:
            op.create_unique_constraint("uq_balance_snapshot_scope", "ledger_balance_snapshot", ["class_id", "seat_id", "account_type"])
        return
    op.add_column("ledger_balance_snapshot", sa.Column("account_type", sa.String(length=20), nullable=True))
    op.add_column("ledger_balance_snapshot", sa.Column("posted_balance_cents", sa.Integer(), nullable=True))
    op.add_column("ledger_balance_snapshot", sa.Column("reconciled_through_posting_sequence", sa.BigInteger(), nullable=True))
    op.execute(sa.text("""
        UPDATE ledger_balance_snapshot
        SET account_type = 'checking',
            posted_balance_cents = posted_checking_balance_cents
        WHERE account_type IS NULL
    """))
    op.execute(sa.text("""
        INSERT INTO ledger_balance_snapshot
            (seat_id, class_id, join_code, account_type, posted_balance_cents,
             reconciled_through_posting_sequence, last_settlement_at, updated_at)
        SELECT seat_id, class_id, join_code, 'savings', posted_savings_balance_cents,
               NULL, last_settlement_at, updated_at
        FROM ledger_balance_snapshot
        WHERE posted_savings_balance_cents <> 0
    """))
    op.alter_column("ledger_balance_snapshot", "account_type", nullable=False)
    op.alter_column("ledger_balance_snapshot", "posted_balance_cents", nullable=False)
    op.drop_constraint("uq_balance_cache_seat_universe", "ledger_balance_snapshot", type_="unique")
    op.drop_column("ledger_balance_snapshot", "posted_checking_balance_cents")
    op.drop_column("ledger_balance_snapshot", "posted_savings_balance_cents")
    op.create_unique_constraint(
        "uq_balance_snapshot_scope", "ledger_balance_snapshot", ["class_id", "seat_id", "account_type"]
    )


def downgrade():
    raise RuntimeError("Canonical Ledger persistence is not safely reversible after canonical effects exist.")
