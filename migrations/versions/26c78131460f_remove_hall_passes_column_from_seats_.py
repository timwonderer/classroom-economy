"""Remove hall_passes column from seats (derived from EntitlementEvent)

Revision ID: 26c78131460f
Revises: 677a7c3b06e0
Create Date: 2026-07-09 16:33:28.162725

Hall pass balance is now derived from EntitlementEvent.quantity_delta sum
for (seat_id, class_id). The cached counter on seats is removed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26c78131460f'
down_revision = '677a7c3b06e0'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def upgrade():
    if column_exists('seats', 'hall_passes'):
        op.drop_column('seats', 'hall_passes')


def downgrade():
    if not column_exists('seats', 'hall_passes'):
        op.add_column(
            'seats',
            sa.Column('hall_passes', sa.Integer(), nullable=False, server_default='3'),
        )
