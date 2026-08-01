"""Canonical obligations schema: add internal_ref, correlation_id, viewable_at, bill_cycle_id; create bill_cycles table; fix satisfaction uniqueness

Revision ID: cda78c55185e
Revises: 0006
Create Date: 2026-07-24 07:04:16.372841

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

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

def get_foreign_keys_by_column(table_name, column_name):
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = 'cda78c55185e'
down_revision = '9bb0d3678c86'
# Note: This migration follows 9bb0d3678c86 (redemption_events cleanup)
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # CANONICAL OBLIGATIONS SCHEMA MIGRATION
    # ========================================================================

    # 1. Create bill_cycles table (new canonical table)
    if not table_exists('bill_cycles'):
        op.create_table('bill_cycles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('internal_ref', sa.String(length=200), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('source_version_id', sa.String(length=200), nullable=True),
        sa.Column('cycle_boundary_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('next_assessment_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('internal_ref', 'cycle_number', name='uq_bill_cycles_ref_cycle')
        )
        op.create_index(op.f('ix_bill_cycles_internal_ref'), 'bill_cycles', ['internal_ref'], unique=False)
        print("✅ Created bill_cycles table")
    else:
        print("⚠️  bill_cycles table already exists, skipping...")

    # 2. Add canonical fields to assessment_events
    if not column_exists('assessment_events', 'internal_ref'):
        op.add_column('assessment_events', sa.Column('internal_ref', sa.String(length=200), nullable=False))
        print("✅ Added internal_ref to assessment_events")
    else:
        print("⚠️  internal_ref already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'correlation_id'):
        op.add_column('assessment_events', sa.Column('correlation_id', sa.String(length=200), nullable=False))
        print("✅ Added correlation_id to assessment_events")
    else:
        print("⚠️  correlation_id already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'viewable_at'):
        op.add_column('assessment_events', sa.Column('viewable_at', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added viewable_at to assessment_events")
    else:
        print("⚠️  viewable_at already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'created_at'):
        op.add_column('assessment_events', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
        print("✅ Added created_at to assessment_events")
    else:
        print("⚠️  created_at already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'bill_cycle_id'):
        op.add_column('assessment_events', sa.Column('bill_cycle_id', sa.Integer(), nullable=True))
        print("✅ Added bill_cycle_id to assessment_events")
    else:
        print("⚠️  bill_cycle_id already exists on assessment_events, skipping...")

    # 3. Make amount_snap nullable in assessment_events (per DOM-OBL-001, amounts not stored here)
    if column_exists('assessment_events', 'amount_snap'):
        op.alter_column('assessment_events', 'amount_snap',
                   existing_type=sa.NUMERIC(precision=12, scale=2),
                   nullable=True)
        print("✅ Made amount_snap nullable on assessment_events")

    # 4. Create indexes on canonical fields
    if not index_exists('assessment_events', 'ix_assessment_events_bill_cycle_id'):
        op.create_index(op.f('ix_assessment_events_bill_cycle_id'), 'assessment_events', ['bill_cycle_id'], unique=False)
        print("✅ Created ix_assessment_events_bill_cycle_id")

    if not index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.create_index(op.f('ix_assessment_events_correlation_id'), 'assessment_events', ['correlation_id'], unique=True)
        print("✅ Created ix_assessment_events_correlation_id")

    if not index_exists('assessment_events', 'ix_assessment_events_internal_ref'):
        op.create_index(op.f('ix_assessment_events_internal_ref'), 'assessment_events', ['internal_ref'], unique=False)
        print("✅ Created ix_assessment_events_internal_ref")

    # 5. Create FK from assessment_events to bill_cycles
    if not foreign_key_exists('assessment_events', 'assessment_events_bill_cycle_id_fkey'):
        op.create_foreign_key(None, 'assessment_events', 'bill_cycles', ['bill_cycle_id'], ['id'], ondelete='SET NULL')
        print("✅ Created FK: assessment_events.bill_cycle_id → bill_cycles.id")

    # ========================================================================
    # OBLIGATION SATISFACTION SCHEMA MIGRATION
    # ========================================================================
    # Note: obligation_satisfaction is now optional - may not exist if migration 0006+ skipped creating it
    # All these changes will be skipped if the table doesn't exist (will be handled by migration 0008)

    if table_exists('obligation_satisfaction'):
        # 6. Fix obligation_satisfaction to allow multiple PAYMENT events
        # Remove unique constraint on assessment_id and add it back as non-unique index
        if index_exists('obligation_satisfaction', 'ix_obligation_satisfaction_assessment_id') and \
           'ix_obligation_satisfaction_assessment_id' in [
               idx['name'] for idx in sa.inspect(op.get_bind()).get_indexes('obligation_satisfaction')
               if idx.get('unique')
           ]:
            # The old index is unique; need to drop and recreate as non-unique
            op.drop_index(op.f('ix_obligation_satisfaction_assessment_id'), table_name='obligation_satisfaction')
            op.create_index(op.f('ix_obligation_satisfaction_assessment_id'), 'obligation_satisfaction', ['assessment_id'], unique=False)
            print("✅ Changed ix_obligation_satisfaction_assessment_id from unique to non-unique")

        # 7. Add canonical satisfaction fields
        if not column_exists('obligation_satisfaction', 'ledger_transaction_id'):
            op.add_column('obligation_satisfaction', sa.Column('ledger_transaction_id', sa.Integer(), nullable=True))
            print("✅ Added ledger_transaction_id to obligation_satisfaction")
        else:
            print("⚠️  ledger_transaction_id already exists on obligation_satisfaction, skipping...")

        if not column_exists('obligation_satisfaction', 'occurred_at'):
            op.add_column('obligation_satisfaction', sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False))
            print("✅ Added occurred_at to obligation_satisfaction")
        else:
            print("⚠️  occurred_at already exists on obligation_satisfaction, skipping...")

        if not column_exists('obligation_satisfaction', 'created_at'):
            op.add_column('obligation_satisfaction', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
            print("✅ Added created_at to obligation_satisfaction")
        else:
            print("⚠️  created_at already exists on obligation_satisfaction, skipping...")

        # 8. Remove legacy derived fields (per DOM-OBL-001 Section VIII)
        legacy_cols = ['amount_paid', 'was_late', 'late_fee_charged', 'satisfied_at', 'transaction_id']
        for col_name in legacy_cols:
            if column_exists('obligation_satisfaction', col_name):
                op.drop_column('obligation_satisfaction', col_name)
                print(f"✅ Dropped legacy column {col_name} from obligation_satisfaction")

        # 9. Create/fix indexes on satisfaction table
        if not index_exists('obligation_satisfaction', 'ix_obligation_satisfaction_ledger_transaction_id'):
            op.create_index(op.f('ix_obligation_satisfaction_ledger_transaction_id'), 'obligation_satisfaction', ['ledger_transaction_id'], unique=False)
            print("✅ Created ix_obligation_satisfaction_ledger_transaction_id")

        # 10. Create FK from satisfaction to ledger
        if not foreign_key_exists('obligation_satisfaction', 'obligation_satisfaction_ledger_transaction_id_fkey'):
            op.create_foreign_key(None, 'obligation_satisfaction', 'ledger_transaction', ['ledger_transaction_id'], ['id'], ondelete='SET NULL')
            print("✅ Created FK: obligation_satisfaction.ledger_transaction_id → ledger_transaction.id")
    else:
        print("⏭️  obligation_satisfaction table does not exist (will be handled by migration 0008)")

    # Note: Other Alembic-detected changes are handled separately in other migrations.
    # This migration focuses exclusively on canonical obligations schema evolution.


def downgrade():
    print("ℹ️  Downgrading canonical obligations schema...")
    print("⚠️  WARNING: Downgrade of canonical obligations schema is not fully implemented.")
    print("The upgrade added canonical fields (internal_ref, correlation_id, bill_cycles table, etc).")
    print("To fully downgrade, restore from a database backup or create a targeted downgrade migration.")

    if table_exists('bill_cycles'):
        op.drop_index(op.f('ix_bill_cycles_internal_ref'), table_name='bill_cycles')
        op.drop_table('bill_cycles')
        print("✅ Dropped bill_cycles table")

    print("⚠️  Downgrade incomplete. Manual database intervention may be required.")
    # ### end Alembic commands ###
