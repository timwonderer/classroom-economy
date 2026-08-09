"""Phase 2b: Remove id surrogate from class_features

Revision ID: 83be5c965a68
Revises: 0f0436f6026f
Create Date: 2026-08-09 02:59:13.965481

This migration removes the redundant id column from class_features now that
we have a proper composite primary key: (class_id, feature, effective_at).

The ORM model was already updated in Phase 2 to use the composite PK, but
the database table still had the old id column. This migration removes it.
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

def primary_key_columns(table_name):
    """Return primary-key columns for a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        pk = inspector.get_pk_constraint(table_name) or {}
        return pk.get('constrained_columns') or []
    except Exception:
        return []

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = '83be5c965a68'
down_revision = '0f0436f6026f'
branch_labels = None
depends_on = None


def upgrade():
    """Remove id surrogate from class_features and establish composite PK."""
    print("\n🔄 Phase 2b: Removing id surrogate from class_features...")

    if not table_exists('class_features'):
        print("⚠️  class_features table not found; skipping")
        return

    composite_pk = ['class_id', 'feature', 'effective_at']

    if column_exists('class_features', 'id'):
        print("   📋 Removing id column and reestablishing composite PK...")
        with op.batch_alter_table('class_features', schema=None) as batch_op:
            batch_op.drop_column('id')
        print("   ✅ Dropped id column")
    else:
        print("   ℹ️  id column already absent; verifying composite PK")

    if primary_key_columns('class_features') != composite_pk:
        op.create_primary_key(
            'pk_class_features',
            'class_features',
            composite_pk
        )
        print("   ✅ Created composite primary key (class_id, feature, effective_at)")
    else:
        print("   ℹ️  Composite primary key already exists")

    print("   ✅ Phase 2b complete: class_features now uses composite PK (class_id, feature, effective_at)")


def downgrade():
    """Revert Phase 2b (downgrade not supported)."""
    raise RuntimeError(
        "Downgrade from Phase 2b is not supported. "
        "Removing the id surrogate and establishing composite PK (class_id, feature, effective_at) "
        "is a permanent architectural change. If rollback is necessary, restore from database backup. "
        "Contact ops team for guidance."
    )
