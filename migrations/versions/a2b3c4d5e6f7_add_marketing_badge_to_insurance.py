"""add marketing badge to insurance

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2025-11-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Add marketing_badge column to insurance_policies table
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('marketing_badge', sa.String(length=50), nullable=True))


def downgrade():
    # Remove marketing_badge column
    with op.batch_alter_table('insurance_policies', schema=None) as batch_op:
        batch_op.drop_column('marketing_badge')
