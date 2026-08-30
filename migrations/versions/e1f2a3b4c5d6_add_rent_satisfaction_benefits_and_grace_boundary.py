"""Add rent satisfaction_benefits and bill_cycle grace_boundary_at

Two purely-additive columns supporting the canonical Rent lifecycle:

1. ``rent_settings.satisfaction_benefits`` (JSON, nullable) — Option-C typed
   payload describing the PERK entitlement grants awarded when a rent obligation
   is satisfied. Phase-1 closed schema: a list of ``{entitlement_type, quantity}``
   restricted to HALL_PASS. ``NULL`` means no grants.

2. ``bill_cycles.grace_boundary_at`` (timestamptz, nullable) — the resolved
   late-penalty boundary for a specific cycle, materialized once at cycle
   creation from ``grace_period_days``. Persisting it (rather than re-deriving
   from mutable RentSettings on every read) guarantees that a later settings
   change cannot retroactively move an already-materialized cycle's grace
   boundary, per INV-CORE-000 non-retroactivity.

Both columns are nullable with no server default; no backfill is required.

Revision ID: e1f2a3b4c5d6
Revises: d0bb45617620
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd0bb45617620'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    if table_exists('rent_settings') and not column_exists('rent_settings', 'satisfaction_benefits'):
        op.add_column('rent_settings', sa.Column('satisfaction_benefits', sa.JSON(), nullable=True))
        print("✅ Added column rent_settings.satisfaction_benefits")
    else:
        print("⚠️  Column 'satisfaction_benefits' already exists on 'rent_settings' (or table missing), skipping...")

    if table_exists('bill_cycles') and not column_exists('bill_cycles', 'grace_boundary_at'):
        op.add_column('bill_cycles', sa.Column('grace_boundary_at', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added column bill_cycles.grace_boundary_at")
    else:
        print("⚠️  Column 'grace_boundary_at' already exists on 'bill_cycles' (or table missing), skipping...")


def downgrade():
    if column_exists('bill_cycles', 'grace_boundary_at'):
        op.drop_column('bill_cycles', 'grace_boundary_at')
        print("❌ Dropped column bill_cycles.grace_boundary_at")
    else:
        print("⚠️  Column 'grace_boundary_at' does not exist on 'bill_cycles', skipping...")

    if column_exists('rent_settings', 'satisfaction_benefits'):
        op.drop_column('rent_settings', 'satisfaction_benefits')
        print("❌ Dropped column rent_settings.satisfaction_benefits")
    else:
        print("⚠️  Column 'satisfaction_benefits' does not exist on 'rent_settings', skipping...")
