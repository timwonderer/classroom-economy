"""Fix deletionrequesttype enum case mismatch

Revision ID: 9957794d7f45
Revises: 3e1b8bd76b40
Create Date: 2025-12-01 17:51:00.000000

This migration fixes the case sensitivity mismatch between PostgreSQL ENUM values
and Python enum values. PostgreSQL may have uppercase values (PERIOD, ACCOUNT) while
Python expects lowercase (period, account). This migration converts any uppercase
values to lowercase.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9957794d7f45'
down_revision = '3e1b8bd76b40'
branch_labels = None
depends_on = None


def upgrade():
    """
    Convert deletionrequesttype enum values from uppercase to lowercase if needed.
    This migration is idempotent and can be run multiple times safely.
    """
    conn = op.get_bind()
    
    # Check if the enum type exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequesttype')"
    ))
    enum_exists = result.scalar()
    
    if not enum_exists:
        print("⚠️  deletionrequesttype enum does not exist, nothing to fix")
        return
    
    # Check current enum values
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'deletionrequesttype')
        ORDER BY enumlabel
    """))
    current_values = [row[0] for row in result]
    
    print(f"ℹ️  Current enum values: {current_values}")
    
    # Check if we have uppercase values that need fixing
    has_uppercase = any(val.isupper() or val != val.lower() for val in current_values)
    
    if not has_uppercase:
        print("✅ Enum values are already lowercase, no fix needed")
        return
    
    print("🔧 Fixing enum case mismatch: converting uppercase values to lowercase")
    
    # PostgreSQL doesn't allow direct enum value changes, so we need to:
    # 1. Create new enum with lowercase values
    # 2. Convert the column to use the new enum
    # 3. Drop old enum and rename new one
    
    # Create new enum with lowercase values
    conn.execute(sa.text("CREATE TYPE deletionrequesttype_new AS ENUM ('period', 'account')"))
    print("  ✓ Created deletionrequesttype_new enum")
    
    # Check if deletion_requests table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'deletion_requests'
        )
    """))
    table_exists = result.scalar()
    
    if table_exists:
        # Convert the column to use the new enum, handling both uppercase and lowercase
        conn.execute(sa.text("""
            ALTER TABLE deletion_requests 
            ALTER COLUMN request_type TYPE deletionrequesttype_new 
            USING CASE 
                WHEN UPPER(request_type::text) = 'PERIOD' THEN 'period'::deletionrequesttype_new
                WHEN UPPER(request_type::text) = 'ACCOUNT' THEN 'account'::deletionrequesttype_new
                ELSE NULL
            END
        """))
        print("  ✓ Converted deletion_requests.request_type column")
    else:
        print("  ⚠️  deletion_requests table does not exist, skipping column conversion")
    
    # Drop old enum
    conn.execute(sa.text("DROP TYPE deletionrequesttype"))
    print("  ✓ Dropped old deletionrequesttype enum")
    
    # Rename new enum to original name
    conn.execute(sa.text("ALTER TYPE deletionrequesttype_new RENAME TO deletionrequesttype"))
    print("  ✓ Renamed deletionrequesttype_new to deletionrequesttype")
    
    print("✅ Fixed enum case mismatch successfully")


def downgrade():
    """
    Downgrade would convert back to uppercase, but this is a fix migration
    so we don't need to implement a true downgrade.
    The fix should always be applied.
    """
    print("⚠️  This is a fix migration, downgrade is not implemented")
    print("⚠️  The lowercase enum values should always be used")
    pass
