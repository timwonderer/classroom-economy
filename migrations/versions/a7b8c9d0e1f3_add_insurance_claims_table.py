"""Add insurance_claims table (first-class insurance claim lifecycle)

Introduces the canonical ``insurance_claims`` table backing the product-agnostic
insurance-claim lifecycle (DOM-STORE-001 / FEAT-STOR-003):

    SUBMITTED -> APPROVED | REJECTED

A claim is correlated to an insurance entitlement lineage (via the stable
class-scoped ``entitlement_id`` string) but is NEVER represented by an
``EntitlementEvent`` — entitlements are event-sourced with no addressable
canonical row, so ``entitlement_id`` is a soft correlation column validated
through the owning domain, not a hard FK. Downstream lineage references
(``payroll_event_id`` / ``ledger_transaction_id``) are nullable until an APPROVED
decision materializes them.

This migration is purely additive. It does not touch the existing TRANSACTION
claim path (pending_actions + terminal CONSUMED events), which is migrated
separately in a later step.

Revision ID: a7b8c9d0e1f3
Revises: d4e5f6a7b8c9
Create Date: 2026-08-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f3'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


# Single-column indexes mirror the ORM ``index=True`` / ``unique=True`` columns
# so `flask db migrate` detects no drift after this lands.
_SINGLE_COLUMN_INDEXES = [
    ('ix_insurance_claims_class_id', ['class_id'], False),
    ('ix_insurance_claims_entitlement_id', ['entitlement_id'], False),
    ('ix_insurance_claims_target_seat_id', ['target_seat_id'], False),
    ('ix_insurance_claims_status', ['status'], False),
    ('ix_insurance_claims_correlation_id', ['correlation_id'], True),
]

# Composite indexes mirror ``InsuranceClaim.__table_args__``.
_COMPOSITE_INDEXES = [
    ('ix_insurance_claims_entitlement_class', ['entitlement_id', 'class_id'], False),
    ('ix_insurance_claims_seat_class', ['target_seat_id', 'class_id'], False),
    ('ix_insurance_claims_status_class', ['status', 'class_id'], False),
]


def upgrade():
    if not table_exists('insurance_claims'):
        op.create_table(
            'insurance_claims',
            sa.Column('claim_id', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('entitlement_id', sa.String(length=36), nullable=False),
            sa.Column('target_seat_id', sa.Integer(), nullable=False),
            sa.Column('actor_seat_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('correlation_id', sa.String(length=200), nullable=False),
            sa.Column('claim_basis', sa.JSON(), nullable=False),
            sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('decided_by_seat_id', sa.Integer(), nullable=True),
            sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('decision_note', sa.Text(), nullable=True),
            sa.Column('result_amount', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('payroll_event_id', sa.Integer(), nullable=True),
            sa.Column('ledger_transaction_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['target_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['actor_seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['decided_by_seat_id'], ['seats.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('claim_id'),
        )
        print("✅ Created table insurance_claims")
    else:
        print("⚠️  Table 'insurance_claims' already exists, skipping...")

    for name, cols, unique in _SINGLE_COLUMN_INDEXES + _COMPOSITE_INDEXES:
        if not index_exists('insurance_claims', name):
            op.create_index(name, 'insurance_claims', cols, unique=unique)
            print(f"✅ Created index {name}")
        else:
            print(f"⚠️  Index '{name}' already exists, skipping...")


def downgrade():
    for name, _cols, _unique in _SINGLE_COLUMN_INDEXES + _COMPOSITE_INDEXES:
        if index_exists('insurance_claims', name):
            op.drop_index(name, table_name='insurance_claims')
            print(f"❌ Dropped index {name}")
        else:
            print(f"⚠️  Index '{name}' does not exist, skipping...")

    if table_exists('insurance_claims'):
        op.drop_table('insurance_claims')
        print("❌ Dropped table insurance_claims")
    else:
        print("⚠️  Table 'insurance_claims' does not exist, skipping...")
