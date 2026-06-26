"""Drop Student first_name/last_initial, add class_id to identity_profiles, make seat_id NOT NULL

Revision ID: a2b3c4d5e6f7
Revises: 1cbe502574ec
Create Date: 2026-06-20 01:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = '1cbe502574ec'
branch_labels = None
depends_on = None


# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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
# UPGRADE
# ============================================================================

def upgrade():
    # 1. Drop legacy Student name columns
    if column_exists('students', 'first_name'):
        op.drop_column('students', 'first_name')
        print("✅ Dropped first_name from students")
    else:
        print("⚠️  Column 'first_name' does not exist on 'students', skipping...")

    if column_exists('students', 'last_initial'):
        op.drop_column('students', 'last_initial')
        print("✅ Dropped last_initial from students")
    else:
        print("⚠️  Column 'last_initial' does not exist on 'students', skipping...")

    # 2. Add class_id to identity_profiles
    if not column_exists('identity_profiles', 'class_id'):
        op.add_column('identity_profiles', sa.Column('class_id', sa.String(36), nullable=False))
        print("✅ Added class_id to identity_profiles")
    else:
        print("⚠️  Column 'class_id' already exists on 'identity_profiles', skipping...")

    if not index_exists('identity_profiles', 'ix_identity_profiles_class_id'):
        op.create_index('ix_identity_profiles_class_id', 'identity_profiles', ['class_id'])
        print("✅ Created index ix_identity_profiles_class_id")

    if not foreign_key_exists('identity_profiles', 'fk_identity_profiles_class_id'):
        op.create_foreign_key(
            'fk_identity_profiles_class_id',
            'identity_profiles',
            'classes',
            ['class_id'],
            ['class_id'],
            ondelete='CASCADE',
        )
        print("✅ Created FK fk_identity_profiles_class_id")

    # 3. Make seat_id NOT NULL on identity_profiles
    op.alter_column('identity_profiles', 'seat_id', nullable=False)
    print("✅ Made seat_id NOT NULL on identity_profiles")


# ============================================================================
# DOWNGRADE
# ============================================================================

def downgrade():
    # 1. Make seat_id nullable again
    op.alter_column('identity_profiles', 'seat_id', nullable=True)
    print("✅ Made seat_id nullable on identity_profiles")

    # 2. Drop class_id from identity_profiles
    for fk in get_foreign_keys_by_column('identity_profiles', 'class_id'):
        op.drop_constraint(fk['name'], 'identity_profiles', type_='foreignkey')
        print(f"✅ Dropped FK {fk['name']} from identity_profiles")

    if index_exists('identity_profiles', 'ix_identity_profiles_class_id'):
        op.drop_index('ix_identity_profiles_class_id', 'identity_profiles')
        print("✅ Dropped index ix_identity_profiles_class_id")

    if column_exists('identity_profiles', 'class_id'):
        op.drop_column('identity_profiles', 'class_id')
        print("✅ Dropped class_id from identity_profiles")

    # 3. Re-add legacy Student columns
    if not column_exists('students', 'last_initial'):
        op.add_column('students', sa.Column('last_initial', sa.String(1), nullable=True))
        print("✅ Re-added last_initial to students")

    if not column_exists('students', 'first_name'):
        op.add_column('students', sa.Column('first_name', sa.LargeBinary(), nullable=True))
        print("✅ Re-added first_name to students")
