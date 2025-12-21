"""Fix deletionrequeststatus enum case and type

Revision ID: fa40lzegx5tq
Revises: 5esz32blgjej
Create Date: 2025-12-02 06:30:00.000000

This migration fixes the DeletionRequestStatus column issues:
1. The original migration created status as String(20) instead of an Enum
2. Some data may have been stored as uppercase ('PENDING') instead of lowercase ('pending')
3. The Python enum expects lowercase values: 'pending', 'approved', 'rejected'

This migration:
- Creates the PostgreSQL enum type 'deletionrequeststatus' with lowercase values
- Converts any existing uppercase values to lowercase
- Changes the status column from String to Enum type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'fa40lzegx5tq'
down_revision = '5esz32blgjej'
branch_labels = None
depends_on = None


def upgrade():
    """
    Convert status column from String to Enum with lowercase values.
    This migration is idempotent and safe to run multiple times.
    """
    conn = op.get_bind()
    
    # Check if we're running on PostgreSQL
    if conn.dialect.name != 'postgresql':
        print("⚠️  This migration is PostgreSQL-specific, skipping on non-PostgreSQL database")
        # For SQLite (testing), the column is already String which is fine
        return
    
    # Step 1: Check if the table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'deletion_requests'
        )
    """))
    table_exists = result.scalar()
    
    if not table_exists:
        print("ℹ️  deletion_requests table does not exist, nothing to fix")
        return
    
    print("🔧 Fixing DeletionRequestStatus enum...")
    
    # Step 2: Check if enum type already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequeststatus')"
    ))
    enum_exists = result.scalar()
    
    # Step 3: Update any existing uppercase values to lowercase
    print("  Step 1: Converting any uppercase status values to lowercase...")
    result = conn.execute(sa.text("""
        SELECT COUNT(*) FROM deletion_requests 
        WHERE status IN ('PENDING', 'APPROVED', 'REJECTED')
    """))
    uppercase_count = result.scalar()
    
    if uppercase_count > 0:
        print(f"  ℹ️  Found {uppercase_count} rows with uppercase status values, converting...")
        conn.execute(sa.text("""
            UPDATE deletion_requests 
            SET status = LOWER(status) 
            WHERE status IN ('PENDING', 'APPROVED', 'REJECTED')
        """))
        print(f"  ✓ Converted {uppercase_count} rows to lowercase")
    else:
        print("  ℹ️  No uppercase status values found")
    
    # Step 4: Create the enum type if it doesn't exist
    if not enum_exists:
        print("  Step 2: Creating deletionrequeststatus enum type...")
        conn.execute(sa.text(
            "CREATE TYPE deletionrequeststatus AS ENUM ('pending', 'approved', 'rejected')"
        ))
        print("  ✓ Created deletionrequeststatus enum type")
    else:
        print("  ℹ️  deletionrequeststatus enum type already exists")
        
        # Verify it has the correct values
        result = conn.execute(sa.text("""
            SELECT enumlabel FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'deletionrequeststatus')
            ORDER BY enumlabel
        """))
        current_values = sorted([row[0] for row in result])
        expected_values = ['approved', 'pending', 'rejected']
        
        if current_values != expected_values:
            print(f"  ⚠️  Enum has unexpected values: {current_values}")
            print(f"  Expected: {expected_values}")
            raise ValueError(
                f"deletionrequeststatus enum has unexpected values: {current_values}. "
                f"Expected: {expected_values}. "
                f"To fix this, you can recreate the enum manually:\n"
                f"  DROP TYPE deletionrequeststatus CASCADE;\n"
                f"  CREATE TYPE deletionrequeststatus AS ENUM ('pending', 'approved', 'rejected');\n"
                f"  ALTER TABLE deletion_requests ALTER COLUMN status TYPE deletionrequeststatus USING status::text::deletionrequeststatus;"
            )
    
    # Step 5: Check the current column type
    result = conn.execute(sa.text("""
        SELECT data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'deletion_requests' AND column_name = 'status'
    """))
    row = result.fetchone()
    current_type = row[1] if row else None
    
    print(f"  ℹ️  Current status column type: {current_type}")
    
    # Step 6: Convert column to enum if it's not already
    if current_type != 'deletionrequeststatus':
        print("  Step 3: Converting status column from String to Enum...")
        
        # First, check all values are valid
        result = conn.execute(sa.text("""
            SELECT DISTINCT status FROM deletion_requests
        """))
        stored_values = [row[0] for row in result]
        valid_values = {'pending', 'approved', 'rejected'}
        invalid_values = [v for v in stored_values if v not in valid_values]
        
        if invalid_values:
            raise ValueError(
                f"Found invalid status values in deletion_requests: {invalid_values}. "
                f"Expected only 'pending', 'approved', or 'rejected'. "
                f"Please fix these values before running this migration."
            )
        
        # Drop the default constraint before converting the column type
        # PostgreSQL can't automatically cast string defaults to enum
        print("  Step 3a: Dropping default constraint...")
        conn.execute(sa.text("""
            ALTER TABLE deletion_requests 
            ALTER COLUMN status DROP DEFAULT
        """))
        print("  ✓ Dropped default constraint")
        
        # Convert the column type
        print("  Step 3b: Converting column type to enum...")
        conn.execute(sa.text("""
            ALTER TABLE deletion_requests 
            ALTER COLUMN status TYPE deletionrequeststatus 
            USING status::deletionrequeststatus
        """))
        print("  ✓ Converted status column to deletionrequeststatus enum")
        
        # Recreate the default constraint with the proper enum value
        print("  Step 3c: Recreating default constraint...")
        conn.execute(sa.text("""
            ALTER TABLE deletion_requests 
            ALTER COLUMN status SET DEFAULT 'pending'::deletionrequeststatus
        """))
        print("  ✓ Recreated default constraint")
    else:
        print("  ✓ Status column is already deletionrequeststatus enum type")
    
    print("✅ Successfully fixed DeletionRequestStatus enum")


def downgrade():
    """
    Convert status column back from Enum to String.
    """
    conn = op.get_bind()
    
    if conn.dialect.name != 'postgresql':
        print("⚠️  This migration is PostgreSQL-specific, skipping on non-PostgreSQL database")
        return
    
    # Check if the table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'deletion_requests'
        )
    """))
    table_exists = result.scalar()
    
    if not table_exists:
        print("ℹ️  deletion_requests table does not exist, nothing to downgrade")
        return
    
    print("⚠️  Downgrading status column from Enum to String...")
    
    # Drop the default constraint before converting the column type
    conn.execute(sa.text("""
        ALTER TABLE deletion_requests 
        ALTER COLUMN status DROP DEFAULT
    """))
    print("  ✓ Dropped enum default constraint")
    
    # Convert column back to String
    conn.execute(sa.text("""
        ALTER TABLE deletion_requests 
        ALTER COLUMN status TYPE VARCHAR(20) 
        USING status::text
    """))
    print("  ✓ Converted status column back to String")
    
    # Recreate the string default
    conn.execute(sa.text("""
        ALTER TABLE deletion_requests 
        ALTER COLUMN status SET DEFAULT 'pending'
    """))
    print("  ✓ Recreated string default constraint")
    
    # Drop the enum type
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequeststatus')"
    ))
    enum_exists = result.scalar()
    
    if enum_exists:
        conn.execute(sa.text("DROP TYPE deletionrequeststatus"))
        print("  ✓ Dropped deletionrequeststatus enum type")
    
    print("✅ Downgrade complete")
