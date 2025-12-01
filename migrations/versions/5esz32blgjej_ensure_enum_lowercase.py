"""Ensure deletionrequesttype enum values are lowercase

Revision ID: 5esz32blgjej
Revises: nvlu271s3hgq
Create Date: 2025-12-01 20:35:00.000000

This migration ensures that the deletionrequesttype enum in the database
has lowercase values ('period', 'account') to match the Python enum values.

This is critical because:
1. Python enum DeletionRequestType has values: 'period', 'account'
2. The database enum might have: 'PERIOD', 'ACCOUNT'
3. When data is stored as lowercase but enum expects uppercase, queries fail
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5esz32blgjej'
down_revision = 'nvlu271s3hgq'
branch_labels = None
depends_on = None


def upgrade():
    """
    Ensure the enum has lowercase values that match the Python enum.
    This migration is idempotent and safe to run multiple times.
    
    NOTE: This migration is PostgreSQL-specific as it handles PostgreSQL ENUMs.
    The application requires PostgreSQL in production.
    """
    conn = op.get_bind()
    
    # Check if we're running on PostgreSQL
    if conn.dialect.name != 'postgresql':
        print("⚠️  This migration is PostgreSQL-specific, skipping on non-PostgreSQL database")
        return
    
    # Check if the enum type exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequesttype')"
    ))
    enum_exists = result.scalar()
    
    if not enum_exists:
        print("ℹ️  deletionrequesttype enum does not exist, creating it with lowercase values")
        deletionrequesttype = postgresql.ENUM('period', 'account', name='deletionrequesttype')
        deletionrequesttype.create(op.get_bind())
        print("✅ Created deletionrequesttype enum with lowercase values")
        return
    
    # Check current enum values
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'deletionrequesttype')
        ORDER BY enumlabel
    """))
    current_values = [row[0] for row in result]
    
    print(f"ℹ️  Current enum values: {current_values}")
    
    # Check if values are correct (lowercase)
    expected_lowercase = ['account', 'period']
    if sorted(current_values) == sorted(expected_lowercase):
        print("✅ Enum values are already correct (lowercase), no action needed")
        return
    
    # Check if we have uppercase values
    expected_uppercase = ['ACCOUNT', 'PERIOD']
    if sorted(current_values) == sorted(expected_uppercase):
        print("🔧 Fixing enum: converting uppercase to lowercase")
    else:
        print(f"⚠️  Unexpected enum values: {current_values}")
        print("🔧 Attempting to fix...")
    
    # Strategy: Create new enum with correct values, convert column, drop old enum
    
    # Step 1: Create temporary enum with lowercase values
    print("  Step 1: Creating temporary enum with lowercase values...")
    try:
        conn.execute(sa.text("CREATE TYPE deletionrequesttype_temp AS ENUM ('period', 'account')"))
    except Exception as e:
        # If temp enum already exists, drop and recreate it
        print(f"  ⚠️  Temp enum already exists, dropping and recreating: {e}")
        conn.execute(sa.text("DROP TYPE IF EXISTS deletionrequesttype_temp CASCADE"))
        conn.execute(sa.text("CREATE TYPE deletionrequesttype_temp AS ENUM ('period', 'account')"))
    print("  ✓ Created deletionrequesttype_temp")
    
    # Step 2: Check if deletion_requests table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'deletion_requests'
        )
    """))
    table_exists = result.scalar()
    
    if table_exists:
        print("  Step 2: Converting deletion_requests.request_type column...")
        
        # First, check if there's any data
        result = conn.execute(sa.text("SELECT COUNT(*) FROM deletion_requests"))
        row_count = result.scalar()
        print(f"  ℹ️  Found {row_count} rows in deletion_requests")
        
        if row_count > 0:
            # Check what values are actually stored
            result = conn.execute(sa.text("""
                SELECT DISTINCT request_type::text 
                FROM deletion_requests
            """))
            stored_values = [row[0] for row in result]
            print(f"  ℹ️  Stored values: {stored_values}")
            
            # Validate that all stored values are valid (case-insensitive)
            valid_values = {'period', 'account', 'PERIOD', 'ACCOUNT'}
            invalid_values = [v for v in stored_values if v not in valid_values]
            if invalid_values:
                raise ValueError(
                    f"Found unexpected enum values in deletion_requests: {invalid_values}. "
                    f"Expected only 'period', 'account', 'PERIOD', or 'ACCOUNT'. "
                    f"Please manually fix these values before running this migration."
                )
        
        # Convert the column to use the new enum
        # This handles any combination of uppercase/lowercase in both enum definition and stored data
        conn.execute(sa.text("""
            ALTER TABLE deletion_requests 
            ALTER COLUMN request_type TYPE deletionrequesttype_temp 
            USING CASE 
                WHEN LOWER(request_type::text) = 'period' THEN 'period'::deletionrequesttype_temp
                WHEN LOWER(request_type::text) = 'account' THEN 'account'::deletionrequesttype_temp
            END
        """))
        print("  ✓ Converted request_type column to use temporary enum")
    else:
        print("  ℹ️  deletion_requests table does not exist, skipping column conversion")
    
    # Step 3: Drop old enum
    print("  Step 3: Dropping old enum...")
    conn.execute(sa.text("DROP TYPE deletionrequesttype"))
    print("  ✓ Dropped old deletionrequesttype enum")
    
    # Step 4: Rename new enum to original name
    print("  Step 4: Renaming temporary enum to deletionrequesttype...")
    conn.execute(sa.text("ALTER TYPE deletionrequesttype_temp RENAME TO deletionrequesttype"))
    print("  ✓ Renamed deletionrequesttype_temp to deletionrequesttype")
    
    print("✅ Successfully fixed enum case - all values are now lowercase")


def downgrade():
    """
    This is a fix migration to ensure correct enum values.
    Downgrade would be to restore incorrect uppercase values, which we don't want.
    """
    print("⚠️  This is a fix migration - downgrade would restore incorrect enum values")
    print("⚠️  Downgrade is not implemented as lowercase values should always be used")
    pass
