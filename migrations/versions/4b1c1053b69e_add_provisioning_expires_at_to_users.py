"""Add provisioning_expires_at to users table

Revision ID: 4b1c1053b69e
Revises: f1a2b3c4d5e6
Create Date: 2026-08-13 04:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '4b1c1053b69e'
down_revision = 'f1a2b3c4d5e6'
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
    if not column_exists('users', 'provisioning_expires_at'):
        op.add_column('users', sa.Column(
            'provisioning_expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ))
        print("✅ Added provisioning_expires_at column to users")
    else:
        print("⚠️  Column provisioning_expires_at already exists on users, skipping")

    if not index_exists('users', 'ix_users_provisioning_expires_at'):
        op.create_index(
            'ix_users_provisioning_expires_at',
            'users',
            ['provisioning_expires_at'],
            unique=False,
        )
        print("✅ Created index ix_users_provisioning_expires_at")


def downgrade():
    if index_exists('users', 'ix_users_provisioning_expires_at'):
        op.drop_index('ix_users_provisioning_expires_at', table_name='users')

    if column_exists('users', 'provisioning_expires_at'):
        op.drop_column('users', 'provisioning_expires_at')
