"""add tier level to insurance policies

Revision ID: cf7a5cda2d0a
Revises: 6323c80bab8e
Create Date: 2025-12-15 07:53:36.062834

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf7a5cda2d0a'

down_revision = '6323c80bab8e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('insurance_policies') as batch_op:
        batch_op.add_column(sa.Column('tier_level', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('insurance_policies') as batch_op:
        batch_op.drop_column('tier_level')
