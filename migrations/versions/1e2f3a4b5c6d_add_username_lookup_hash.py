"""Add deterministic username lookup hash

Revision ID: 1e2f3a4b5c6d
Revises: m2n3o4p5q6r7
Create Date: 2025-12-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1e2f3a4b5c6d'
down_revision = 'm2n3o4p5q6r7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username_lookup_hash', sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint('uq_students_username_lookup_hash', ['username_lookup_hash'])


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_constraint('uq_students_username_lookup_hash', type_='unique')
        batch_op.drop_column('username_lookup_hash')
