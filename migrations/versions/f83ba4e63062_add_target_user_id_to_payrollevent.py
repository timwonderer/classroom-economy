"""Add target_user_id to payroll_event

Revision ID: f83ba4e63062
Revises: f8d9e0f1a2b4
Create Date: 2026-07-22 06:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

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

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

revision = 'f83ba4e63062'
down_revision = 'f8d9e0f1a2b4'
branch_labels = None
depends_on = None


def upgrade():
    """Add target_user_id column to payroll_event for traceability."""

    # Step 1: Add column as nullable (will backfill if needed)
    if not column_exists('payroll_event', 'target_user_id'):
        op.add_column('payroll_event', sa.Column('target_user_id', sa.Integer(), nullable=True))
        print("✅ Added target_user_id column to payroll_event")
    else:
        print("⚠️  Column 'target_user_id' already exists on 'payroll_event', skipping add_column...")

    # Step 2: Backfill from target_seat_id → Seat.user_id
    # For each payroll_event, get the user_id from the associated seat
    print("📝 Backfilling target_user_id from seat.user_id...")
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        UPDATE payroll_event pe
        SET target_user_id = s.user_id
        FROM seats s
        WHERE pe.target_seat_id = s.id
        AND pe.target_user_id IS NULL
    """))
    print(f"📊 Backfilled {result.rowcount} rows")

    # Step 3: Create index
    if not index_exists('payroll_event', 'ix_payroll_event_target_user_id'):
        op.create_index(op.f('ix_payroll_event_target_user_id'), 'payroll_event', ['target_user_id'], unique=False)
        print("✅ Created index ix_payroll_event_target_user_id")
    else:
        print("⚠️  Index 'ix_payroll_event_target_user_id' already exists, skipping...")

    # Step 4: Create foreign key
    if not foreign_key_exists('payroll_event', 'fk_payroll_event_target_user_id_users'):
        op.create_foreign_key(
            'fk_payroll_event_target_user_id_users',
            'payroll_event',
            'users',
            ['target_user_id'],
            ['id'],
            ondelete='CASCADE'
        )
        print("✅ Created foreign key fk_payroll_event_target_user_id_users")
    else:
        print("⚠️  Foreign key already exists, skipping...")

    # Step 5: Make column non-nullable
    print("🔒 Making target_user_id non-nullable...")
    op.alter_column('payroll_event', 'target_user_id', nullable=False)
    print("✅ Migration complete")


def downgrade():
    """Revert target_user_id addition."""

    # Step 1: Drop foreign key if it exists
    fks = op.get_bind().inspector.get_foreign_keys('payroll_event')
    for fk in fks:
        if 'target_user_id' in fk['constrained_columns']:
            op.drop_constraint(fk['name'], 'payroll_event', type_='foreignkey')
            print(f"✅ Dropped foreign key {fk['name']}")

    # Step 2: Drop index
    if index_exists('payroll_event', 'ix_payroll_event_target_user_id'):
        op.drop_index(op.f('ix_payroll_event_target_user_id'), table_name='payroll_event')
        print("✅ Dropped index ix_payroll_event_target_user_id")

    # Step 3: Drop column
    if column_exists('payroll_event', 'target_user_id'):
        op.drop_column('payroll_event', 'target_user_id')
        print("✅ Dropped column target_user_id from payroll_event")

    print("❌ Downgrade complete")
