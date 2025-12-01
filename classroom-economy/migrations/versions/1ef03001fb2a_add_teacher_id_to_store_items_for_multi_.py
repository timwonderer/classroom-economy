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


def upgrade():
    conn = op.get_bind()
    
    # Create the ENUM type first if it doesn't exist
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deletionrequesttype')"
    ))
    enum_exists = result.scalar()
    
    if not enum_exists:
        deletionrequesttype = postgresql.ENUM('full_account', 'student_data_only', name='deletionrequesttype')
        deletionrequesttype.create(op.get_bind())
    
    # Add teacher_id to store_items
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_store_items_teacher', 'admins', ['teacher_id'], ['id'])
    
    # Backfill store_items.teacher_id with first admin
    result = conn.execute(sa.text("SELECT id FROM admins ORDER BY id LIMIT 1"))
    first_admin_id = result.scalar()
    
    if first_admin_id:
        conn.execute(sa.text("UPDATE store_items SET teacher_id = :admin_id WHERE teacher_id IS NULL"), {"admin_id": first_admin_id})
        
        # Make it NOT NULL
        with op.batch_alter_table('store_items', schema=None) as batch_op:
            batch_op.alter_column('teacher_id', nullable=False)
    
    # Handle deletion_requests table if it exists
    inspector = sa.inspect(conn)
    if 'deletion_requests' in inspector.get_table_names():
        # Use raw SQL with USING clause for type conversion
        conn.execute(sa.text(
            "ALTER TABLE deletion_requests ALTER COLUMN request_type TYPE deletionrequesttype USING request_type::deletionrequesttype"
        ))


def downgrade():
    # Drop foreign key and column from store_items
    with op.batch_alter_table('store_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_store_items_teacher', type_='foreignkey')
        batch_op.drop_column('teacher_id')
    
    # Revert deletion_requests if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'deletion_requests' in inspector.get_table_names():
        # Convert back to VARCHAR
        conn.execute(sa.text(
            "ALTER TABLE deletion_requests ALTER COLUMN request_type TYPE VARCHAR(50) USING request_type::text"
        ))
    
    # Drop the enum type
    deletionrequesttype = postgresql.ENUM('full_account', 'student_data_only', name='deletionrequesttype')
    deletionrequesttype.drop(op.get_bind(), checkfirst=True)
