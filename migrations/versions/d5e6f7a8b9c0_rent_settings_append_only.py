"""Make rent_settings an append-only immutable policy repository

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-04 00:00:00.000000

DOM-POL-001 §VI.0/§VI.1: ``policy_uuid`` *is* the version. A class accumulates one
immutable row per teacher submission; the definition payload is never rewritten in
place. This migration removes the singleton constraint that made in-place editing the
only possible shape, and adds the availability projection that identifies which of the
accumulated rows is selectable for new work.

Why this matters (blocker B1): ``BillCycle.policy_uuid`` and
``ObligationAssessment.policy_uuid`` already froze the governing policy at creation
time, and ``ObligationAssessment`` has no amount column — the amount owed is resolved
from the referenced ``rent_settings`` row at read time. Because that row was rewritten
in place, a teacher raising rent from 50 to 200 retroactively rewrote the amount owed
on every already-assessed historical cycle. The freeze mechanism was fully wired; it
was inert only because the row it pointed at kept changing underneath it.

Changes:
  1. ``ix_rent_settings_class_id`` drops its UNIQUE flag — a class may now hold many
     rows. Recreated non-unique so lookups stay indexed.
  2. New ``availability_state`` column (IN_USE / HIDDEN / RETIRED). Existing rows
     backfill to IN_USE via server_default: the single row a class has today *is* its
     current policy.
  3. CHECK constraint backstopping the enum, and a composite
     ``(class_id, availability_state)`` index for the current-policy read.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


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
        return column_name in [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx['name'] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return fk_name in [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    except Exception:
        return False


def check_constraint_exists(table_name, constraint_name):
    """Check if a CHECK constraint exists on a table.

    The shared template helper only inspects UNIQUE constraints; the availability
    enum is enforced with a CHECK, so it needs its own existence probe.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return constraint_name in [c['name'] for c in inspector.get_check_constraints(table_name)]
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


def get_check_constraints_by_column(table_name, column_name):
    """Get CHECK constraints whose expression references a column.

    Used in downgrade() instead of hardcoding the constraint name: an environment
    that acquired the constraint through create_all() rather than this migration may
    have a different generated name for the same rule.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            c for c in inspector.get_check_constraints(table_name)
            if column_name in (c.get('sqltext') or '')
        ]
    except Exception:
        return []


def _index_is_unique(table_name, index_name):
    """Return True when the named index currently carries a UNIQUE flag."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for idx in inspector.get_indexes(table_name):
            if idx['name'] == index_name:
                return bool(idx.get('unique'))
    except Exception:
        return False
    return False


def upgrade():
    if not table_exists('rent_settings'):
        print("⚠️  Table 'rent_settings' does not exist, skipping...")
        return

    # 1. Drop the singleton constraint. One row per class was the shape that forced
    #    in-place edits; append-only requires many rows per class.
    if _index_is_unique('rent_settings', 'ix_rent_settings_class_id'):
        op.drop_index('ix_rent_settings_class_id', table_name='rent_settings')
        print("❌ Dropped UNIQUE index 'ix_rent_settings_class_id'")
    if not index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.create_index('ix_rent_settings_class_id', 'rent_settings', ['class_id'], unique=False)
        print("✅ Recreated 'ix_rent_settings_class_id' as non-unique")
    else:
        print("⚠️  'ix_rent_settings_class_id' already non-unique, skipping...")

    # 2. Availability projection over the immutable row. server_default backfills
    #    every existing row to IN_USE, which is correct: under the old unique
    #    constraint a class had exactly one row and it was the live policy.
    if not column_exists('rent_settings', 'availability_state'):
        op.add_column(
            'rent_settings',
            sa.Column(
                'availability_state',
                sa.String(length=16),
                nullable=False,
                server_default='IN_USE',
            ),
        )
        print("✅ Added 'availability_state' to rent_settings (backfilled IN_USE)")
    else:
        print("⚠️  Column 'availability_state' already exists, skipping...")

    # 3. Enum backstop at the database boundary.
    if not check_constraint_exists('rent_settings', 'ck_rent_settings_availability'):
        op.create_check_constraint(
            'ck_rent_settings_availability',
            'rent_settings',
            "availability_state IN ('IN_USE','HIDDEN','RETIRED')",
        )
        print("✅ Added CHECK constraint 'ck_rent_settings_availability'")
    else:
        print("⚠️  CHECK 'ck_rent_settings_availability' already exists, skipping...")

    # 4. Composite index for the current-policy read: the newest IN_USE row for a
    #    class. Without it that read degrades to a scan as rows accumulate.
    if not index_exists('rent_settings', 'ix_rent_settings_class_availability'):
        op.create_index(
            'ix_rent_settings_class_availability',
            'rent_settings',
            ['class_id', 'availability_state'],
            unique=False,
        )
        print("✅ Added index 'ix_rent_settings_class_availability'")
    else:
        print("⚠️  Index 'ix_rent_settings_class_availability' already exists, skipping...")


def downgrade():
    """Restore the singleton shape.

    Reverting to a UNIQUE class_id is lossy by construction: any class that has
    accumulated superseded policy versions must shed them, and the rows discarded are
    exactly the ones historical assessments resolve their amounts through. Keep the
    newest IN_USE row per class (falling back to the newest row of any state) so the
    live policy survives, and delete the rest.
    """
    if not table_exists('rent_settings'):
        print("⚠️  Table 'rent_settings' does not exist, skipping...")
        return

    if index_exists('rent_settings', 'ix_rent_settings_class_availability'):
        op.drop_index('ix_rent_settings_class_availability', table_name='rent_settings')
        print("❌ Dropped index 'ix_rent_settings_class_availability'")

    for constraint in get_check_constraints_by_column('rent_settings', 'availability_state'):
        op.drop_constraint(constraint['name'], 'rent_settings', type_='check')
        print(f"❌ Dropped CHECK constraint {constraint['name']!r}")

    # Collapse to one row per class before the unique index can be restored.
    # Ordering mirrors the canonical current-policy read: IN_USE first, then newest
    # rent_configured_at, then highest id as a total tiebreak.
    if column_exists('rent_settings', 'availability_state'):
        op.execute(
            """
            DELETE FROM rent_settings
            WHERE id NOT IN (
                SELECT DISTINCT ON (class_id) id
                FROM rent_settings
                ORDER BY class_id,
                         (availability_state = 'IN_USE') DESC,
                         rent_configured_at DESC NULLS LAST,
                         id DESC
            )
            """
        )
        print("❌ Collapsed rent_settings to one row per class (superseded versions deleted)")
        op.drop_column('rent_settings', 'availability_state')
        print("❌ Dropped 'availability_state' from rent_settings")
    else:
        op.execute(
            """
            DELETE FROM rent_settings
            WHERE id NOT IN (
                SELECT DISTINCT ON (class_id) id
                FROM rent_settings
                ORDER BY class_id, rent_configured_at DESC NULLS LAST, id DESC
            )
            """
        )
        print("❌ Collapsed rent_settings to one row per class")

    if index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.drop_index('ix_rent_settings_class_id', table_name='rent_settings')
    if not index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.create_index('ix_rent_settings_class_id', 'rent_settings', ['class_id'], unique=True)
        print("✅ Restored UNIQUE index 'ix_rent_settings_class_id'")
