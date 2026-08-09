"""Phase 2c: Add composite FK and UNIQUE constraints for class-scoped isolation

Revision ID: 9a5b6c7d8e9f
Revises: 83be5c965a68
Create Date: 2026-08-09 22:00:00.000000

Add class-scoped isolation constraints per Phase 2 architecture:

1. EconomicEngine: Add UNIQUE (class_id, economic_version_id) to prevent multiple active versions per class
2. EconomicEngine: Change previous_version_id FK to composite FK (class_id, previous_version_id)
   to enforce previous versions must be in same class (RESTRICT cascade)
3. ClassFeature: Add composite FK (class_id, economic_version_id) to enforce features must reference
   EconomicEngine versions in their own class

These constraints make class boundaries structural (DB-enforced) rather than semantic (caller remembers).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

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

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

# revision identifiers, used by Alembic.
revision = '9a5b6c7d8e9f'
down_revision = '83be5c965a68'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite FK and UNIQUE constraints for class-scoped isolation."""
    print("\n" + "=" * 80)
    print("Phase 2c: Add composite FK and UNIQUE constraints for class-scoped isolation")
    print("=" * 80)

    conn = op.get_bind()

    # ==========================================================================
    # STEP 1: Add UNIQUE constraint to EconomicEngine
    # ==========================================================================
    print("\n📊 Adding class-scope isolation constraints to EconomicEngine...")

    if table_exists('economic_engine'):
        # Add UNIQUE (class_id, economic_version_id) to prevent multiple active versions per class
        if not constraint_exists('economic_engine', 'uq_economic_engine_class_version'):
            op.create_unique_constraint(
                'uq_economic_engine_class_version',
                'economic_engine',
                ['class_id', 'economic_version_id']
            )
            print("   ✅ Added UNIQUE(class_id, economic_version_id)")
        else:
            print("   ℹ️  UNIQUE constraint already exists")

        # Drop old single-column FK on previous_version_id (will be replaced with composite FK)
        if foreign_key_exists('economic_engine', 'fk_economic_engine_previous_version_id'):
            op.drop_constraint('fk_economic_engine_previous_version_id', 'economic_engine', type_='foreignkey')
            print("   ✅ Dropped old single-column FK on previous_version_id")
        else:
            print("   ℹ️  Old FK already dropped or doesn't exist")

        # Add composite FK: (class_id, previous_version_id) -> (class_id, economic_version_id)
        if not foreign_key_exists('economic_engine', 'fk_economic_engine_previous_version_composite'):
            op.create_foreign_key(
                'fk_economic_engine_previous_version_composite',
                'economic_engine',
                'economic_engine',
                ['class_id', 'previous_version_id'],
                ['class_id', 'economic_version_id'],
                ondelete='RESTRICT'
            )
            print("   ✅ Added composite FK (class_id, previous_version_id) -> (class_id, economic_version_id)")
        else:
            print("   ℹ️  Composite FK already exists")
    else:
        print("⚠️  economic_engine table not found; skipping constraints")

    # ==========================================================================
    # STEP 2: Update ClassFeature FK to composite FK
    # ==========================================================================
    print("\n📊 Adding class-scope isolation constraints to ClassFeature...")

    if table_exists('class_features'):
        # Drop old single-column FK on economic_version_id (will be replaced with composite FK)
        if foreign_key_exists('class_features', 'fk_class_features_economic_version_id'):
            op.drop_constraint('fk_class_features_economic_version_id', 'class_features', type_='foreignkey')
            print("   ✅ Dropped old single-column FK on economic_version_id")
        else:
            print("   ℹ️  Old FK already dropped or doesn't exist")

        # Add composite FK: (class_id, economic_version_id) -> (class_id, economic_version_id)
        if not foreign_key_exists('class_features', 'fk_class_features_economic_version_composite'):
            op.create_foreign_key(
                'fk_class_features_economic_version_composite',
                'class_features',
                'economic_engine',
                ['class_id', 'economic_version_id'],
                ['class_id', 'economic_version_id'],
                ondelete='RESTRICT'
            )
            print("   ✅ Added composite FK (class_id, economic_version_id) -> (class_id, economic_version_id)")
        else:
            print("   ℹ️  Composite FK already exists")
    else:
        print("⚠️  class_features table not found; skipping constraints")

    print("\n" + "=" * 80)
    print("✅ Phase 2c Complete: Class-scoped isolation enforced at database level")
    print("=" * 80)


def downgrade():
    """Downgrade Phase 2c (not supported)."""
    raise RuntimeError(
        "Downgrade from Phase 2c is not supported. "
        "Adding composite FK and UNIQUE constraints for class-scoped isolation "
        "is a permanent architectural change. If rollback is necessary, restore from database backup. "
        "Contact ops team for guidance."
    )
