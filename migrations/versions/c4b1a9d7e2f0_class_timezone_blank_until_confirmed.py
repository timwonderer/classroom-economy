"""Make class_timezone blank until confirmed (drop 'UTC' placeholder default)

Revision ID: c4b1a9d7e2f0
Revises: 534108fd5524
Create Date: 2026-08-24

Canonical fix for the recurring class-timezone confirmation loop.

Previously `classes.class_timezone` was `NOT NULL DEFAULT 'UTC'`, so every class
was *born* carrying the placeholder value 'UTC'. That made an unconfirmed class
(never set by the teacher) indistinguishable from a class deliberately set to
UTC. The confirmation modal (admin_students.html) treated 'UTC' as "unset" and
re-prompted, while the server gate (`_class_timezone_needs_confirmation`) treated
'UTC' as a valid, already-confirmed value and returned 409 "already locked" on
the teacher's real pick — so the write never landed and the modal reappeared
forever.

Canonical model: NULL is the single "unset" sentinel. A class is created with a
blank timezone; the teacher confirms exactly once via the modal. A deliberate UTC
confirmation is persisted as the distinct value 'Etc/UTC' (never the bare 'UTC'
placeholder), so it reads as resolved.

This migration:
  1. Drops the NOT NULL constraint and the 'UTC' server_default.
  2. Normalizes existing placeholder rows: class_timezone = 'UTC' -> NULL.
     (Genuine UTC confirmations are stored as 'Etc/UTC' and are left untouched.)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4b1a9d7e2f0'
down_revision = '534108fd5524'
branch_labels = None
depends_on = None


TABLE = 'classes'
COLUMN = 'class_timezone'


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
    """Return True if the column is currently nullable."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for col in inspector.get_columns(table_name):
            if col['name'] == column_name:
                return bool(col.get('nullable', False))
    except Exception:
        return False
    return False


def upgrade():
    if not column_exists(TABLE, COLUMN):
        print(f"⚠️  Column '{COLUMN}' missing on '{TABLE}', skipping...")
        return

    # 1. Drop NOT NULL + server default so blank/NULL is the unset sentinel.
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.String(length=64),
        nullable=True,
        server_default=None,
    )
    print(f"✅ {TABLE}.{COLUMN} is now nullable with no server default")

    # 2. Normalize placeholder rows to the canonical unset sentinel (NULL).
    #    Confirmed-UTC rows are stored as 'Etc/UTC' and are intentionally spared.
    result = op.get_bind().execute(
        sa.text(f"UPDATE {TABLE} SET {COLUMN} = NULL WHERE {COLUMN} = 'UTC'")
    )
    print(f"✅ Normalized {result.rowcount} placeholder 'UTC' row(s) to NULL")


def downgrade():
    if not column_exists(TABLE, COLUMN):
        print(f"⚠️  Column '{COLUMN}' missing on '{TABLE}', skipping...")
        return

    # Restore placeholder for any NULL rows before re-imposing NOT NULL.
    op.get_bind().execute(
        sa.text(f"UPDATE {TABLE} SET {COLUMN} = 'UTC' WHERE {COLUMN} IS NULL")
    )

    if column_is_nullable(TABLE, COLUMN):
        op.alter_column(
            TABLE,
            COLUMN,
            existing_type=sa.String(length=64),
            nullable=False,
            server_default='UTC',
        )
        print(f"❌ Restored {TABLE}.{COLUMN} NOT NULL DEFAULT 'UTC'")
    else:
        print(f"⚠️  {TABLE}.{COLUMN} already NOT NULL, skipping...")
