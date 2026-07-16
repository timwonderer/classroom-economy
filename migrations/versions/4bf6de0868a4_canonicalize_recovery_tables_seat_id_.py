"""Canonicalize recovery tables: seat_id, class_id, drop legacy columns

Revision ID: 4bf6de0868a4
Revises: d4c3b2a19087
Create Date: 2026-07-16 04:34:20.868259

"""
from alembic import op
import sqlalchemy as sa

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

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
    """Get FKs for a column (for downgrade without hardcoded names)."""
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
# MIGRATION
# ============================================================================

revision = '4bf6de0868a4'
down_revision = 'd4c3b2a19087'
branch_labels = None
depends_on = None


def upgrade():
    # ---- recovery_requests: drop legacy columns ----
    if index_exists('recovery_requests', 'ix_recovery_requests_join_code'):
        op.drop_index('ix_recovery_requests_join_code', table_name='recovery_requests')
        print("✅ Dropped index ix_recovery_requests_join_code")

    if column_exists('recovery_requests', 'dob_sum_hash'):
        op.drop_column('recovery_requests', 'dob_sum_hash')
        print("✅ Dropped recovery_requests.dob_sum_hash")

    if column_exists('recovery_requests', 'join_code'):
        op.drop_column('recovery_requests', 'join_code')
        print("✅ Dropped recovery_requests.join_code")

    # ---- student_recovery_codes: add canonical columns ----
    if not column_exists('student_recovery_codes', 'seat_id'):
        op.add_column('student_recovery_codes', sa.Column('seat_id', sa.Integer(), nullable=True))
        print("✅ Added student_recovery_codes.seat_id")

    if not column_exists('student_recovery_codes', 'class_id'):
        op.add_column('student_recovery_codes', sa.Column('class_id', sa.String(length=36), nullable=True))
        print("✅ Added student_recovery_codes.class_id")

    # ---- student_recovery_codes: drop legacy FK and columns ----
    for fk in get_foreign_keys_by_column('student_recovery_codes', 'user_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'student_recovery_codes', type_='foreignkey')
            print(f"✅ Dropped FK {fk['name']} on student_recovery_codes")

    if index_exists('student_recovery_codes', 'ix_student_recovery_codes_join_code'):
        op.drop_index('ix_student_recovery_codes_join_code', table_name='student_recovery_codes')
        print("✅ Dropped index ix_student_recovery_codes_join_code")

    if column_exists('student_recovery_codes', 'user_id'):
        op.drop_column('student_recovery_codes', 'user_id')
        print("✅ Dropped student_recovery_codes.user_id")

    if column_exists('student_recovery_codes', 'join_code'):
        op.drop_column('student_recovery_codes', 'join_code')
        print("✅ Dropped student_recovery_codes.join_code")

    # ---- student_recovery_codes: add canonical FKs and indexes ----
    if not index_exists('student_recovery_codes', 'ix_student_recovery_codes_seat_id'):
        op.create_index('ix_student_recovery_codes_seat_id', 'student_recovery_codes', ['seat_id'], unique=False)
        print("✅ Created index ix_student_recovery_codes_seat_id")

    if not index_exists('student_recovery_codes', 'ix_student_recovery_codes_class_id'):
        op.create_index('ix_student_recovery_codes_class_id', 'student_recovery_codes', ['class_id'], unique=False)
        print("✅ Created index ix_student_recovery_codes_class_id")

    if not foreign_key_exists('student_recovery_codes', 'fk_student_recovery_codes_seat_id_seats'):
        op.create_foreign_key(
            'fk_student_recovery_codes_seat_id_seats',
            'student_recovery_codes', 'seats',
            ['seat_id'], ['id'],
        )
        print("✅ Created FK fk_student_recovery_codes_seat_id_seats")

    if not foreign_key_exists('student_recovery_codes', 'fk_student_recovery_codes_class_id_classes'):
        op.create_foreign_key(
            'fk_student_recovery_codes_class_id_classes',
            'student_recovery_codes', 'classes',
            ['class_id'], ['class_id'],
            ondelete='CASCADE',
        )
        print("✅ Created FK fk_student_recovery_codes_class_id_classes")

    # ---- Make seat_id and class_id NOT NULL (table is empty, safe) ----
    op.alter_column('student_recovery_codes', 'seat_id', nullable=False)
    op.alter_column('student_recovery_codes', 'class_id', nullable=False)
    print("✅ Set seat_id and class_id to NOT NULL")


def downgrade():
    # ---- student_recovery_codes: restore legacy columns ----
    if not column_exists('student_recovery_codes', 'user_id'):
        op.add_column('student_recovery_codes', sa.Column('user_id', sa.INTEGER(), nullable=True))

    if not column_exists('student_recovery_codes', 'join_code'):
        op.add_column('student_recovery_codes', sa.Column('join_code', sa.VARCHAR(length=20), nullable=True))

    # Drop canonical FKs
    for fk in get_foreign_keys_by_column('student_recovery_codes', 'seat_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'student_recovery_codes', type_='foreignkey')

    for fk in get_foreign_keys_by_column('student_recovery_codes', 'class_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'student_recovery_codes', type_='foreignkey')

    # Drop canonical indexes
    if index_exists('student_recovery_codes', 'ix_student_recovery_codes_seat_id'):
        op.drop_index('ix_student_recovery_codes_seat_id', table_name='student_recovery_codes')

    if index_exists('student_recovery_codes', 'ix_student_recovery_codes_class_id'):
        op.drop_index('ix_student_recovery_codes_class_id', table_name='student_recovery_codes')

    # Drop canonical columns
    if column_exists('student_recovery_codes', 'seat_id'):
        op.drop_column('student_recovery_codes', 'seat_id')

    if column_exists('student_recovery_codes', 'class_id'):
        op.drop_column('student_recovery_codes', 'class_id')

    # Restore legacy FK
    if not foreign_key_exists('student_recovery_codes', 'fk_student_recovery_codes_user_id_users'):
        op.create_foreign_key(
            'fk_student_recovery_codes_user_id_users',
            'student_recovery_codes', 'users',
            ['user_id'], ['id'],
        )

    # Restore legacy index
    if not index_exists('student_recovery_codes', 'ix_student_recovery_codes_join_code'):
        op.create_index('ix_student_recovery_codes_join_code', 'student_recovery_codes', ['join_code'], unique=False)

    # ---- recovery_requests: restore legacy columns ----
    if not column_exists('recovery_requests', 'join_code'):
        op.add_column('recovery_requests', sa.Column('join_code', sa.VARCHAR(length=20), nullable=True))

    if not column_exists('recovery_requests', 'dob_sum_hash'):
        op.add_column('recovery_requests', sa.Column('dob_sum_hash', sa.VARCHAR(length=64), nullable=True))

    if not index_exists('recovery_requests', 'ix_recovery_requests_join_code'):
        op.create_index('ix_recovery_requests_join_code', 'recovery_requests', ['join_code'], unique=False)
