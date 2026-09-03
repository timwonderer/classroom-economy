"""Add partial unique index for insurance tier-group rank (max 3 active tiers/group)

Backstops the FEAT-CLASS-003 tier-group guard: at most one IN_USE insurance policy
per (class_id, tier_group, tier_level), so a group holds at most three active tiers
(basic/mid/premium). Immutable RETIRED/HIDDEN versions are excluded from the index,
so editing a tier (mint a new IN_USE row + retire the old) never trips it.

Revision ID: c4d5e6f7a8b9
Revises: 1ed7b3643792
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

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

def get_foreign_keys_by_column(table_name, column_name):
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
revision = 'c4d5e6f7a8b9'
down_revision = '1ed7b3643792'
branch_labels = None
depends_on = None

_INDEX = 'uq_insurance_policies_group_rank_in_use'


def upgrade():
    if table_exists('insurance_policies') and not index_exists('insurance_policies', _INDEX):
        op.create_index(
            _INDEX,
            'insurance_policies',
            ['class_id', 'tier_group', 'tier_level'],
            unique=True,
            postgresql_where=sa.text(
                "availability_state = 'IN_USE' AND tier_group IS NOT NULL"
            ),
        )
        print(f"✅ Created partial unique index {_INDEX}")
    else:
        print(f"⚠️  Index {_INDEX} already exists (or table missing), skipping")


def downgrade():
    if table_exists('insurance_policies') and index_exists('insurance_policies', _INDEX):
        op.drop_index(_INDEX, table_name='insurance_policies')
        print(f"❌ Dropped index {_INDEX}")
    else:
        print(f"⚠️  Index {_INDEX} does not exist, skipping")
