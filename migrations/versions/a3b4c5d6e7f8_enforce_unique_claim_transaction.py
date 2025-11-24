"""Enforce unique claim per transaction

Revision ID: a3b4c5d6e7f8
Revises: 2f3g4h5i6j7k
Create Date: 2025-12-15 00:00:00.000000

"""

revision = 'a3b4c5d6e7f8'
down_revision = '2f3g4h5i6j7k'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint(
        'uq_insurance_claims_transaction_id',
        'insurance_claims',
        ['transaction_id'],
    )


def downgrade():
    op.drop_constraint('uq_insurance_claims_transaction_id', 'insurance_claims', type_='unique')
