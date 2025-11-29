"""Add block column to hall pass settings

Revision ID: 146f76e63c09
Revises: b6bc11a3a665
Create Date: 2025-11-29 04:32:53.164445

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import NoSuchTableError


# revision identifiers, used by Alembic.
revision = '146f76e63c09'
down_revision = 'b6bc11a3a665'
branch_labels = None
depends_on = None


def _get_columns(table_name: str):
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    try:
        return [col['name'] for col in inspector.get_columns(table_name)]
    except NoSuchTableError:
        return []


def upgrade():
    columns = _get_columns('hall_pass_settings')
    if 'block' not in columns:
        op.add_column('hall_pass_settings', sa.Column('block', sa.String(length=10), nullable=True))


def downgrade():
    columns = _get_columns('hall_pass_settings')
    if 'block' in columns:
        op.drop_column('hall_pass_settings', 'block')
