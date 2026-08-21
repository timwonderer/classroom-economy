"""Store canonical flat or progressive overdraft fines on EconomicEngine."""

from alembic import op
import sqlalchemy as sa


revision = "da1b2c3d4e5f"
down_revision = ("c9e0f1a2b3c4", "f8d9e0f1a2b4")
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("economic_engine")}
    if "overdraft_fine_amount" in columns and "flat_overdraft_fee" not in columns:
        op.alter_column("economic_engine", "overdraft_fine_amount", new_column_name="flat_overdraft_fee")
        columns.remove("overdraft_fine_amount")
        columns.add("flat_overdraft_fee")
    if "flat_overdraft_fee" not in columns:
        op.add_column("economic_engine", sa.Column("flat_overdraft_fee", sa.Numeric(precision=12, scale=2), nullable=True))
    if "progressive_overdraft_fee" not in columns:
        op.add_column("economic_engine", sa.Column("progressive_overdraft_fee", sa.JSON(), nullable=True))
    if "overdraft_protection_enabled" not in columns:
        op.add_column("economic_engine", sa.Column("overdraft_protection_enabled", sa.Boolean(), nullable=True))
    constraints = {constraint["name"] for constraint in inspector.get_check_constraints("economic_engine")}
    if "ck_economic_engine_overdraft_fine" in constraints:
        op.drop_constraint("ck_economic_engine_overdraft_fine", "economic_engine", type_="check")
    if "ck_economic_engine_flat_overdraft_fee" not in constraints:
        op.create_check_constraint(
            "ck_economic_engine_flat_overdraft_fee",
            "economic_engine",
            "flat_overdraft_fee IS NULL OR flat_overdraft_fee >= 0",
        )
    conflicts = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM economic_engine WHERE flat_overdraft_fee IS NOT NULL AND progressive_overdraft_fee IS NOT NULL"
    )).scalar()
    if conflicts:
        raise RuntimeError(f"{conflicts} economic_engine rows violate overdraft fee exclusivity")
    if "ck_economic_engine_overdraft_fee_exclusive" not in constraints:
        op.create_check_constraint(
            "ck_economic_engine_overdraft_fee_exclusive",
            "economic_engine",
            "flat_overdraft_fee IS NULL OR progressive_overdraft_fee IS NULL",
        )


def downgrade():
    raise NotImplementedError("EconomicEngine schema evolution is append-only")
