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
    required_bal_scope = {"id", "seat_id", "class_id"}
    # This guard asserts that reconciliation preserved a usable runtime shape. It
    # must accept BOTH balance-snapshot shapes, because the shape it sees depends
    # on how the database arrived here:
    #   - replaying real history: the pre-split shape, one row per seat carrying
    #     both accounts, which e6f7a8b9c0d1 later splits per DOM-LED-001 §2;
    #   - a bootstrapped database: 0001 materializes the CURRENT ORM schema, so
    #     the canonical per-account shape already exists by the time we get here.
    # Demanding only the pre-split columns made a present-day model change
    # retroactively break this historical step. e6f7a8b9c0d1 already tolerates
    # both shapes; this guard now does too.
    pre_split_bal = {"posted_checking_balance_cents", "posted_savings_balance_cents"}
    canonical_bal = {"account_type", "posted_balance_cents"}

    missing_tx = sorted(required_tx - tx_cols)
    missing_bal_scope = sorted(required_bal_scope - bal_cols)
    has_accounts = pre_split_bal.issubset(bal_cols) or canonical_bal.issubset(bal_cols)

    if missing_tx:
        raise RuntimeError(
            "ledger_transaction is missing required runtime columns after reconciliation: "
            + ", ".join(missing_tx)
        )
    if missing_bal_scope:
        raise RuntimeError(
            "ledger_balance_snapshot is missing required runtime columns after reconciliation: "
            + ", ".join(missing_bal_scope)
        )
    if not has_accounts:
        raise RuntimeError(
            "ledger_balance_snapshot carries neither the pre-split balance columns "
            f"({', '.join(sorted(pre_split_bal))}) nor the canonical per-account columns "
            f"({', '.join(sorted(canonical_bal))}) after reconciliation."
        )


def upgrade():
    _reconcile_table_pair(legacy_name="transaction", canonical_name="ledger_transaction")
    _reconcile_table_pair(legacy_name="balance_cache", canonical_name="ledger_balance_snapshot")
    _assert_expected_runtime_shape()


def downgrade():
    # No-op: this repair migration intentionally establishes canonical table names
    # and removes split-name drift. Reversing would reintroduce drift.
    pass
