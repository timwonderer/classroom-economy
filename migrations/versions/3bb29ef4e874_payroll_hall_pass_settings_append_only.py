"""Make payroll_settings and hall_pass_settings append-only policy repositories

Revision ID: 3bb29ef4e874
Revises: 429f7709a9d3
Create Date: 2026-09-04 00:00:00.000000

Blocker B2, the payroll half of the defect class B1 fixed for rent.

``PayrollEvent`` already froze ``policy_version_id``/``policy_uuid`` at creation
time, but ``_resolve_pay_rate_per_second`` computed the payout by reading the
*live* ``payroll_settings`` row, and a payroll run pays out all attendance
accrued since the seat's last payroll event. A teacher raising the pay rate
mid-cycle therefore repriced time a student had already worked — the freeze was
decorative because the row it pointed at kept changing underneath it.
DOM-CLASS-003 ("Pending Next-Cycle Payroll-Governing Changes") is explicit that
a payroll-governing change MUST NOT mutate the policy governing the open cycle
(INV-ARC-015 §VI.7).

``hall_pass_settings`` had the mirror-image gap: its writer already inserted a
new row per save, but nothing retired the predecessor, so a class accumulated
several rows all claiming to be current and the reader picked one by sort order.

Changes to ``payroll_settings``:
  1. New ``policy_uuid`` — under DOM-POL-001 §VI.0 this IS the version
     identifier. Backfilled per row, then made NOT NULL + UNIQUE.
  2. New ``availability_state`` (IN_USE / HIDDEN / RETIRED), backfilled from
     ``is_active``, plus a CHECK backstop.
  3. ``is_active`` dropped. Two current-policy projections on one table would be
     exactly the alternative version pointer DOM-POL-001 §VI.0 prohibits.
  4. Partial UNIQUE index on ``class_id WHERE availability_state = 'IN_USE'``,
     which is what makes supersession atomic and closes the TOCTOU race where
     two submissions both observe no current policy and both insert.
  5. Composite ``(class_id, availability_state)`` index for the current read.

Changes to ``hall_pass_settings``: items 2, 4 and 5 above (it already carries
``policy_uuid``).

Both tables may hold more than one row that this migration would consider
current. Duplicates are retired newest-wins before the unique index is built, so
the index creation cannot fail on legacy data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '3bb29ef4e874'
down_revision = '429f7709a9d3'
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
    that acquired the constraint through create_all() rather than this migration
    may have a different generated name for the same rule.
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


# A UUID literal without depending on pgcrypto or a specific server version.
_NEW_UUID_TEXT = "(md5(random()::text || clock_timestamp()::text))::uuid::text"


def _add_availability_state(table_name):
    """Add the availability projection column with an IN_USE backfill."""
    if not column_exists(table_name, 'availability_state'):
        op.add_column(
            table_name,
            sa.Column(
                'availability_state',
                sa.String(length=16),
                nullable=False,
                server_default='IN_USE',
            ),
        )
        print(f"✅ Added 'availability_state' to {table_name} (backfilled IN_USE)")
    else:
        print(f"⚠️  Column 'availability_state' already exists on {table_name!r}, skipping...")


def _add_availability_check(table_name, constraint_name):
    if not check_constraint_exists(table_name, constraint_name):
        op.create_check_constraint(
            constraint_name,
            table_name,
            "availability_state IN ('IN_USE','HIDDEN','RETIRED')",
        )
        print(f"✅ Added CHECK constraint {constraint_name!r}")
    else:
        print(f"⚠️  CHECK {constraint_name!r} already exists, skipping...")


def _retire_duplicate_current_rows(table_name, recency_column):
    """Leave exactly one IN_USE row per class so the unique index can be built.

    Newest wins, matching the canonical current-policy read: most recent
    ``recency_column``, then highest id as a total tiebreak.
    """
    op.execute(
        f"""
        UPDATE {table_name}
        SET availability_state = 'RETIRED'
        WHERE availability_state = 'IN_USE'
          AND id NOT IN (
              SELECT DISTINCT ON (class_id) id
              FROM {table_name}
              WHERE availability_state = 'IN_USE'
              ORDER BY class_id, {recency_column} DESC NULLS LAST, id DESC
          )
        """
    )
    print(f"✅ Retired superseded IN_USE rows in {table_name} (newest per class kept)")


def _add_active_scope_index(table_name, index_name):
    if not index_exists(table_name, index_name):
        op.create_index(
            index_name,
            table_name,
            ['class_id'],
            unique=True,
            postgresql_where=sa.text("availability_state = 'IN_USE'"),
        )
        print(f"✅ Added partial UNIQUE index {index_name!r}")
    else:
        print(f"⚠️  Index {index_name!r} already exists, skipping...")


def _add_class_availability_index(table_name, index_name):
    if not index_exists(table_name, index_name):
        op.create_index(index_name, table_name, ['class_id', 'availability_state'], unique=False)
        print(f"✅ Added index {index_name!r}")
    else:
        print(f"⚠️  Index {index_name!r} already exists, skipping...")


def upgrade():
    # --- payroll_settings -------------------------------------------------
    if table_exists('payroll_settings'):
        # 1. policy_uuid IS the version (DOM-POL-001 §VI.0). Added nullable,
        #    backfilled, then tightened — an existing table cannot take a NOT
        #    NULL column with no default in one step.
        if not column_exists('payroll_settings', 'policy_uuid'):
            op.add_column(
                'payroll_settings',
                sa.Column('policy_uuid', sa.String(length=36), nullable=True),
            )
            op.execute(
                f"UPDATE payroll_settings SET policy_uuid = {_NEW_UUID_TEXT} "
                "WHERE policy_uuid IS NULL"
            )
            op.alter_column('payroll_settings', 'policy_uuid', nullable=False)
            print("✅ Added 'policy_uuid' to payroll_settings (backfilled)")
        else:
            print("⚠️  Column 'policy_uuid' already exists on payroll_settings, skipping...")

        if not index_exists('payroll_settings', 'ix_payroll_settings_policy_uuid'):
            op.create_index(
                'ix_payroll_settings_policy_uuid',
                'payroll_settings',
                ['policy_uuid'],
                unique=True,
            )
            print("✅ Added UNIQUE index 'ix_payroll_settings_policy_uuid'")

        # 2. Availability projection, seeded from the is_active flag it replaces.
        _add_availability_state('payroll_settings')
        if column_exists('payroll_settings', 'is_active'):
            op.execute(
                "UPDATE payroll_settings "
                "SET availability_state = CASE WHEN is_active THEN 'IN_USE' ELSE 'RETIRED' END"
            )
            print("✅ Backfilled payroll_settings.availability_state from is_active")
        _add_availability_check('payroll_settings', 'ck_payroll_settings_availability')

        # 3. Collapse to one current row per class, then constrain it.
        _retire_duplicate_current_rows('payroll_settings', 'created_at')
        _add_active_scope_index('payroll_settings', 'uq_payroll_settings_active_scope')
        _add_class_availability_index(
            'payroll_settings', 'ix_payroll_settings_class_availability'
        )

        # 4. Retire the old flag. Keeping both projections would reintroduce the
        #    prohibited second current-version pointer.
        if column_exists('payroll_settings', 'is_active'):
            op.drop_column('payroll_settings', 'is_active')
            print("❌ Dropped 'is_active' from payroll_settings (replaced by availability_state)")
    else:
        print("⚠️  Table 'payroll_settings' does not exist, skipping...")

    # --- hall_pass_settings -----------------------------------------------
    if table_exists('hall_pass_settings'):
        _add_availability_state('hall_pass_settings')
        _add_availability_check('hall_pass_settings', 'ck_hall_pass_settings_availability')
        _retire_duplicate_current_rows('hall_pass_settings', 'effective_date')
        _add_active_scope_index('hall_pass_settings', 'uq_hall_pass_settings_active_scope')
        _add_class_availability_index(
            'hall_pass_settings', 'ix_hall_pass_settings_class_availability'
        )
    else:
        print("⚠️  Table 'hall_pass_settings' does not exist, skipping...")


def downgrade():
    """Restore the mutable-singleton shape.

    Lossy by construction on payroll_settings: ``is_active`` cannot express
    HIDDEN, so it collapses to ``availability_state = 'IN_USE'``. Superseded
    rows are kept (they are the rows historical payroll events resolve their
    rates through); only the constraints that forbid in-place editing are lifted.
    """
    if table_exists('hall_pass_settings'):
        for name in (
            'uq_hall_pass_settings_active_scope',
            'ix_hall_pass_settings_class_availability',
        ):
            if index_exists('hall_pass_settings', name):
                op.drop_index(name, table_name='hall_pass_settings')
                print(f"❌ Dropped index {name!r}")
        for constraint in get_check_constraints_by_column(
            'hall_pass_settings', 'availability_state'
        ):
            op.drop_constraint(constraint['name'], 'hall_pass_settings', type_='check')
            print(f"❌ Dropped CHECK constraint {constraint['name']!r}")
        if column_exists('hall_pass_settings', 'availability_state'):
            op.drop_column('hall_pass_settings', 'availability_state')
            print("❌ Dropped 'availability_state' from hall_pass_settings")

    if table_exists('payroll_settings'):
        if not column_exists('payroll_settings', 'is_active'):
            op.add_column(
                'payroll_settings',
                sa.Column(
                    'is_active',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('true'),
                ),
            )
            if column_exists('payroll_settings', 'availability_state'):
                op.execute(
                    "UPDATE payroll_settings "
                    "SET is_active = (availability_state = 'IN_USE')"
                )
            print("✅ Restored 'is_active' on payroll_settings")

        for name in (
            'uq_payroll_settings_active_scope',
            'ix_payroll_settings_class_availability',
        ):
            if index_exists('payroll_settings', name):
                op.drop_index(name, table_name='payroll_settings')
                print(f"❌ Dropped index {name!r}")
        for constraint in get_check_constraints_by_column(
            'payroll_settings', 'availability_state'
        ):
            op.drop_constraint(constraint['name'], 'payroll_settings', type_='check')
            print(f"❌ Dropped CHECK constraint {constraint['name']!r}")
        if column_exists('payroll_settings', 'availability_state'):
            op.drop_column('payroll_settings', 'availability_state')
            print("❌ Dropped 'availability_state' from payroll_settings")

        if index_exists('payroll_settings', 'ix_payroll_settings_policy_uuid'):
            op.drop_index('ix_payroll_settings_policy_uuid', table_name='payroll_settings')
        if column_exists('payroll_settings', 'policy_uuid'):
            op.drop_column('payroll_settings', 'policy_uuid')
            print("❌ Dropped 'policy_uuid' from payroll_settings")
