"""add insurance_policies definition-of-record table

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f3
Create Date: 2026-08-25

Additive-only. Introduces the STOR-owned, POL-managed immutable insurance
policy definition-of-record (``insurance_policies``). Typed columns with
per-type structural CHECKs and hard-domain invariant CHECKs act as DB
integrity backstops. Economic-Engine recommendation ranges are intentionally
NOT encoded here.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a7b8c9d0e1f3"
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    if not table_exists("insurance_policies"):
        op.create_table(
            "insurance_policies",
            sa.Column("policy_uuid", sa.String(length=36), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("insurance_type", sa.String(length=20), nullable=False),
            sa.Column("tier_level", sa.Integer(), nullable=True),
            sa.Column("premium", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column("charge_frequency", sa.String(length=20), nullable=False),  # WEEKLY | MONTHLY
            sa.Column("reimbursement_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column("payout_multiple", sa.Numeric(precision=6, scale=2), nullable=True),
            sa.Column("claims_per_week_equivalent", sa.Numeric(precision=6, scale=3), nullable=True),
            sa.Column("claim_window_days", sa.Integer(), nullable=True),
            sa.Column("claimable_dates_per_week_equivalent", sa.Numeric(precision=6, scale=3), nullable=True),
            sa.Column("waiting_period_days", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=120), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tier_name", sa.String(length=60), nullable=True),
            sa.Column("tier_group", sa.String(length=60), nullable=True),
            sa.Column("availability_state", sa.String(length=16), nullable=False, server_default="IN_USE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by_seat_id", sa.Integer(), nullable=True),
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["class_id"], ["classes.class_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_seat_id"], ["seats.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("policy_uuid"),
            # --- Enum backstops ---------------------------------------------
            sa.CheckConstraint(
                "insurance_type IN ('TRANSACTION','PRODUCTIVITY','NON_MONETARY')",
                name="ck_insurance_policies_type",
            ),
            sa.CheckConstraint(
                "availability_state IN ('IN_USE','HIDDEN','RETIRED')",
                name="ck_insurance_policies_availability",
            ),
            sa.CheckConstraint(
                "charge_frequency IN ('WEEKLY','MONTHLY')",
                name="ck_insurance_policies_frequency",
            ),
            # --- Hard-domain invariants (NOT recommendation ranges) ---------
            sa.CheckConstraint("premium >= 0", name="ck_insurance_policies_premium_nonneg"),
            sa.CheckConstraint(
                "reimbursement_percentage IS NULL OR "
                "(reimbursement_percentage >= 0 AND reimbursement_percentage <= 100)",
                name="ck_insurance_policies_reimbursement_range",
            ),
            sa.CheckConstraint(
                "payout_multiple IS NULL OR payout_multiple >= 0",
                name="ck_insurance_policies_payout_multiple_nonneg",
            ),
            sa.CheckConstraint(
                "claims_per_week_equivalent IS NULL OR claims_per_week_equivalent >= 0",
                name="ck_insurance_policies_claims_per_week_nonneg",
            ),
            sa.CheckConstraint(
                "claim_window_days IS NULL OR claim_window_days >= 0",
                name="ck_insurance_policies_claim_window_nonneg",
            ),
            sa.CheckConstraint(
                "claimable_dates_per_week_equivalent IS NULL OR "
                "claimable_dates_per_week_equivalent >= 0",
                name="ck_insurance_policies_claimable_dates_nonneg",
            ),
            sa.CheckConstraint(
                "waiting_period_days IS NULL OR waiting_period_days >= 0",
                name="ck_insurance_policies_waiting_period_nonneg",
            ),
            sa.CheckConstraint(
                "tier_level IS NULL OR tier_level >= 0",
                name="ck_insurance_policies_tier_level_nonneg",
            ),
            # --- Per-type structural subset ---------------------------------
            sa.CheckConstraint(
                "("
                "  insurance_type = 'TRANSACTION' AND"
                "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
                "  claims_per_week_equivalent IS NOT NULL AND claim_window_days IS NOT NULL AND"
                "  claimable_dates_per_week_equivalent IS NULL AND waiting_period_days IS NULL"
                ") OR ("
                "  insurance_type = 'PRODUCTIVITY' AND"
                "  reimbursement_percentage IS NOT NULL AND payout_multiple IS NOT NULL AND"
                "  claimable_dates_per_week_equivalent IS NOT NULL AND"
                "  claims_per_week_equivalent IS NULL AND claim_window_days IS NULL AND"
                "  waiting_period_days IS NULL"
                ") OR ("
                "  insurance_type = 'NON_MONETARY' AND"
                "  claims_per_week_equivalent IS NOT NULL AND waiting_period_days IS NOT NULL AND"
                "  reimbursement_percentage IS NULL AND payout_multiple IS NULL AND"
                "  claim_window_days IS NULL AND claimable_dates_per_week_equivalent IS NULL"
                ")",
                name="ck_insurance_policies_type_subset",
            ),
        )
        print("✅ Created table insurance_policies")
    else:
        print("⚠️  Table 'insurance_policies' already exists, skipping...")

    if not index_exists("insurance_policies", "ix_insurance_policies_class_id"):
        op.create_index(
            "ix_insurance_policies_class_id", "insurance_policies", ["class_id"], unique=False
        )
        print("✅ Created index ix_insurance_policies_class_id")
    else:
        print("⚠️  Index 'ix_insurance_policies_class_id' already exists, skipping...")

    if not index_exists("insurance_policies", "ix_insurance_policies_class_avail"):
        op.create_index(
            "ix_insurance_policies_class_avail",
            "insurance_policies",
            ["class_id", "availability_state"],
            unique=False,
        )
        print("✅ Created index ix_insurance_policies_class_avail")
    else:
        print("⚠️  Index 'ix_insurance_policies_class_avail' already exists, skipping...")


def downgrade():
    if index_exists("insurance_policies", "ix_insurance_policies_class_avail"):
        op.drop_index("ix_insurance_policies_class_avail", table_name="insurance_policies")
        print("❌ Dropped index ix_insurance_policies_class_avail")

    if index_exists("insurance_policies", "ix_insurance_policies_class_id"):
        op.drop_index("ix_insurance_policies_class_id", table_name="insurance_policies")
        print("❌ Dropped index ix_insurance_policies_class_id")

    if table_exists("insurance_policies"):
        op.drop_table("insurance_policies")
        print("❌ Dropped table insurance_policies")
    else:
        print("⚠️  Table 'insurance_policies' does not exist, skipping...")
