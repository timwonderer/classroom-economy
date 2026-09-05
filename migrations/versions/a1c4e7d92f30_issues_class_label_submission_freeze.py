"""Add issues.class_label — the class display name frozen at submission

DOM-SUP-001 §VI lists ``class_label`` as part of the ``issues`` schema contract:
a *class context cache*, frozen at submission time, which "must not be re-fetched
live from ClassEconomy after submission." The column was never created, so the
sysadmin escalation views read an attribute that did not exist and returned a
hard 500 (blocker B4).

Resolving the label live from ``class_public_id`` would have avoided the
migration but broken the freeze: an escalation describes the class as it stood
when the student submitted, and a class renamed — or destroyed — afterwards
would silently rewrite or erase the context of tickets already in flight.

Backfill uses the live class row, which is the best available approximation for
rows that predate the column. It is explicitly a one-time reconstruction, not an
ongoing resolution path; from here forward the value is written once at
submission and never updated.

Disclosure of this value to sysadmin remains gated on
``share_class_name_with_sysadmin`` (default false) at the view boundary.

Revision ID: a1c4e7d92f30
Revises: 3bb29ef4e874
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c4e7d92f30'
down_revision = '3bb29ef4e874'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


# ============================================================================


def upgrade():
    if not table_exists('issues'):
        print("⚠️  Table 'issues' does not exist, skipping...")
        return

    if column_exists('issues', 'class_label'):
        print("⚠️  Column 'class_label' already exists on 'issues', skipping...")
        return

    op.add_column('issues', sa.Column('class_label', sa.String(length=255), nullable=True))
    print("✅ Added class_label to issues")

    # One-time reconstruction for pre-existing rows. Only rows that can be
    # matched to a surviving class get a label; the rest stay NULL, which the
    # view layer renders as "no class context" rather than inventing one.
    if table_exists('classes') and column_exists('classes', 'class_public_id'):
        result = op.get_bind().execute(sa.text("""
            UPDATE issues i
            SET class_label = c.display_name
            FROM classes c
            WHERE i.class_public_id = c.class_public_id
              AND i.class_label IS NULL
        """))
        print(f"✅ Backfilled class_label on {result.rowcount} issue rows")
    else:
        print("⚠️  'classes.class_public_id' unavailable, skipping backfill")


def downgrade():
    if column_exists('issues', 'class_label'):
        op.drop_column('issues', 'class_label')
        print("❌ Dropped class_label from issues")
    else:
        print("⚠️  Column 'class_label' does not exist on 'issues', skipping...")
