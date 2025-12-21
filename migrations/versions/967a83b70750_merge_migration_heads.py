"""merge migration heads

Revision ID: 967a83b70750
Revises: a1b2c3d4e5f8, cf7a5cda2d0a
Create Date: 2025-12-21 11:38:35.266958

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '967a83b70750'
down_revision = ('a1b2c3d4e5f8', 'cf7a5cda2d0a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
