"""Add store_products table (Policies domain)

Revision ID: e13a59b6aa6b
Revises: 4aa06b69d65d
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e13a59b6aa6b'
down_revision = '4aa06b69d65d'
branch_labels = None
depends_on = None


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


# ============================================================================
# MIGRATION
# ============================================================================

def upgrade():
    """Create store_products table (Policies domain)."""
    if not table_exists('store_products'):
        op.create_table(
            'store_products',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('policy_uuid', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_by_seat_id', sa.Integer(), nullable=True),
            sa.Column('is_retired', sa.Boolean(), nullable=False),
            sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_seat_id'], ['seats.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        print("✅ Created store_products table")
    else:
        print("⚠️  Table 'store_products' already exists, skipping creation")

    # Create indexes independently so a partially applied migration can still recover.
    if not index_exists('store_products', 'ix_store_products_policy_uuid'):
        op.create_index('ix_store_products_policy_uuid', 'store_products', ['policy_uuid'], unique=True)
        print("✅ Created index ix_store_products_policy_uuid")

    if not index_exists('store_products', 'ix_store_products_class_id'):
        op.create_index('ix_store_products_class_id', 'store_products', ['class_id'])
        print("✅ Created index ix_store_products_class_id")

    if not index_exists('store_products', 'ix_store_products_class_retired'):
        op.create_index('ix_store_products_class_retired', 'store_products', ['class_id', 'is_retired'])
        print("✅ Created index ix_store_products_class_retired")

    if not index_exists('store_products', 'ix_store_products_class_created'):
        op.create_index('ix_store_products_class_created', 'store_products', ['class_id', 'created_at'])
        print("✅ Created index ix_store_products_class_created")


def downgrade():
    """Drop store_products table."""
    if table_exists('store_products'):
        op.drop_table('store_products')
        print("❌ Dropped store_products table")
    else:
        print("⚠️  Table 'store_products' does not exist, skipping drop")
