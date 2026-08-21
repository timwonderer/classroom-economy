"""Drop dead rent_settings version columns

Revision ID: 2978fdba914a
Revises: a4e8f19d7c31
Create Date: 2026-08-16 06:54:20.171979

Drops rent_settings.active_version_id and rent_settings.next_version_id.

Both columns are orphans from an abandoned rent-specific versioning
mechanism. Migration c5459df99053 added them alongside a rent_policy_versions
table; migration 7c3d4e5f6a7b dropped rent_policy_versions and the FK
constraints on these two columns but left the columns themselves behind.
The RentSettings ORM model does not declare either column, no code path
reads or writes them, and every existing row holds NULL for both.

Under DOM-POL-001 §VI.0, policy_uuid IS the version identifier for a
policy definition — no separate version-pointer column belongs on a
Policies-repository table.

"""
from alembic import op
import sqlalchemy as sa


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
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
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
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = '2978fdba914a'
down_revision = 'a4e8f19d7c31'
branch_labels = None
depends_on = None


def upgrade():
    for col_name in ('active_version_id', 'next_version_id'):
        # Defensive: drop any lingering FK constraints on the column first.
        # The 7c3d4e5f6a7b migration already removed the original FKs, but
        # get_foreign_keys_by_column() is a no-op if none remain.
        for fk in get_foreign_keys_by_column('rent_settings', col_name):
            fk_name = fk.get('name')
            if fk_name:
                op.drop_constraint(fk_name, 'rent_settings', type_='foreignkey')
                print(f"❌ Dropped orphan FK {fk_name} on rent_settings.{col_name}")

        if column_exists('rent_settings', col_name):
            op.drop_column('rent_settings', col_name)
            print(f"❌ Dropped dead column rent_settings.{col_name}")
        else:
            print(f"⚠️  rent_settings.{col_name} already absent, skipping")


def downgrade():
    # Restore the two nullable integer columns without FK constraints.
    # rent_policy_versions no longer exists (dropped by 7c3d4e5f6a7b), so
    # we cannot recreate the original FKs. This downgrade only restores
    # the physical column shape, which matches the state left by
    # 7c3d4e5f6a7b prior to this migration.
    if not column_exists('rent_settings', 'active_version_id'):
        op.add_column(
            'rent_settings',
            sa.Column('active_version_id', sa.Integer(), nullable=True),
        )
        print("↩️  Restored rent_settings.active_version_id (no FK)")

    if not column_exists('rent_settings', 'next_version_id'):
        op.add_column(
            'rent_settings',
            sa.Column('next_version_id', sa.Integer(), nullable=True),
        )
        print("↩️  Restored rent_settings.next_version_id (no FK)")
