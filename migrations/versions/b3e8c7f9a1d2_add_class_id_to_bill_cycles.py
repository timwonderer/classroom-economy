"""Add class_id to bill_cycles for multi-tenancy scoping

Revision ID: b3e8c7f9a1d2
Revises: 8186458304e5
Create Date: 2026-07-26 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# ============================================================================
# IDEMPOTENCY HELPERS
# ============================================================================

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
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

# ============================================================================
# MIGRATION
# ============================================================================

revision = 'b3e8c7f9a1d2'
down_revision = '8186458304e5'
branch_labels = None
depends_on = None


def upgrade():
    """Add class_id column to bill_cycles for INV-CORE-000 multi-tenancy scoping."""
    # Add class_id column (nullable initially for existing data)
    if not column_exists('bill_cycles', 'class_id'):
        op.add_column('bill_cycles', sa.Column('class_id', sa.String(length=36), nullable=True))
        print("✅ Added class_id column to bill_cycles")
    else:
        print("⚠️  class_id column already exists on bill_cycles, skipping...")

    # Create index on class_id for query performance
    if not index_exists('bill_cycles', 'ix_bill_cycles_class_id'):
        op.create_index('ix_bill_cycles_class_id', 'bill_cycles', ['class_id'], unique=False)
        print("✅ Created index ix_bill_cycles_class_id")
    else:
        print("⚠️  Index ix_bill_cycles_class_id already exists, skipping...")

    # Create foreign key constraint linking to classes
    if not foreign_key_exists('bill_cycles', 'fk_bill_cycles_class_id_classes'):
        op.create_foreign_key(
            'fk_bill_cycles_class_id_classes',
            'bill_cycles',
            'classes',
            ['class_id'],
            ['class_id'],
            ondelete='CASCADE'
        )
        print("✅ Created foreign key fk_bill_cycles_class_id_classes")
    else:
        print("⚠️  Foreign key fk_bill_cycles_class_id_classes already exists, skipping...")


def downgrade():
    """Remove class_id column from bill_cycles."""
    # Drop foreign key if it exists
    if foreign_key_exists('bill_cycles', 'fk_bill_cycles_class_id_classes'):
        op.drop_constraint('fk_bill_cycles_class_id_classes', 'bill_cycles', type_='foreignkey')
        print("❌ Dropped foreign key fk_bill_cycles_class_id_classes")
    else:
        print("⚠️  Foreign key fk_bill_cycles_class_id_classes does not exist, skipping...")

    # Drop index if it exists
    if index_exists('bill_cycles', 'ix_bill_cycles_class_id'):
        op.drop_index('ix_bill_cycles_class_id', table_name='bill_cycles')
        print("❌ Dropped index ix_bill_cycles_class_id")
    else:
        print("⚠️  Index ix_bill_cycles_class_id does not exist, skipping...")

    # Drop column if it exists
    if column_exists('bill_cycles', 'class_id'):
        op.drop_column('bill_cycles', 'class_id')
        print("❌ Dropped class_id column from bill_cycles")
    else:
        print("⚠️  class_id column does not exist on bill_cycles, skipping...")
