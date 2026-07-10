"""Add hall_pass_verify_token to users

Revision ID: 572a1b9a2d74
Revises: 26c78131460f
Create Date: 2026-07-09 16:50:20.539013

hall_pass_verify_token moves from Admin (legacy teachers table) to the
canonical User model so the verification route can query User directly.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '572a1b9a2d74'
down_revision = '26c78131460f'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx['name'] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def upgrade():
    if not column_exists('users', 'hall_pass_verify_token'):
        op.add_column('users', sa.Column('hall_pass_verify_token', sa.String(length=64), nullable=True))
    if not index_exists('users', 'ix_users_hall_pass_verify_token'):
        op.create_index(
            op.f('ix_users_hall_pass_verify_token'),
            'users',
            ['hall_pass_verify_token'],
            unique=True,
        )


def downgrade():
    if index_exists('users', 'ix_users_hall_pass_verify_token'):
        op.drop_index(op.f('ix_users_hall_pass_verify_token'), table_name='users')
    if column_exists('users', 'hall_pass_verify_token'):
        op.drop_column('users', 'hall_pass_verify_token')
