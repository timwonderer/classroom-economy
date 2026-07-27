"""Align Wave 7 obligations tables with the canonical schema contract.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "cda78c55185e"
branch_labels = None
depends_on = None


def table_exists(table_name):
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def column_exists(table_name, column_name):
    try:
        return column_name in {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns(table_name)
        }
    except Exception:
        return False


def index_exists(table_name, index_name):
    try:
        return index_name in {
            index["name"]
            for index in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    try:
        return fk_name in {
            foreign_key["name"]
            for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        }
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    try:
        return [
            foreign_key
            for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
            if column_name in foreign_key["constrained_columns"]
        ]
    except Exception:
        return []


def _assessment_columns():
    """Get canonical assessment columns that exist in the target schema."""
    # All possible legacy columns that might exist
    all_columns = [
        "id",
        "seat_id",
        "class_id",
        "join_code",
        "period",
        "obligation_type",
        "due_at",
        "assessed_at",
        "period_key",
        "coverage_start_time",
        "coverage_end_time",
        "cycle_idempotency_key",
        "period_month",
        "period_year",
        "coverage_month",
        "coverage_year",
        "internal_ref",
        "correlation_id",
        "event_type",
        "policy_version_id",
        "viewable_at",
        "created_at",
        "bill_cycle_id",
        "ledger_transaction_id",
    ]
    return all_columns


def _copy_missing_assessments(source_table, target_table):
    """Copy missing assessments, only including columns that exist in both tables."""
    # Get all columns from _assessment_columns and filter to only those that exist in BOTH source and target
    all_columns = _assessment_columns()
    existing_columns = [
        col for col in all_columns
        if column_exists(source_table, col) and column_exists(target_table, col)
    ]

    if not existing_columns:
        return  # No columns to copy (tables may be same or one may not have the columns)

    columns_str = ", ".join(existing_columns)
    op.get_bind().execute(
        sa.text(
            f"""
            INSERT INTO {target_table} ({columns_str})
            SELECT {columns_str}
            FROM {source_table} source
            WHERE NOT EXISTS (
                SELECT 1 FROM {target_table} target WHERE target.id = source.id
            )
            """
        )
    )


def _repoint_assessment_foreign_key(table_name, target_table, ondelete):
    current_targets = {
        foreign_key["referred_table"]
        for foreign_key in get_foreign_keys_by_column(table_name, "assessment_id")
    }
    if current_targets == {target_table}:
        return

    for foreign_key in get_foreign_keys_by_column(table_name, "assessment_id"):
        op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")

    constraint_name = f"fk_{table_name}_assessment_id_{target_table}"
    if not foreign_key_exists(table_name, constraint_name):
        op.create_foreign_key(
            constraint_name,
            table_name,
            target_table,
            ["assessment_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade():
    if not table_exists("assessment_events"):
        op.create_table(
            "assessment_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("seat_id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(36), nullable=False),
            sa.Column("join_code", sa.String(20), nullable=True),
            sa.Column("period", sa.String(10), nullable=True),
            sa.Column("obligation_type", sa.String(30), nullable=False),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_key", sa.String(20), nullable=True),
            sa.Column("coverage_start_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("coverage_end_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cycle_idempotency_key", sa.String(160), nullable=True),
            sa.Column("period_month", sa.Integer(), nullable=True),
            sa.Column("period_year", sa.Integer(), nullable=True),
            sa.Column("coverage_month", sa.Integer(), nullable=True),
            sa.Column("coverage_year", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["seat_id"], ["seats.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "seat_id",
                "class_id",
                "cycle_idempotency_key",
                name="uq_assessment_events_idempotency",
            ),
        )

    for index_name, columns in [
        ("ix_assessment_events_seat_id", ["seat_id"]),
        ("ix_assessment_events_class_id", ["class_id"]),
        ("ix_assessment_events_join_code", ["join_code"]),
        ("ix_assessment_events_period", ["period"]),
        ("ix_assessment_events_obligation_type", ["obligation_type"]),
        ("ix_assessment_events_coverage_start_time", ["coverage_start_time"]),
        ("ix_assessment_events_coverage_end_time", ["coverage_end_time"]),
        ("ix_assessment_events_cycle_idempotency_key", ["cycle_idempotency_key"]),
        ("ix_assessment_events_seat_class", ["seat_id", "class_id"]),
    ]:
        # Only create index if all columns exist and index doesn't already exist
        if not index_exists("assessment_events", index_name):
            all_columns_exist = all(
                column_exists("assessment_events", col) for col in columns
            )
            if all_columns_exist:
                op.create_index(index_name, "assessment_events", columns)

    if table_exists("obligation_assessment"):
        _copy_missing_assessments("obligation_assessment", "assessment_events")

    if not table_exists("obligation_lifecycle"):
        op.create_table(
            "obligation_lifecycle",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("assessment_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["assessment_id"], ["assessment_events.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "assessment_id", name="uq_obligation_lifecycle_assessment"
            ),
        )

    if not index_exists(
        "obligation_lifecycle", "ix_obligation_lifecycle_assessment_id"
    ):
        op.create_index(
            "ix_obligation_lifecycle_assessment_id",
            "obligation_lifecycle",
            ["assessment_id"],
        )
    if not index_exists("obligation_lifecycle", "ix_obligation_lifecycle_status"):
        op.create_index(
            "ix_obligation_lifecycle_status",
            "obligation_lifecycle",
            ["status"],
        )

    # Backfill obligation_lifecycle with initial status values
    # Use conditional logic based on which columns actually exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    try:
        satisfaction_cols = [col['name'] for col in inspector.get_columns('obligation_satisfaction')]
        has_satisfied_at = 'satisfied_at' in satisfaction_cols

        # Build the SELECT clause based on available columns
        if has_satisfied_at:
            timestamp_expr = "COALESCE(reversal.reversed_at, satisfaction.satisfied_at, assessment.assessed_at)"
        else:
            # If satisfied_at doesn't exist, use assessed_at or created_at if it exists
            has_created_at = 'created_at' in satisfaction_cols
            if has_created_at:
                timestamp_expr = "COALESCE(reversal.reversed_at, satisfaction.created_at, assessment.assessed_at)"
            else:
                timestamp_expr = "COALESCE(reversal.reversed_at, assessment.assessed_at)"

        backfill_sql = f"""
            INSERT INTO obligation_lifecycle (assessment_id, status, updated_at)
            SELECT
                assessment.id,
                CASE
                    WHEN reversal.id IS NOT NULL THEN 'REVERSED'
                    WHEN satisfaction.method = 'WAIVER' THEN 'WAIVED'
                    WHEN satisfaction.id IS NOT NULL THEN 'PAID'
                    WHEN assessment.due_at IS NOT NULL
                         AND assessment.due_at < CURRENT_TIMESTAMP THEN 'OVERDUE'
                    ELSE 'DUE'
                END,
                {timestamp_expr}
            FROM assessment_events assessment
            LEFT JOIN obligation_satisfaction satisfaction
                ON satisfaction.assessment_id = assessment.id
            LEFT JOIN obligation_reversal reversal
                ON reversal.assessment_id = assessment.id
            WHERE NOT EXISTS (
                SELECT 1
                FROM obligation_lifecycle lifecycle
                WHERE lifecycle.assessment_id = assessment.id
            )
            """

        conn.execute(sa.text(backfill_sql))
        print("✅ Backfilled obligation_lifecycle with initial status values")
    except Exception as e:
        print(f"⚠️  Could not backfill obligation_lifecycle: {e}")
        # This is non-critical; the table may be empty or in transition

    # Only repoint foreign keys if the legacy tables exist
    # (they are skipped in migration 0006 and handled by migration 0008)
    if table_exists("obligation_satisfaction"):
        _repoint_assessment_foreign_key(
            "obligation_satisfaction", "assessment_events", "CASCADE"
        )
    if table_exists("obligation_reversal"):
        _repoint_assessment_foreign_key(
            "obligation_reversal", "assessment_events", "CASCADE"
        )
    # Only repoint if entitlement_events has assessment_id column (legacy schema)
    if table_exists("entitlement_events") and column_exists("entitlement_events", "assessment_id"):
        _repoint_assessment_foreign_key(
            "entitlement_events", "assessment_events", "SET NULL"
        )


def downgrade():
    if table_exists("obligation_assessment") and table_exists("assessment_events"):
        _copy_missing_assessments("assessment_events", "obligation_assessment")

    if table_exists("obligation_satisfaction"):
        _repoint_assessment_foreign_key(
            "obligation_satisfaction", "obligation_assessment", "CASCADE"
        )
    if table_exists("obligation_reversal"):
        _repoint_assessment_foreign_key(
            "obligation_reversal", "obligation_assessment", "CASCADE"
        )
    # Only repoint if entitlement_events has assessment_id column (legacy schema)
    if table_exists("entitlement_events") and column_exists("entitlement_events", "assessment_id"):
        _repoint_assessment_foreign_key(
            "entitlement_events", "obligation_assessment", "SET NULL"
        )

    if table_exists("obligation_lifecycle"):
        op.drop_table("obligation_lifecycle")
    if table_exists("assessment_events"):
        op.drop_table("assessment_events")
