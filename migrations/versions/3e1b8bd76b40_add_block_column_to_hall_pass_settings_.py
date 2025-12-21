"""Add block column to hall_pass_settings for multi-tenancy

Revision ID: 3e1b8bd76b40
Revises: 1ef03001fb2a
Create Date: 2025-11-30 21:34:13.076241
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3e1b8bd76b40'
down_revision = '1ef03001fb2a'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('block', sa.String(length=10), nullable=True))

def downgrade():
    with op.batch_alter_table('hall_pass_settings', schema=None) as batch_op:
        batch_op.drop_column('block')