"""Remove join_code from Seat — owned by ClassEconomy per DOM-IDEN-007

Revision ID: 1c6893a8b375
Revises: 0b1c2d3e4f5a
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa


revision = '1c6893a8b375'
down_revision = '0b1c2d3e4f5a'
branch_labels = None
depends_on = None


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


def upgrade():
    if index_exists('seats', 'ix_seats_join_code'):
        op.drop_index('ix_seats_join_code', table_name='seats')
        print("✅ Dropped index ix_seats_join_code")
    else:
        print("⚠️  Index ix_seats_join_code does not exist, skipping...")

    if column_exists('seats', 'join_code'):
        with op.batch_alter_table('seats', schema=None) as batch_op:
            batch_op.drop_column('join_code')
        print("✅ Dropped seats.join_code — join_code is owned by ClassEconomy per DOM-IDEN-007")
    else:
        print("⚠️  Column seats.join_code does not exist, skipping...")


def downgrade():
    if not column_exists('seats', 'join_code'):
        with op.batch_alter_table('seats', schema=None) as batch_op:
            batch_op.add_column(sa.Column('join_code', sa.String(20), nullable=True))
        print("❌ Restored seats.join_code (nullable) for downgrade")
    else:
        print("⚠️  Column seats.join_code already exists, skipping...")

    if not index_exists('seats', 'ix_seats_join_code'):
        op.create_index('ix_seats_join_code', 'seats', ['join_code'])
        print("❌ Restored index ix_seats_join_code")
    else:
        print("⚠️  Index ix_seats_join_code already exists, skipping...")
