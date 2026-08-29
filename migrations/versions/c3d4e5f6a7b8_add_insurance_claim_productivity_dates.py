"""Add insurance_claim_productivity_dates child table

Normalizes PRODUCTIVITY insurance-claim asserted dates out of the parent claim's
JSON basis and into a first-class child table (DOM-STORE-001 / FEAT-STOR-003
§V.B). ``InsuranceClaim`` stays the product-agnostic case; each asserted
class-local loss-date becomes its own row carrying immutable submitted hours,
adjudicated hours, an optional per-date adjustment note, and the immutable
recognized economic result.

The ``UNIQUE(entitlement_id, claim_date)`` constraint structurally enforces the
settled invariant: within one entitlement a class-local date participates in at
most one PRODUCTIVITY claim lifecycle regardless of SUBMITTED/APPROVED/REJECTED —
rejection does NOT free the date. ``UNIQUE(claim_id, claim_date)`` forbids a date
appearing twice within a single case.

Purely additive. Does not touch the TRANSACTION claim path.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
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


_TABLE = 'insurance_claim_productivity_dates'

# Single-column indexes mirror the ORM ``index=True`` columns.
_INDEXES = [
    ('ix_icpd_claim_id', ['claim_id']),
    ('ix_icpd_entitlement_id', ['entitlement_id']),
    ('ix_icpd_class_id', ['class_id']),
]


def upgrade():
    if not table_exists(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('claim_id', sa.String(length=36), nullable=False),
            sa.Column('entitlement_id', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('claim_date', sa.Date(), nullable=False),
            sa.Column('student_claimed_hours', sa.Numeric(precision=6, scale=2), nullable=False),
            sa.Column('teacher_approved_hours', sa.Numeric(precision=6, scale=2), nullable=True),
            sa.Column('adjustment_note', sa.Text(), nullable=True),
            sa.Column('recognized_payout', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.ForeignKeyConstraint(['claim_id'], ['insurance_claims.claim_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('entitlement_id', 'claim_date', name='uq_icpd_entitlement_date'),
            sa.UniqueConstraint('claim_id', 'claim_date', name='uq_icpd_claim_date'),
        )
        print(f"✅ Created table {_TABLE}")
    else:
        print(f"⚠️  Table '{_TABLE}' already exists, skipping...")

    for name, cols in _INDEXES:
        if not index_exists(_TABLE, name):
            op.create_index(name, _TABLE, cols, unique=False)
            print(f"✅ Created index {name}")
        else:
            print(f"⚠️  Index '{name}' already exists, skipping...")


def downgrade():
    for name, _cols in _INDEXES:
        if index_exists(_TABLE, name):
            op.drop_index(name, table_name=_TABLE)
            print(f"❌ Dropped index {name}")
        else:
            print(f"⚠️  Index '{name}' does not exist, skipping...")

    if table_exists(_TABLE):
        op.drop_table(_TABLE)
        print(f"❌ Dropped table {_TABLE}")
    else:
        print(f"⚠️  Table '{_TABLE}' does not exist, skipping...")
