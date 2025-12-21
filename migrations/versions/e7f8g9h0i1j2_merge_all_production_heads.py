"""Continue from insurance feature merge

Revision ID: e7f8g9h0i1j2
Revises: d6e7f8g9h0i1
Create Date: 2025-11-23 18:00:00.000000

"""


# revision identifiers, used by Alembic.
revision = 'e7f8g9h0i1j2'
down_revision = 'd6e7f8g9h0i1'
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration - no schema changes needed
    # Both parent migrations have already applied their respective changes
    pass


def downgrade():
    # This is a merge migration - no schema changes needed
    pass
