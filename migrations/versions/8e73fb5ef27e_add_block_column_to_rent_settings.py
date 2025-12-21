"""Add block column to rent settings

Revision ID: 8e73fb5ef27e
Revises: d1e2f3a4b5c6
Create Date: 2025-11-29 00:16:43.449204

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e73fb5ef27e'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('rent_settings')]
    if 'block' not in columns:
        op.add_column('rent_settings', sa.Column('block', sa.String(length=10), nullable=True))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('rent_settings')]
    if 'block' in columns:
        op.drop_column('rent_settings', 'block')
