"""Phase 2e: Add composite key class scoping for EconomicEngine and ClassFeature

Revision ID: 9c6d5e4f3a2b
Revises: ae6b7c8d9e0f
Create Date: 2026-08-10 00:00:00.000000

Per INV-ARC-004 and DOM-CLASS-001, all class-level configuration must be scoped by class_id.
This migration enforces class-local version references at the database boundary:

1. Add composite unique key: EconomicEngine(class_id, economic_version_id)
   - Prevents cross-class version references
   - Enables composite foreign keys scoped to class

2. Add composite foreign key: EconomicEngine.previous_version_id
   - (class_id, previous_version_id) → (class_id, economic_version_id)
   - Ensures version chains stay within class boundary

3. Add composite foreign key: ClassFeature.economic_version_id
   - (class_id, economic_version_id) → (class_id, economic_version_id)
   - Ensures features only reference versions in their own class
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

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)] + \
                     [c['name'] for c in inspector.get_foreign_keys(table_name)]
        return constraint_name in constraints
    except Exception:
        return False

# revision identifiers, used by Alembic.
revision = '9c6d5e4f3a2b'
down_revision = 'ae6b7c8d9e0f'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite key class scoping for EconomicEngine and ClassFeature."""
    print("\n" + "=" * 80)
    print("Phase 2e: Add composite key class scoping")
    print("=" * 80)

    conn = op.get_bind()

    # ==========================================================================
    # STEP 1: Add composite unique key to EconomicEngine
    # ==========================================================================
    print("\n🔐 Adding composite key to EconomicEngine...")

    if table_exists('economic_engine'):
        if not constraint_exists('economic_engine', 'uq_economic_engine_class_version'):
            op.create_unique_constraint(
                'uq_economic_engine_class_version',
                'economic_engine',
                ['class_id', 'economic_version_id']
            )
            print("   ✅ Created composite unique key: (class_id, economic_version_id)")
        else:
            print("   ℹ️  Composite unique key already exists")

        # Add composite foreign key for previous_version_id
        if not constraint_exists('economic_engine', 'fk_economic_engine_previous_version'):
            op.create_foreign_key(
                'fk_economic_engine_previous_version',
                'economic_engine',
                'economic_engine',
                ['class_id', 'previous_version_id'],
                ['class_id', 'economic_version_id'],
                ondelete='RESTRICT'
            )
            print("   ✅ Created composite FK: (class_id, previous_version_id) → (class_id, economic_version_id)")
        else:
            print("   ℹ️  Composite FK for previous_version_id already exists")
    else:
        print("⚠️  economic_engine table not found; skipping")

    # ==========================================================================
    # STEP 2: Add composite foreign key to ClassFeature
    # ==========================================================================
    print("\n🔐 Adding composite foreign key to ClassFeature...")

    if table_exists('class_features'):
        if not constraint_exists('class_features', 'fk_class_features_economic_version'):
            op.create_foreign_key(
                'fk_class_features_economic_version',
                'class_features',
                'economic_engine',
                ['class_id', 'economic_version_id'],
                ['class_id', 'economic_version_id'],
                ondelete='RESTRICT'
            )
            print("   ✅ Created composite FK: (class_id, economic_version_id) → (class_id, economic_version_id)")
        else:
            print("   ℹ️  Composite FK already exists")
    else:
        print("⚠️  class_features table not found; skipping")

    print("\n" + "=" * 80)
    print("✅ Phase 2e Complete: Class scoping enforced at database boundary")
    print("=" * 80)


def downgrade():
    """Downgrade Phase 2e (not supported)."""
    raise RuntimeError(
        "Downgrade from Phase 2e is not supported. "
        "Adding composite key class scoping is a permanent database-level constraint. "
        "If rollback is necessary, restore from database backup. Contact ops team for guidance."
    )
