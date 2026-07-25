"""merge policy transition fk head

Revision ID: 7a9b8c6d5e4f
Revises: a3f2c8d91b47, 8f1a2c3d4b5e
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7a9b8c6d5e4f"
down_revision = ("a3f2c8d91b47", "8f1a2c3d4b5e")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
