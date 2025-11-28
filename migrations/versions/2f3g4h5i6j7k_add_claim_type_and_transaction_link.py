"""Add claim type and transaction link to insurance models

Revision ID: 2f3g4h5i6j7k
Revises: 1e2f3a4b5c6d
Create Date: 2025-12-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f3g4h5i6j7k'
down_revision = '1e2f3a4b5c6d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'insurance_policies',
        sa.Column('claim_type', sa.String(length=20), nullable=False, server_default='legacy_monetary')
    )
    op.add_column(
        'insurance_claims',
        sa.Column('transaction_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(None, 'insurance_claims', 'transaction', ['transaction_id'], ['id'])

    insurance_policies = sa.sql.table(
        'insurance_policies',
        sa.Column('id', sa.Integer()),
        sa.Column('is_monetary', sa.Boolean()),
        sa.Column('claim_type', sa.String(length=20)),
    )

    op.execute(
        insurance_policies.update()
        .where(insurance_policies.c.is_monetary == False)
        .values(claim_type='non_monetary')
    )
    op.execute(
        insurance_policies.update()
        .where(insurance_policies.c.is_monetary != False)
        .values(claim_type='legacy_monetary')
    )

    op.alter_column('insurance_policies', 'claim_type', server_default=None)


def downgrade():
    op.drop_constraint(None, 'insurance_claims', type_='foreignkey')
    op.drop_column('insurance_claims', 'transaction_id')
    op.drop_column('insurance_policies', 'claim_type')
