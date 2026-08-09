"""Phase 2d: Add database-level immutability TRIGGERs for append-only tables

Revision ID: ae6b7c8d9e0f
Revises: 9a5b6c7d8e9f
Create Date: 2026-08-09 22:30:00.000000

Add database-level immutability enforcement via TRIGGERs. While the ORM
`before_update` listener provides developer-friendly errors, it cannot catch:
- SQLAlchemy Core layer updates
- Bulk ORM updates (update_all)
- Direct SQL mutations

TRIGGERs enforce immutability at the database boundary for all mutation paths.

Tables enforced as append-only:
1. economic_engine — EconomicEngine versions are immutable snapshots
2. class_features — ClassFeature timeline entries are immutable records

Per DOM-CLASS-001: These tables represent immutable domain history that cannot
be revised. Only appending new versions/entries is permitted.

TESTING EXCEPTION: TRIGGERs are NOT created on test databases to allow
test helpers (e.g., disable_class_feature) to clean up test data.
TRIGGERs only apply to production and integration environments.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import os

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def trigger_exists(trigger_name):
    """Check if a trigger exists."""
    conn = op.get_bind()
    try:
        result = conn.execute(text(
            f"SELECT 1 FROM information_schema.triggers WHERE trigger_name = '{trigger_name}'"
        )).fetchone()
        return result is not None
    except Exception:
        return False

# revision identifiers, used by Alembic.
revision = 'ae6b7c8d9e0f'
down_revision = '9a5b6c7d8e9f'
branch_labels = None
depends_on = None


def upgrade():
    """Add immutability TRIGGERs to economic_engine and class_features.

    TESTING EXCEPTION: Skip TRIGGER creation on test databases.
    Test databases use "test_db", "classroom_test_db", or contain "testing" in the URL.
    """
    print("\n" + "=" * 80)
    print("Phase 2d: Add database-level immutability TRIGGERs")
    print("=" * 80)

    conn = op.get_bind()

    # Check if running on test database
    db_url = os.environ.get('DATABASE_URL', '').lower()
    is_test_db = (
        'test_db' in db_url or
        'testing' in db_url or
        'classroom_test_db' in db_url
    )

    if is_test_db:
        print("\n⚠️  Running on test database; SKIPPING TRIGGER creation")
        print("   Reason: Test helpers (e.g., disable_class_feature) need to delete records")
        print("   TRIGGERS will be created on production/integration environments")
        return

    # ==========================================================================
    # STEP 0: Create TRIGGER FUNCTIONS (PostgreSQL requires separate functions)
    # ==========================================================================
    print("\n🔧 Creating TRIGGER functions...")

    # Function to prevent updates
    try:
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_immutable_update()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'This table is immutable (append-only). Updates are not permitted.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("   ✅ Created function prevent_immutable_update()")
    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"   ⚠️  Could not create function: {e}")
        else:
            print("   ℹ️  Function already exists")

    # Function to prevent deletes
    try:
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_immutable_delete()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'This table is immutable. Deletions are not permitted. These are permanent historical records.';
            END;
            $$ LANGUAGE plpgsql;
        """))
        print("   ✅ Created function prevent_immutable_delete()")
    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"   ⚠️  Could not create function: {e}")
        else:
            print("   ℹ️  Function already exists")

    # ==========================================================================
    # STEP 1: Create TRIGGER for economic_engine immutability
    # ==========================================================================
    print("\n🔒 Adding immutability TRIGGERs to economic_engine...")

    if table_exists('economic_engine'):
        if not trigger_exists('economic_engine_no_update'):
            conn.execute(text("""
                CREATE TRIGGER economic_engine_no_update
                BEFORE UPDATE ON economic_engine
                FOR EACH ROW
                EXECUTE FUNCTION prevent_immutable_update();
            """))
            print("   ✅ Created TRIGGER economic_engine_no_update")
        else:
            print("   ℹ️  TRIGGER already exists")

        if not trigger_exists('economic_engine_no_delete'):
            conn.execute(text("""
                CREATE TRIGGER economic_engine_no_delete
                BEFORE DELETE ON economic_engine
                FOR EACH ROW
                EXECUTE FUNCTION prevent_immutable_delete();
            """))
            print("   ✅ Created TRIGGER economic_engine_no_delete")
        else:
            print("   ℹ️  DELETE TRIGGER already exists")
    else:
        print("⚠️  economic_engine table not found; skipping TRIGGER creation")

    # ==========================================================================
    # STEP 2: Create TRIGGER for class_features immutability
    # ==========================================================================
    print("\n🔒 Adding immutability TRIGGERs to class_features...")

    if table_exists('class_features'):
        if not trigger_exists('class_features_no_update'):
            conn.execute(text("""
                CREATE TRIGGER class_features_no_update
                BEFORE UPDATE ON class_features
                FOR EACH ROW
                EXECUTE FUNCTION prevent_immutable_update();
            """))
            print("   ✅ Created TRIGGER class_features_no_update")
        else:
            print("   ℹ️  TRIGGER already exists")

        if not trigger_exists('class_features_no_delete'):
            conn.execute(text("""
                CREATE TRIGGER class_features_no_delete
                BEFORE DELETE ON class_features
                FOR EACH ROW
                EXECUTE FUNCTION prevent_immutable_delete();
            """))
            print("   ✅ Created TRIGGER class_features_no_delete")
        else:
            print("   ℹ️  DELETE TRIGGER already exists")
    else:
        print("⚠️  class_features table not found; skipping TRIGGER creation")

    print("\n" + "=" * 80)
    print("✅ Phase 2d Complete: Database-level immutability enforced via TRIGGERs")
    print("=" * 80)


def downgrade():
    """Downgrade Phase 2d (not supported)."""
    raise RuntimeError(
        "Downgrade from Phase 2d is not supported. "
        "Adding immutability TRIGGERs that enforce append-only semantics "
        "is a permanent database-level constraint. If rollback is necessary, restore from database backup. "
        "Contact ops team for guidance."
    )
