"""Add interest calculation type and compound frequency to BankingSettings

Revision ID: n1o2p3q4r5s6
Revises: m0n1o2p3q4r5
Create Date: 2025-11-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n1o2p3q4r5s6'
down_revision = 'm0n1o2p3q4r5'
branch_labels = None
depends_on = None


def upgrade():
    # Add interest calculation type and compound frequency columns
    op.add_column('banking_settings',
        sa.Column('interest_calculation_type', sa.String(20), nullable=True, server_default='simple')
    )
    op.add_column('banking_settings',
        sa.Column('compound_frequency', sa.String(20), nullable=True, server_default='monthly')
    )


def downgrade():
    # Remove interest calculation type and compound frequency columns
    op.drop_column('banking_settings', 'compound_frequency')
    op.drop_column('banking_settings', 'interest_calculation_type')
