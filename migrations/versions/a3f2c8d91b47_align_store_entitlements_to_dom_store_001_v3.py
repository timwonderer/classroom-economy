"""Align Store & Entitlements schema to DOM-STORE-001 v3.0

Rename entitlement_grants -> entitlements, align column names and FKs
across entitlement_consumptions and insurance_claims to match v3.0 canonical
persistence contract.

Revision ID: a3f2c8d91b47
Revises: 1761e2187234
Create Date: 2026-07-23 06:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f2c8d91b47'
down_revision = '1761e2187234'
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

def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False


# ============================================================================
# MIGRATION
# ============================================================================

def upgrade():
    # -----------------------------------------------------------------------
    # 1. Rename entitlement_grants -> entitlements
    # -----------------------------------------------------------------------
    if table_exists('entitlement_grants') and not table_exists('entitlements'):
        op.rename_table('entitlement_grants', 'entitlements')
        print("✅ Renamed entitlement_grants -> entitlements")
    elif table_exists('entitlements'):
        print("⚠️  entitlements already exists, skipping rename")

    # 1a. Drop purchase_id column and its FK/index from entitlements
    if column_exists('entitlements', 'purchase_id'):
        # Drop FK constraint first
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        fks = inspector.get_foreign_keys('entitlements')
        for fk in fks:
            if 'purchase_id' in fk.get('constrained_columns', []):
                op.drop_constraint(fk['name'], 'entitlements', type_='foreignkey')
                print(f"✅ Dropped FK {fk['name']} on entitlements.purchase_id")
        # Drop index
        if index_exists('entitlements', 'ix_entitlement_grants_purchase_id'):
            op.drop_index('ix_entitlement_grants_purchase_id', table_name='entitlements')
        op.drop_column('entitlements', 'purchase_id')
        print("✅ Dropped entitlements.purchase_id")

    # 1b. Rename indexes from entitlement_grants_* to entitlements_*
    _rename_index_if_exists('ix_entitlement_grants_entitlement_id', 'ix_entitlements_entitlement_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_entitlement_item_id', 'ix_entitlements_entitlement_item_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_target_seat_id', 'ix_entitlements_target_seat_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_actor_seat_id', 'ix_entitlements_actor_seat_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_class_id', 'ix_entitlements_class_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_correlation_id', 'ix_entitlements_correlation_id', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_target_class', 'ix_entitlements_target_class', 'entitlements')
    _rename_index_if_exists('ix_entitlement_grants_item_class', 'ix_entitlements_item_class', 'entitlements')

    # -----------------------------------------------------------------------
    # 2. Align entitlement_consumptions to v3.0
    # -----------------------------------------------------------------------

    # 2a. Rename entitlement_consumption_id -> consumption_id
    if column_exists('entitlement_consumptions', 'entitlement_consumption_id') and not column_exists('entitlement_consumptions', 'consumption_id'):
        op.alter_column('entitlement_consumptions', 'entitlement_consumption_id', new_column_name='consumption_id')
        print("✅ Renamed entitlement_consumptions.entitlement_consumption_id -> consumption_id")

    # 2b. Rename occurred_at -> timestamp
    if column_exists('entitlement_consumptions', 'occurred_at') and not column_exists('entitlement_consumptions', 'timestamp'):
        op.alter_column('entitlement_consumptions', 'occurred_at', new_column_name='timestamp')
        print("✅ Renamed entitlement_consumptions.occurred_at -> timestamp")

    # 2c. Add target_seat_id
    if not column_exists('entitlement_consumptions', 'target_seat_id'):
        op.add_column('entitlement_consumptions', sa.Column('target_seat_id', sa.Integer(), nullable=True))
        # Backfill from entitlements table where possible
        conn = op.get_bind()
        conn.execute(sa.text("""
            UPDATE entitlement_consumptions ec
            SET target_seat_id = e.target_seat_id
            FROM entitlements e
            WHERE ec.entitlement_id = e.entitlement_id
              AND ec.target_seat_id IS NULL
        """))
        # Now make non-nullable
        op.alter_column('entitlement_consumptions', 'target_seat_id', nullable=False)
        op.create_foreign_key(
            'fk_entitlement_consumptions_target_seat_id',
            'entitlement_consumptions', 'seats',
            ['target_seat_id'], ['id'],
            ondelete='CASCADE',
        )
        if not index_exists('entitlement_consumptions', 'ix_entitlement_consumptions_target_seat_id'):
            op.create_index('ix_entitlement_consumptions_target_seat_id', 'entitlement_consumptions', ['target_seat_id'])
        print("✅ Added entitlement_consumptions.target_seat_id")

    # 2d. Drop notes column
    if column_exists('entitlement_consumptions', 'notes'):
        op.drop_column('entitlement_consumptions', 'notes')
        print("✅ Dropped entitlement_consumptions.notes")

    # 2e. Add FK from entitlement_consumptions.entitlement_id -> entitlements.entitlement_id
    if not foreign_key_exists('entitlement_consumptions', 'fk_entitlement_consumptions_entitlement_id'):
        op.create_foreign_key(
            'fk_entitlement_consumptions_entitlement_id',
            'entitlement_consumptions', 'entitlements',
            ['entitlement_id'], ['entitlement_id'],
        )
        print("✅ Added FK entitlement_consumptions.entitlement_id -> entitlements.entitlement_id")

    # 2f. Rename index for consumption_id
    _rename_index_if_exists(
        'ix_entitlement_consumptions_entitlement_consumption_id',
        'ix_entitlement_consumptions_consumption_id',
        'entitlement_consumptions',
    )

    # -----------------------------------------------------------------------
    # 3. Align insurance_claims to v3.0
    # -----------------------------------------------------------------------

    # 3a. Rename insurance_claim_id -> claim_id
    if column_exists('insurance_claims', 'insurance_claim_id') and not column_exists('insurance_claims', 'claim_id'):
        op.alter_column('insurance_claims', 'insurance_claim_id', new_column_name='claim_id')
        print("✅ Renamed insurance_claims.insurance_claim_id -> claim_id")

    # 3b. Add actor_seat_id
    if not column_exists('insurance_claims', 'actor_seat_id'):
        op.add_column('insurance_claims', sa.Column('actor_seat_id', sa.Integer(), nullable=True))
        # Backfill: actor is same as target for existing rows (student submitted their own claim)
        conn = op.get_bind()
        conn.execute(sa.text("""
            UPDATE insurance_claims SET actor_seat_id = target_seat_id WHERE actor_seat_id IS NULL
        """))
        op.alter_column('insurance_claims', 'actor_seat_id', nullable=False)
        op.create_foreign_key(
            'fk_insurance_claims_actor_seat_id',
            'insurance_claims', 'seats',
            ['actor_seat_id'], ['id'],
            ondelete='CASCADE',
        )
        if not index_exists('insurance_claims', 'ix_insurance_claims_actor_seat_id'):
            op.create_index('ix_insurance_claims_actor_seat_id', 'insurance_claims', ['actor_seat_id'])
        print("✅ Added insurance_claims.actor_seat_id")

    # 3c. Rename referenced_transaction_id -> transaction_id
    if column_exists('insurance_claims', 'referenced_transaction_id') and not column_exists('insurance_claims', 'transaction_id'):
        # Drop existing FK first
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        fks = inspector.get_foreign_keys('insurance_claims')
        for fk in fks:
            if 'referenced_transaction_id' in fk.get('constrained_columns', []):
                op.drop_constraint(fk['name'], 'insurance_claims', type_='foreignkey')
                print(f"✅ Dropped FK {fk['name']} on insurance_claims.referenced_transaction_id")
        # Drop old index
        if index_exists('insurance_claims', 'ix_insurance_claims_referenced_transaction_id'):
            op.drop_index('ix_insurance_claims_referenced_transaction_id', table_name='insurance_claims')
        # Rename column
        op.alter_column('insurance_claims', 'referenced_transaction_id', new_column_name='transaction_id')
        # Recreate FK and index with new name
        op.create_foreign_key(
            'fk_insurance_claims_transaction_id',
            'insurance_claims', 'ledger_transaction',
            ['transaction_id'], ['id'],
        )
        op.create_index('ix_insurance_claims_transaction_id', 'insurance_claims', ['transaction_id'])
        print("✅ Renamed insurance_claims.referenced_transaction_id -> transaction_id")

    # 3d. Rename referenced_dates -> claimed_dates
    if column_exists('insurance_claims', 'referenced_dates') and not column_exists('insurance_claims', 'claimed_dates'):
        op.alter_column('insurance_claims', 'referenced_dates', new_column_name='claimed_dates')
        print("✅ Renamed insurance_claims.referenced_dates -> claimed_dates")

    # 3e. Drop claim_type (resolvable from entitlement_id -> config chain)
    if column_exists('insurance_claims', 'claim_type'):
        op.drop_column('insurance_claims', 'claim_type')
        print("✅ Dropped insurance_claims.claim_type")

    # 3f. Drop claim_basis (not in v3 key fields)
    if column_exists('insurance_claims', 'claim_basis'):
        op.drop_column('insurance_claims', 'claim_basis')
        print("✅ Dropped insurance_claims.claim_basis")

    # 3g. Drop decision_notes (not in v3 key fields)
    if column_exists('insurance_claims', 'decision_notes'):
        op.drop_column('insurance_claims', 'decision_notes')
        print("✅ Dropped insurance_claims.decision_notes")

    # 3h. Add FK from insurance_claims.entitlement_id -> entitlements.entitlement_id
    if not foreign_key_exists('insurance_claims', 'fk_insurance_claims_entitlement_id'):
        op.create_foreign_key(
            'fk_insurance_claims_entitlement_id',
            'insurance_claims', 'entitlements',
            ['entitlement_id'], ['entitlement_id'],
        )
        print("✅ Added FK insurance_claims.entitlement_id -> entitlements.entitlement_id")

    # 3i. Rename index for claim_id
    _rename_index_if_exists(
        'ix_insurance_claims_insurance_claim_id',
        'ix_insurance_claims_claim_id',
        'insurance_claims',
    )

    # -----------------------------------------------------------------------
    # 4. Drop insurance_claim_type_enum (no longer used)
    # -----------------------------------------------------------------------
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS insurance_claim_type_enum"))
    print("✅ Dropped insurance_claim_type_enum")


def _rename_index_if_exists(old_name, new_name, table_name):
    """Rename an index if the old name exists and new name doesn't."""
    if index_exists(table_name, old_name) and not index_exists(table_name, new_name):
        conn = op.get_bind()
        conn.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))
        print(f"✅ Renamed index {old_name} -> {new_name}")


def downgrade():
    conn = op.get_bind()

    # --- Restore insurance_claim_type_enum ---
    conn.execute(sa.text("CREATE TYPE insurance_claim_type_enum AS ENUM ('TRANSACTION', 'PRODUCTIVITY', 'NON_MONETARY')"))

    # --- Reverse insurance_claims changes ---
    # Restore decision_notes
    if not column_exists('insurance_claims', 'decision_notes'):
        op.add_column('insurance_claims', sa.Column('decision_notes', sa.Text(), nullable=True))

    # Restore claim_basis
    if not column_exists('insurance_claims', 'claim_basis'):
        op.add_column('insurance_claims', sa.Column('claim_basis', sa.Text(), nullable=True))

    # Restore claim_type
    if not column_exists('insurance_claims', 'claim_type'):
        op.add_column('insurance_claims', sa.Column(
            'claim_type',
            sa.Enum('TRANSACTION', 'PRODUCTIVITY', 'NON_MONETARY', name='insurance_claim_type_enum'),
            nullable=True,
        ))

    # Rename claim_id -> insurance_claim_id
    if column_exists('insurance_claims', 'claim_id') and not column_exists('insurance_claims', 'insurance_claim_id'):
        op.alter_column('insurance_claims', 'claim_id', new_column_name='insurance_claim_id')

    # Rename claimed_dates -> referenced_dates
    if column_exists('insurance_claims', 'claimed_dates') and not column_exists('insurance_claims', 'referenced_dates'):
        op.alter_column('insurance_claims', 'claimed_dates', new_column_name='referenced_dates')

    # Rename transaction_id -> referenced_transaction_id
    if column_exists('insurance_claims', 'transaction_id') and not column_exists('insurance_claims', 'referenced_transaction_id'):
        if foreign_key_exists('insurance_claims', 'fk_insurance_claims_transaction_id'):
            op.drop_constraint('fk_insurance_claims_transaction_id', 'insurance_claims', type_='foreignkey')
        if index_exists('insurance_claims', 'ix_insurance_claims_transaction_id'):
            op.drop_index('ix_insurance_claims_transaction_id', table_name='insurance_claims')
        op.alter_column('insurance_claims', 'transaction_id', new_column_name='referenced_transaction_id')
        op.create_foreign_key(
            None, 'insurance_claims', 'ledger_transaction',
            ['referenced_transaction_id'], ['id'],
        )
        op.create_index('ix_insurance_claims_referenced_transaction_id', 'insurance_claims', ['referenced_transaction_id'])

    # Drop actor_seat_id from insurance_claims
    if column_exists('insurance_claims', 'actor_seat_id'):
        if foreign_key_exists('insurance_claims', 'fk_insurance_claims_actor_seat_id'):
            op.drop_constraint('fk_insurance_claims_actor_seat_id', 'insurance_claims', type_='foreignkey')
        if index_exists('insurance_claims', 'ix_insurance_claims_actor_seat_id'):
            op.drop_index('ix_insurance_claims_actor_seat_id', table_name='insurance_claims')
        op.drop_column('insurance_claims', 'actor_seat_id')

    # Drop FK from insurance_claims.entitlement_id
    if foreign_key_exists('insurance_claims', 'fk_insurance_claims_entitlement_id'):
        op.drop_constraint('fk_insurance_claims_entitlement_id', 'insurance_claims', type_='foreignkey')

    # Rename index back
    _rename_index_if_exists('ix_insurance_claims_claim_id', 'ix_insurance_claims_insurance_claim_id', 'insurance_claims')

    # --- Reverse entitlement_consumptions changes ---
    # Drop FK
    if foreign_key_exists('entitlement_consumptions', 'fk_entitlement_consumptions_entitlement_id'):
        op.drop_constraint('fk_entitlement_consumptions_entitlement_id', 'entitlement_consumptions', type_='foreignkey')

    # Restore notes
    if not column_exists('entitlement_consumptions', 'notes'):
        op.add_column('entitlement_consumptions', sa.Column('notes', sa.Text(), nullable=True))

    # Drop target_seat_id
    if column_exists('entitlement_consumptions', 'target_seat_id'):
        if foreign_key_exists('entitlement_consumptions', 'fk_entitlement_consumptions_target_seat_id'):
            op.drop_constraint('fk_entitlement_consumptions_target_seat_id', 'entitlement_consumptions', type_='foreignkey')
        if index_exists('entitlement_consumptions', 'ix_entitlement_consumptions_target_seat_id'):
            op.drop_index('ix_entitlement_consumptions_target_seat_id', table_name='entitlement_consumptions')
        op.drop_column('entitlement_consumptions', 'target_seat_id')

    # Rename timestamp -> occurred_at
    if column_exists('entitlement_consumptions', 'timestamp') and not column_exists('entitlement_consumptions', 'occurred_at'):
        op.alter_column('entitlement_consumptions', 'timestamp', new_column_name='occurred_at')

    # Rename consumption_id -> entitlement_consumption_id
    if column_exists('entitlement_consumptions', 'consumption_id') and not column_exists('entitlement_consumptions', 'entitlement_consumption_id'):
        op.alter_column('entitlement_consumptions', 'consumption_id', new_column_name='entitlement_consumption_id')

    # Rename index back
    _rename_index_if_exists('ix_entitlement_consumptions_consumption_id', 'ix_entitlement_consumptions_entitlement_consumption_id', 'entitlement_consumptions')

    # --- Reverse entitlements -> entitlement_grants ---
    if table_exists('entitlements') and not table_exists('entitlement_grants'):
        # Restore purchase_id before rename
        if not column_exists('entitlements', 'purchase_id'):
            op.add_column('entitlements', sa.Column('purchase_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                None, 'entitlements', 'store_purchases',
                ['purchase_id'], ['id'],
                ondelete='SET NULL',
            )
            op.create_index('ix_entitlement_grants_purchase_id', 'entitlements', ['purchase_id'])

        # Rename indexes back
        _rename_index_if_exists('ix_entitlements_entitlement_id', 'ix_entitlement_grants_entitlement_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_entitlement_item_id', 'ix_entitlement_grants_entitlement_item_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_target_seat_id', 'ix_entitlement_grants_target_seat_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_actor_seat_id', 'ix_entitlement_grants_actor_seat_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_class_id', 'ix_entitlement_grants_class_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_correlation_id', 'ix_entitlement_grants_correlation_id', 'entitlements')
        _rename_index_if_exists('ix_entitlements_target_class', 'ix_entitlement_grants_target_class', 'entitlements')
        _rename_index_if_exists('ix_entitlements_item_class', 'ix_entitlement_grants_item_class', 'entitlements')

        op.rename_table('entitlements', 'entitlement_grants')
        print("✅ Renamed entitlements -> entitlement_grants")
