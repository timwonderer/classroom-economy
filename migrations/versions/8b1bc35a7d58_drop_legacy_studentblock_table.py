"""Drop legacy StudentBlock table

Revision ID: 8b1bc35a7d58
Revises: cb55646cb43e
Create Date: 2026-06-30 04:06:12.167975

"""
from alembic import op
import sqlalchemy as sa


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
revision = '8b1bc35a7d58'
down_revision = 'cb55646cb43e'
branch_labels = None
depends_on = None


def upgrade():
    if index_exists('student_blocks', 'ix_student_blocks_class_id'):
        op.drop_index(op.f('ix_student_blocks_class_id'), table_name='student_blocks')
    if index_exists('student_blocks', 'ix_student_blocks_join_code'):
        op.drop_index(op.f('ix_student_blocks_join_code'), table_name='student_blocks')
    if index_exists('student_blocks', 'ix_student_blocks_period'):
        op.drop_index(op.f('ix_student_blocks_period'), table_name='student_blocks')
    if index_exists('student_blocks', 'ix_student_blocks_seat_id'):
        op.drop_index(op.f('ix_student_blocks_seat_id'), table_name='student_blocks')
    if table_exists('student_blocks'):
        op.drop_table('student_blocks')


def downgrade():
    if not table_exists('student_blocks'):
        op.create_table('student_blocks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('seat_id', sa.Integer(), nullable=False),
            sa.Column('period', sa.String(length=10), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=True),
            sa.Column('join_code', sa.String(length=20), nullable=True),
            sa.Column('tap_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('done_for_day_date', sa.Date(), nullable=True),
            sa.Column('rent_hall_passes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], name=op.f('student_blocks_class_id_fkey'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], name=op.f('student_blocks_seat_id_fkey'), ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id', name=op.f('student_blocks_pkey')),
            sa.UniqueConstraint('seat_id', 'period', name=op.f('uq_student_blocks_seat_period'))
        )
        op.create_index(op.f('ix_student_blocks_class_id'), 'student_blocks', ['class_id'], unique=False)
        op.create_index(op.f('ix_student_blocks_join_code'), 'student_blocks', ['join_code'], unique=False)
        op.create_index(op.f('ix_student_blocks_period'), 'student_blocks', ['period'], unique=False)
        op.create_index(op.f('ix_student_blocks_seat_id'), 'student_blocks', ['seat_id'], unique=False)
