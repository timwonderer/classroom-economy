"""Add entitlement_grants, entitlement_consumptions, insurance_claims tables; drop StorePurchase mutable counter columns

Revision ID: 1761e2187234
Revises: f83ba4e63062
Create Date: 2026-07-23 04:08:08.444512

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '1761e2187234'
down_revision = 'f83ba4e63062'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False

def enum_type_exists(enum_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return enum_name in {row[0] for row in conn.execute(sa.text(
            "SELECT t.typname FROM pg_type t WHERE t.typcategory = 'E'"
        ))}
    except Exception:
        return False

def create_enum_type(enum_name, values):
    quoted_values = ", ".join(f"'{value}'" for value in values)
    op.execute(sa.text(f"""
        DO $$
        BEGIN
            CREATE TYPE {enum_name} AS ENUM ({quoted_values});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
    """))


# ============================================================================
# MIGRATION
# ============================================================================

def upgrade():
    create_enum_type('grant_type_enum', ('PURCHASE', 'MANUAL_GRANT', 'OBLIGATION'))
    create_enum_type('disposition_enum', ('CONSUMED', 'EXPIRED', 'REVOKED'))
    create_enum_type('insurance_claim_type_enum', ('TRANSACTION', 'PRODUCTIVITY', 'NON_MONETARY'))
    create_enum_type('insurance_claim_status_enum', ('SUBMITTED', 'APPROVED', 'REJECTED'))

    # --- 1. Create entitlement_grants (DOM-STORE-001 §XII.A) ---
    if not table_exists('entitlement_grants'):
        op.create_table('entitlement_grants',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('entitlement_id', sa.String(length=36), nullable=False),
            sa.Column('entitlement_item_id', sa.Integer(), nullable=False),
            sa.Column('target_seat_id', sa.Integer(), nullable=False),
            sa.Column('actor_seat_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('grant_type', postgresql.ENUM('PURCHASE', 'MANUAL_GRANT', 'OBLIGATION', name='grant_type_enum', create_type=False), nullable=False),
            sa.Column('correlation_id', sa.String(length=100), nullable=True),
            sa.Column('purchase_id', sa.Integer(), nullable=True),
            sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['actor_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['entitlement_item_id'], ['store_items.id']),
            sa.ForeignKeyConstraint(['purchase_id'], ['store_purchases.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['target_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_entitlement_grants_entitlement_id'), 'entitlement_grants', ['entitlement_id'], unique=True)
        op.create_index(op.f('ix_entitlement_grants_entitlement_item_id'), 'entitlement_grants', ['entitlement_item_id'], unique=False)
        op.create_index(op.f('ix_entitlement_grants_target_seat_id'), 'entitlement_grants', ['target_seat_id'], unique=False)
        op.create_index(op.f('ix_entitlement_grants_actor_seat_id'), 'entitlement_grants', ['actor_seat_id'], unique=False)
        op.create_index(op.f('ix_entitlement_grants_class_id'), 'entitlement_grants', ['class_id'], unique=False)
        op.create_index(op.f('ix_entitlement_grants_correlation_id'), 'entitlement_grants', ['correlation_id'], unique=False)
        op.create_index(op.f('ix_entitlement_grants_purchase_id'), 'entitlement_grants', ['purchase_id'], unique=False)
        op.create_index('ix_entitlement_grants_target_class', 'entitlement_grants', ['target_seat_id', 'class_id'], unique=False)
        op.create_index('ix_entitlement_grants_item_class', 'entitlement_grants', ['entitlement_item_id', 'class_id'], unique=False)
        print("✅ Created entitlement_grants table")
    else:
        print("⚠️  entitlement_grants already exists, skipping")

    # --- 2. Create entitlement_consumptions (DOM-STORE-001 §XII.C) ---
    if not table_exists('entitlement_consumptions'):
        op.create_table('entitlement_consumptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('entitlement_consumption_id', sa.String(length=36), nullable=False),
            sa.Column('entitlement_id', sa.String(length=36), nullable=False),
            sa.Column('disposition', postgresql.ENUM('CONSUMED', 'EXPIRED', 'REVOKED', name='disposition_enum', create_type=False), nullable=False),
            sa.Column('actor_seat_id', sa.Integer(), nullable=True),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('correlation_id', sa.String(length=100), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['actor_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('entitlement_id', 'disposition', name='uq_entitlement_terminal_event'),
        )
        op.create_index(op.f('ix_entitlement_consumptions_entitlement_consumption_id'), 'entitlement_consumptions', ['entitlement_consumption_id'], unique=True)
        op.create_index(op.f('ix_entitlement_consumptions_entitlement_id'), 'entitlement_consumptions', ['entitlement_id'], unique=False)
        op.create_index(op.f('ix_entitlement_consumptions_actor_seat_id'), 'entitlement_consumptions', ['actor_seat_id'], unique=False)
        op.create_index(op.f('ix_entitlement_consumptions_class_id'), 'entitlement_consumptions', ['class_id'], unique=False)
        op.create_index(op.f('ix_entitlement_consumptions_correlation_id'), 'entitlement_consumptions', ['correlation_id'], unique=False)
        print("✅ Created entitlement_consumptions table")
    else:
        print("⚠️  entitlement_consumptions already exists, skipping")

    # --- 3. Create insurance_claims (FEAT-STOR-003) ---
    if not table_exists('insurance_claims'):
        op.create_table('insurance_claims',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('insurance_claim_id', sa.String(length=36), nullable=False),
            sa.Column('entitlement_id', sa.String(length=36), nullable=False),
            sa.Column('target_seat_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('claim_type', postgresql.ENUM('TRANSACTION', 'PRODUCTIVITY', 'NON_MONETARY', name='insurance_claim_type_enum', create_type=False), nullable=False),
            sa.Column('status', postgresql.ENUM('SUBMITTED', 'APPROVED', 'REJECTED', name='insurance_claim_status_enum', create_type=False), nullable=False),
            sa.Column('referenced_transaction_id', sa.Integer(), nullable=True),
            sa.Column('referenced_dates', sa.JSON(), nullable=True),
            sa.Column('claim_basis', sa.Text(), nullable=True),
            sa.Column('decision_notes', sa.Text(), nullable=True),
            sa.Column('decided_by_seat_id', sa.Integer(), nullable=True),
            sa.Column('correlation_id', sa.String(length=100), nullable=True),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['decided_by_seat_id'], ['seats.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['referenced_transaction_id'], ['ledger_transaction.id']),
            sa.ForeignKeyConstraint(['target_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_insurance_claims_insurance_claim_id'), 'insurance_claims', ['insurance_claim_id'], unique=True)
        op.create_index(op.f('ix_insurance_claims_entitlement_id'), 'insurance_claims', ['entitlement_id'], unique=False)
        op.create_index(op.f('ix_insurance_claims_target_seat_id'), 'insurance_claims', ['target_seat_id'], unique=False)
        op.create_index(op.f('ix_insurance_claims_class_id'), 'insurance_claims', ['class_id'], unique=False)
        op.create_index(op.f('ix_insurance_claims_decided_by_seat_id'), 'insurance_claims', ['decided_by_seat_id'], unique=False)
        op.create_index(op.f('ix_insurance_claims_referenced_transaction_id'), 'insurance_claims', ['referenced_transaction_id'], unique=False)
        op.create_index(op.f('ix_insurance_claims_correlation_id'), 'insurance_claims', ['correlation_id'], unique=False)
        op.create_index('ix_insurance_claims_entitlement_class', 'insurance_claims', ['entitlement_id', 'class_id'], unique=False)
        print("✅ Created insurance_claims table")
    else:
        print("⚠️  insurance_claims already exists, skipping")

    # --- 4. Drop misaligned mutable counter columns from store_purchases ---
    if column_exists('store_purchases', 'uses_remaining'):
        op.drop_column('store_purchases', 'uses_remaining')
        print("✅ Dropped store_purchases.uses_remaining")

    if column_exists('store_purchases', 'bundle_remaining'):
        op.drop_column('store_purchases', 'bundle_remaining')
        print("✅ Dropped store_purchases.bundle_remaining")

    if column_exists('store_purchases', 'is_from_bundle'):
        op.drop_column('store_purchases', 'is_from_bundle')
        print("✅ Dropped store_purchases.is_from_bundle")

    # --- 5. Migrate RedemptionEventAction enum values to uppercase ---
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE redemption_events ALTER COLUMN action TYPE VARCHAR(20);
        DROP TYPE IF EXISTS redemption_event_action_enum;
        CREATE TYPE redemption_event_action_enum AS ENUM ('REQUEST', 'APPROVED', 'REJECTED');
        UPDATE redemption_events SET action = UPPER(action) WHERE action != UPPER(action);
        ALTER TABLE redemption_events ALTER COLUMN action TYPE redemption_event_action_enum
            USING action::redemption_event_action_enum;
    """))
    print("✅ Updated redemption_events.action enum to uppercase values")

    # --- 6. Drop legacy v1 store tables not in canonical DOM-STORE-001 ---
    for legacy_table in ('student_items', 'store_item_blocks', 'redemption_audit_logs'):
        if table_exists(legacy_table):
            op.drop_table(legacy_table)
            print(f"✅ Dropped legacy table {legacy_table}")
        else:
            print(f"⚠️  Legacy table {legacy_table} does not exist, skipping")


def downgrade():
    # --- Reverse legacy table drops (minimal schema only) ---
    # Legacy tables are not recreated with full schema — they are unauthorized under DOM-STORE-001.

    # --- Restore mutable counter columns on store_purchases ---
    if not column_exists('store_purchases', 'is_from_bundle'):
        op.add_column('store_purchases', sa.Column('is_from_bundle', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    if not column_exists('store_purchases', 'bundle_remaining'):
        op.add_column('store_purchases', sa.Column('bundle_remaining', sa.Integer(), nullable=True))
    if not column_exists('store_purchases', 'uses_remaining'):
        op.add_column('store_purchases', sa.Column('uses_remaining', sa.Integer(), nullable=True))

    # --- Revert enum values to lowercase ---
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE redemption_events ALTER COLUMN action TYPE VARCHAR(20);
        DROP TYPE IF EXISTS redemption_event_action_enum;
        CREATE TYPE redemption_event_action_enum AS ENUM ('request', 'approved', 'rejected');
        UPDATE redemption_events SET action = LOWER(action) WHERE action != LOWER(action);
        ALTER TABLE redemption_events ALTER COLUMN action TYPE redemption_event_action_enum
            USING action::redemption_event_action_enum;
    """))

    # --- Drop new tables ---
    if table_exists('insurance_claims'):
        op.drop_table('insurance_claims')
    if table_exists('entitlement_consumptions'):
        op.drop_table('entitlement_consumptions')
    if table_exists('entitlement_grants'):
        op.drop_table('entitlement_grants')

    # --- Drop enum types ---
    op.execute("DROP TYPE IF EXISTS grant_type_enum")
    op.execute("DROP TYPE IF EXISTS disposition_enum")
    op.execute("DROP TYPE IF EXISTS insurance_claim_type_enum")
    op.execute("DROP TYPE IF EXISTS insurance_claim_status_enum")
