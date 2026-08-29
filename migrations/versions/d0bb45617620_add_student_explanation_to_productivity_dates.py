"""Add required student_explanation to insurance_claim_productivity_dates

PRODUCTIVITY claim submission is now a multi-date evidentiary form: each asserted
loss-date carries a required, student-authored ``student_explanation`` (the
student's own account of the loss). This is evidence, never derived and never
fabricated.

The column is added ``NOT NULL`` with no server default. A pre-migration
inventory confirmed zero existing ``insurance_claim_productivity_dates`` rows, so
there is nothing to backfill and no historical evidence is manufactured. If any
row unexpectedly existed, this migration fails loudly rather than inventing an
explanation — which is the intended, safe behavior.

The optional claim-wide ``additional_information`` is stored in
``InsuranceClaim.claim_basis`` (JSON), so it needs no schema change.

Purely additive to the PRODUCTIVITY child table. Does not touch the TRANSACTION
claim path.

Revision ID: d0bb45617620
Revises: c3d4e5f6a7b8
Create Date: 2026-08-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0bb45617620'
down_revision = 'c3d4e5f6a7b8'
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


_TABLE = 'insurance_claim_productivity_dates'
_COLUMN = 'student_explanation'


def upgrade():
    if not table_exists(_TABLE):
        print(f"⚠️  Table '{_TABLE}' does not exist, skipping column add...")
        return

    if not column_exists(_TABLE, _COLUMN):
        # NOT NULL with no default is intentional: inventory confirmed zero rows,
        # so there is nothing to backfill and no evidence to fabricate.
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Text(), nullable=False))
        print(f"✅ Added column {_TABLE}.{_COLUMN}")
    else:
        print(f"⚠️  Column '{_COLUMN}' already exists on '{_TABLE}', skipping...")


def downgrade():
    if column_exists(_TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
        print(f"❌ Dropped column {_TABLE}.{_COLUMN}")
    else:
        print(f"⚠️  Column '{_COLUMN}' does not exist on '{_TABLE}', skipping...")
