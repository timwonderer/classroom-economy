"""Add monetary/non-monetary toggle to insurance system

Revision ID: b2c3d4e5f6g7
Revises: a2b3c4d5e6f7
Create Date: 2025-11-16 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_monetary field to insurance_policies table
    # This determines if students claim dollar amounts (monetary) or items/services (non-monetary)
    op.add_column('insurance_policies',
        sa.Column('is_monetary', sa.Boolean(), nullable=True))

    # Add claim_item field to insurance_claims table
    # For non-monetary claims: what item or service the student is claiming
    op.add_column('insurance_claims',
        sa.Column('claim_item', sa.Text(), nullable=True))

    # Add comments field to insurance_claims table
    # Optional field for students to add additional comments to any claim
    op.add_column('insurance_claims',
        sa.Column('comments', sa.Text(), nullable=True))

    # Update existing policies to be monetary (default behavior)
    op.execute("UPDATE insurance_policies SET is_monetary = 1 WHERE is_monetary IS NULL")

    # Make is_monetary non-nullable after setting defaults
    op.alter_column('insurance_policies', 'is_monetary', nullable=False)


def downgrade():
    # Remove the added columns
    op.drop_column('insurance_claims', 'comments')
    op.drop_column('insurance_claims', 'claim_item')
    op.drop_column('insurance_policies', 'is_monetary')
