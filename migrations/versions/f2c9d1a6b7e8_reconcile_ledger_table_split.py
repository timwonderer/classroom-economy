"""Reconcile split legacy/canonical ledger table names.

Revision ID: f2c9d1a6b7e8
Revises: c6a8f6d1e2b3
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c9d1a6b7e8"
down_revision = "c6a8f6d1e2b3"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def table_columns(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return {col["name"] for col in inspector.get_columns(table_name)}


def table_row_count(table_name):
    conn = op.get_bind()
    result = conn.execute(sa.text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
    return int(result or 0)


def _is_stub_shape(table_name):
    cols = table_columns(table_name)
    return cols == {"id", "created_at", "updated_at"}


def _reconcile_table_pair(*, legacy_name, canonical_name):
    legacy_exists = table_exists(legacy_name)
    canonical_exists = table_exists(canonical_name)

    if legacy_exists and not canonical_exists:
        op.rename_table(legacy_name, canonical_name)
        return

    if canonical_exists and not legacy_exists:
        return

    if not legacy_exists and not canonical_exists:
        return

    legacy_count = table_row_count(legacy_name)
    canonical_count = table_row_count(canonical_name)
    canonical_is_stub = _is_stub_shape(canonical_name)

    if legacy_count > 0 and canonical_count == 0:
        # Canonical table exists but is empty; legacy table carries real data.
        op.drop_table(canonical_name)
        op.rename_table(legacy_name, canonical_name)
        return

    if legacy_count == 0:
        # Legacy table is empty baggage; remove it.
        op.drop_table(legacy_name)
        return

    # Both tables are non-empty. Do not guess merge behavior.
    raise RuntimeError(
        f"Cannot reconcile {legacy_name}/{canonical_name}: both tables contain rows "
        f"(legacy={legacy_count}, canonical={canonical_count}, canonical_is_stub={canonical_is_stub})."
    )


def _assert_expected_runtime_shape():
    tx_cols = table_columns("ledger_transaction") if table_exists("ledger_transaction") else set()
    bal_cols = table_columns("ledger_balance_snapshot") if table_exists("ledger_balance_snapshot") else set()

    required_tx = {"id", "seat_id", "class_id", "amount", "timestamp", "status"}
    required_bal_legacy = {
        "id",
        "seat_id",
        "class_id",
        "posted_checking_balance_cents",
        "posted_savings_balance_cents",
    }
    required_bal_canonical = {
        "id",
        "seat_id",
        "class_id",
        "account_type",
        "posted_balance_cents",
    }

    missing_tx = sorted(required_tx - tx_cols)
    missing_bal = sorted(required_bal_legacy - bal_cols)

    if missing_tx:
        raise RuntimeError(
            "ledger_transaction is missing required runtime columns after reconciliation: "
            + ", ".join(missing_tx)
        )
    if not required_bal_legacy.issubset(bal_cols) and not required_bal_canonical.issubset(bal_cols):
        raise RuntimeError(
            "ledger_balance_snapshot is missing required legacy or canonical runtime columns after reconciliation: "
            + ", ".join(sorted(required_bal_legacy - bal_cols))
        )


def upgrade():
    _reconcile_table_pair(legacy_name="transaction", canonical_name="ledger_transaction")
    _reconcile_table_pair(legacy_name="balance_cache", canonical_name="ledger_balance_snapshot")
    _assert_expected_runtime_shape()


def downgrade():
    # No-op: this repair migration intentionally establishes canonical table names
    # and removes split-name drift. Reversing would reintroduce drift.
    pass
