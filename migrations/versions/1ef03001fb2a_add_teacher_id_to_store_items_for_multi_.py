"""Add teacher_id to store_items for multi-tenancy

Revision ID: 1ef03001fb2a
Revises: 442439405e6b
Create Date: [keep original timestamp]

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '1ef03001fb2a'
down_revision = '442439405e6b'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
    return fk_name in foreign_keys


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Create the ENUM type first if it doesn't exist
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequesttype')"
    ))
    enum_exists = result.scalar()
    
    if not enum_exists:
        deletionrequesttype = postgresql.ENUM('period', 'account', name='deletionrequesttype')
        deletionrequesttype.create(op.get_bind())
    
    # Add teacher_id to store_items ONLY if it doesn't exist
    if not column_exists('store_items', 'teacher_id'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
        print("✅ Added teacher_id column to store_items")
    else:
        print("⚠️  Column 'teacher_id' already exists on 'store_items', skipping column creation...")
    
    # Add foreign key constraint ONLY if it doesn't exist
    if not foreign_key_exists('store_items', 'fk_store_items_teacher'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_store_items_teacher', 'admins', ['teacher_id'], ['id'])
        print("✅ Added foreign key constraint fk_store_items_teacher")
    else:
        print("⚠️  Foreign key 'fk_store_items_teacher' already exists on 'store_items', skipping...")
    
    # Backfill store_items.teacher_id with first admin
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.scalar()
    
    if first_admin_id:
        # Only update NULL values to avoid overwriting existing data
        result = conn.execute(sa.text("UPDATE store_items SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        if result.rowcount > 0:
            print(f"✅ Backfilled {result.rowcount} store_items with teacher_id = {first_admin_id}")
        
        # Make it NOT NULL only if it's currently nullable
        columns = inspector.get_columns('store_items')
        teacher_id_col = next((col for col in columns if col['name'] == 'teacher_id'), None)
        if teacher_id_col and teacher_id_col.get('nullable', True):
            with op.batch_alter_table('store_items', schema=None) as batch_op:
                batch_op.alter_column('teacher_id', nullable=False)
            print("✅ Set teacher_id to NOT NULL")
        else:
            print("⚠️  Column 'teacher_id' is already NOT NULL, skipping...")
    
    # Handle deletion_requests table if it exists
    if 'deletion_requests' in inspector.get_table_names():
        # Check if already an enum type
        result = conn.execute(sa.text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'deletion_requests' AND column_name = 'request_type'
        """))
        current_type = result.scalar()
        
        if current_type and 'deletionrequesttype' not in current_type.lower():
            # Convert with proper case handling
            conn.execute(sa.text("""
                ALTER TABLE deletion_requests 
                ALTER COLUMN request_type TYPE deletionrequesttype 
                USING CASE 
                    WHEN LOWER(request_type::text) = 'period' THEN 'period'::deletionrequesttype
                    WHEN LOWER(request_type::text) = 'account' THEN 'account'::deletionrequesttype
                    ELSE NULL
                END
            """))
            print("✅ Converted request_type column to enum type with case handling")
        else:
            print("⚠️  Column 'request_type' is already using enum type, skipping conversion...")


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Drop foreign key constraint from store_items if it exists
    if foreign_key_exists('store_items', 'fk_store_items_teacher'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.drop_constraint('fk_store_items_teacher', type_='foreignkey')
        print("❌ Dropped foreign key constraint fk_store_items_teacher")
    else:
        print("⚠️  Foreign key 'fk_store_items_teacher' does not exist, skipping...")
    
    # Drop column from store_items if it exists
    if column_exists('store_items', 'teacher_id'):
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.drop_column('teacher_id')
        print("❌ Dropped teacher_id column from store_items")
    else:
        print("⚠️  Column 'teacher_id' does not exist on 'store_items', skipping...")
    
    # Revert deletion_requests if it exists
    if 'deletion_requests' in inspector.get_table_names():
        # Convert back to VARCHAR
        conn.execute(sa.text(
            "ALTER TABLE deletion_requests ALTER COLUMN request_type TYPE VARCHAR(50) USING request_type::text"
        ))
    
    # Drop the enum type
    deletionrequesttype = postgresql.ENUM('period', 'account', name='deletionrequesttype')
    deletionrequesttype.drop(op.get_bind(), checkfirst=True)
