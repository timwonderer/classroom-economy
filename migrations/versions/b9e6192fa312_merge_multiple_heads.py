"""merge multiple heads

Revision ID: b9e6192fa312
Revises: 3f43ff5fa23e, 89c0b5675859
Create Date: 2025-06-20 19:55:33.250506

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9e6192fa312'
down_revision = ('3f43ff5fa23e', '89c0b5675859')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
