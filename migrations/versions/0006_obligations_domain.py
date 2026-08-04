"""Wave 7 — Canonical Obligations Domain (DOM-OBL-001)

Creates obligation_assessment, obligation_satisfaction, obligation_reversal,
insurance_enrollments, and entitlement_events tables. Old rent/insurance tables
are retained for backward-compatible reads during the transition period; they
will be dropped in the follow-up Wave 7-B migration once all reads are migrated.

Revision ID: 0006
Revises: 4b1e8f2c6d90
Create Date: 2026-06-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "4b1e8f2c6d90"
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


def constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

def upgrade():
    # 1. obligation_assessment — authoritative debt fact record
    if not table_exists('obligation_assessment'):
        op.create_table(
            'obligation_assessment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('seat_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(36), nullable=False),
            sa.Column('join_code', sa.String(20), nullable=True),
            sa.Column('period', sa.String(10), nullable=True),
            sa.Column('obligation_type', sa.String(30), nullable=False),
            sa.Column('amount_snap', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
            # Rent-cycle coverage-window fields
            sa.Column('period_key', sa.String(20), nullable=True),
            sa.Column('coverage_start_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('coverage_end_time', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cycle_idempotency_key', sa.String(160), nullable=True),
            sa.Column('period_month', sa.Integer(), nullable=True),
            sa.Column('period_year', sa.Integer(), nullable=True),
            sa.Column('coverage_month', sa.Integer(), nullable=True),
            sa.Column('coverage_year', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('seat_id', 'class_id', 'cycle_idempotency_key', name='uq_obligation_assessment_idempotency'),
        )
        print("✅ Created obligation_assessment")
    else:
        print("⚠️  Table 'obligation_assessment' already exists, skipping create...")

    # Indexes for obligation_assessment (guarded independently for partial-run recovery)
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_seat_id'):
        op.create_index('ix_obligation_assessment_seat_id', 'obligation_assessment', ['seat_id'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_class_id'):
        op.create_index('ix_obligation_assessment_class_id', 'obligation_assessment', ['class_id'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_join_code'):
        op.create_index('ix_obligation_assessment_join_code', 'obligation_assessment', ['join_code'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_period'):
        op.create_index('ix_obligation_assessment_period', 'obligation_assessment', ['period'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_obligation_type'):
        op.create_index('ix_obligation_assessment_obligation_type', 'obligation_assessment', ['obligation_type'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_coverage_start_time'):
        op.create_index('ix_obligation_assessment_coverage_start_time', 'obligation_assessment', ['coverage_start_time'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_coverage_end_time'):
        op.create_index('ix_obligation_assessment_coverage_end_time', 'obligation_assessment', ['coverage_end_time'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_cycle_idempotency_key'):
        op.create_index('ix_obligation_assessment_cycle_idempotency_key', 'obligation_assessment', ['cycle_idempotency_key'])
    if not index_exists('obligation_assessment', 'ix_obligation_assessment_seat_class'):
        op.create_index('ix_obligation_assessment_seat_class', 'obligation_assessment', ['seat_id', 'class_id'])

    # 2. obligation_satisfaction — DEPRECATED (will be collapsed into assessment_events via migration 0008)
    # Skipped: will be handled by migration 0008 which uses event_type discriminator
    print("⏭️  obligation_satisfaction table skipped (will be created/managed by migration 0008)")

    # 3. obligation_reversal — DEPRECATED (will be collapsed into assessment_events via migration 0008)
    # Skipped: will be handled by migration 0008 which uses event_type discriminator
    print("⏭️  obligation_reversal table skipped (will be created/managed by migration 0008)")

    # 4. insurance_enrollments was removed in the v2 cutover.
    # The historical table is intentionally not recreated in the baseline.

    # 5. entitlement_events — append-only perk grant/consumption stream
    if not table_exists('entitlement_events'):
        op.create_table(
            'entitlement_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('seat_id', sa.Integer(), nullable=False),
            sa.Column('class_id', sa.String(36), nullable=False),
            sa.Column('assessment_id', sa.Integer(), nullable=True),
            sa.Column('trigger_id', sa.String(200), nullable=True),
            sa.Column('quantity_delta', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(20), nullable=False),
            sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assessment_id'], ['obligation_assessment.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        print("✅ Created entitlement_events")
    else:
        print("⚠️  Table 'entitlement_events' already exists, skipping create...")

    # Index creation guarded by column existence (handles both legacy and canonical schemas)
    if not index_exists('entitlement_events', 'ix_entitlement_events_seat_id') and column_exists('entitlement_events', 'seat_id'):
        op.create_index('ix_entitlement_events_seat_id', 'entitlement_events', ['seat_id'])
    if not index_exists('entitlement_events', 'ix_entitlement_events_class_id') and column_exists('entitlement_events', 'class_id'):
        op.create_index('ix_entitlement_events_class_id', 'entitlement_events', ['class_id'])
    if not index_exists('entitlement_events', 'ix_entitlement_events_assessment_id') and column_exists('entitlement_events', 'assessment_id'):
        op.create_index('ix_entitlement_events_assessment_id', 'entitlement_events', ['assessment_id'])
    if not index_exists('entitlement_events', 'ix_entitlement_events_trigger_id') and column_exists('entitlement_events', 'trigger_id'):
        op.create_index('ix_entitlement_events_trigger_id', 'entitlement_events', ['trigger_id'])
    if not index_exists('entitlement_events', 'ix_entitlement_events_seat_class') and column_exists('entitlement_events', 'seat_id') and column_exists('entitlement_events', 'class_id'):
        op.create_index('ix_entitlement_events_seat_class', 'entitlement_events', ['seat_id', 'class_id'])


def downgrade():
    for table in [
        'entitlement_events',
        'obligation_assessment',
    ]:
        if table_exists(table):
            op.drop_table(table)
            print(f"❌ Dropped {table}")
        else:
            print(f"⚠️  Table '{table}' does not exist, skipping...")
