"""Make classes.class_timezone NOT NULL

Structural cleanup (Slice 2): every class is born with a confirmed IANA timezone
at creation, so classes.class_timezone must be NOT NULL. The optional column was
a bridge artifact from when timezone could be confirmed after the fact (see
c4b1a9d7e2f0, "class_timezone blank until confirmed"); that post-hoc confirmation
machinery has been removed. Per the cleanup directive, this migration adds NO
backfill or legacy-fallback logic for nonexistent production state — the
disposable certification DB is reset through migrations after this schema change.

Revision ID: cafe1234beef
Revises: c4b1a9d7e2f0
Create Date: 2026-08-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cafe1234beef'
down_revision = 'c4b1a9d7e2f0'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def column_is_nullable(table_name, column_name):
    """Return True if the column exists and is currently nullable."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for col in inspector.get_columns(table_name):
            if col['name'] == column_name:
                return bool(col.get('nullable', True))
    except Exception:
        return False
    return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # Enforce the born-confirmed timezone invariant at the schema level.
    if column_exists('classes', 'class_timezone') and column_is_nullable('classes', 'class_timezone'):
        op.alter_column(
            'classes',
            'class_timezone',
            existing_type=sa.String(length=64),
            nullable=False,
        )
        print("✅ classes.class_timezone is now NOT NULL")
    else:
        print("⚠️  classes.class_timezone already NOT NULL (or missing), skipping...")


def downgrade():
    # Revert to nullable. No data change: existing rows keep their timezone.
    if column_exists('classes', 'class_timezone') and not column_is_nullable('classes', 'class_timezone'):
        op.alter_column(
            'classes',
            'class_timezone',
            existing_type=sa.String(length=64),
            nullable=True,
        )
        print("❌ classes.class_timezone reverted to nullable")
    else:
        print("⚠️  classes.class_timezone already nullable (or missing), skipping...")
