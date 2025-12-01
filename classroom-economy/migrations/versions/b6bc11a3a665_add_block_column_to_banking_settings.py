"""Add block column to banking settings

Revision ID: b6bc11a3a665
Revises: 8e73fb5ef27e
Create Date: 2025-11-29 02:13:53.521288

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6bc11a3a665'
down_revision = '8e73fb5ef27e'
branch_labels = None
depends_on = None


def _get_columns(table_name: str):
    """Return column names for the given table."""
    from sqlalchemy.exc import NoSuchTableError
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    try:
        return [col['name'] for col in inspector.get_columns(table_name)]
    except NoSuchTableError:
        return []
def upgrade():
    columns = _get_columns('banking_settings')
    if 'block' not in columns:
        op.add_column('banking_settings', sa.Column('block', sa.String(length=10), nullable=True))


def downgrade():
    columns = _get_columns('banking_settings')
    if 'block' in columns:
        op.drop_column('banking_settings', 'block')
