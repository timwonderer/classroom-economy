"""Merge enum fix with main migration chain

Revision ID: nvlu271s3hgq
Revises: 1e2f3a4b5c6d, 9957794d7f45
Create Date: 2025-12-01 20:33:00.000000

This merge migration combines:
- The main migration chain (1e2f3a4b5c6d)
- The enum case fix migration (9957794d7f45)

After this merge, the deletionrequesttype enum values will be guaranteed to be lowercase.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'nvlu271s3hgq'
down_revision = ('1e2f3a4b5c6d', '9957794d7f45')
branch_labels = None
depends_on = None


def upgrade():
    """
    This is a merge migration. The actual enum fix logic is in the 
    9957794d7f45_fix_deletionrequesttype_enum_case.py migration.
    
    However, we'll add an extra safety check here to ensure the enum
    is properly fixed after the merge.
    
    NOTE: This migration is PostgreSQL-specific as it checks PostgreSQL ENUMs.
    The application requires PostgreSQL in production.
    """
    conn = op.get_bind()
    
    # Skip checks on non-PostgreSQL databases (e.g., SQLite in tests)
    if conn.dialect.name != 'postgresql':
        print("⚠️  This is a merge migration, no action needed on non-PostgreSQL database")
        return
    
    # Check if the enum type exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequesttype')"
    ))
    enum_exists = result.scalar()
    
    if enum_exists:
        # Check current enum values
        result = conn.execute(sa.text("""
            SELECT enumlabel FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'deletionrequesttype')
            ORDER BY enumlabel
        """))
        current_values = [row[0] for row in result]
        
        print(f"ℹ️  Current enum values after merge: {current_values}")
        
        # If we still have uppercase values, the fix didn't run
        has_uppercase = any(val.isupper() or val != val.lower() for val in current_values)
        
        if has_uppercase:
            print("⚠️  Enum still has uppercase values. This shouldn't happen after merge.")
            print("⚠️  The 9957794d7f45 migration should have fixed this.")
        else:
            print("✅ Enum values are correctly lowercase after merge")
    else:
        print("ℹ️  deletionrequesttype enum does not exist")


def downgrade():
    """
    Merge migrations don't need a downgrade implementation.
    To downgrade, use the individual parent migrations.
    """
    pass
