"""Add partial unique index enforcing one active payroll setting per scope

Revision ID: 534108fd5524
Revises: dd4e5f6a7b8c
Create Date: 2026-08-22

Enforces the canonical invariant (DOM-CLASS-001 / INV-ARC-019) that a class has
exactly one *active* PayrollSettings row per resolution scope. The canonical
writer (`upsert_payroll_settings`) updates a single row per class in place, and
the reader (`payroll._fetch_single_active_setting`) treats more than one active
row for a (class_id, block) scope as fatal ("Ambiguous PayrollSettings scope").

Without a persistence-layer guard, duplicate active rows are possible — most
notably via the TOCTOU race in `upsert_payroll_settings`, where two concurrent
callers both observe no existing row and both INSERT. This partial unique index
closes that race at the lowest authoritative boundary.

NULL block is the class-global scope; it is normalized via COALESCE to a single
sentinel so two block=NULL rows collide. A class may still legitimately hold one
global row AND one block-specific row (distinct scopes) at the same time.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '534108fd5524'
down_revision = 'dd4e5f6a7b8c'
branch_labels = None
depends_on = None


INDEX_NAME = 'uq_payroll_settings_active_scope'


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    if not table_exists('payroll_settings'):
        print("⚠️  Table 'payroll_settings' does not exist, skipping...")
        return

    if index_exists('payroll_settings', INDEX_NAME):
        print(f"⚠️  Index '{INDEX_NAME}' already exists, skipping...")
        return

    # Expression + partial index: not expressible via op.create_index portably.
    # CREATE UNIQUE INDEX will fail loudly if duplicate active scopes already
    # exist — that is the intended surfacing of the persistence defect, not a
    # condition to silently paper over.
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME} "
            "ON payroll_settings (class_id, COALESCE(block, '')) "
            "WHERE is_active IS TRUE"
        )
    )
    print(f"✅ Created partial unique index '{INDEX_NAME}' on payroll_settings")


def downgrade():
    if index_exists('payroll_settings', INDEX_NAME):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
        print(f"❌ Dropped partial unique index '{INDEX_NAME}'")
    else:
        print(f"⚠️  Index '{INDEX_NAME}' does not exist, skipping...")
