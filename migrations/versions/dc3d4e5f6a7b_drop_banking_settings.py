"""Remove the retired BankingSettings policy table.

EconomicEngine is the canonical class banking policy authority.  The legacy
table must not remain available as a second source of overdraft or interest
configuration.
"""

from alembic import op
import sqlalchemy as sa


revision = "dc3d4e5f6a7b"
down_revision = "db2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("banking_settings"):
        op.drop_table("banking_settings")


def downgrade():
    raise NotImplementedError(
        "BankingSettings retirement is irreversible. EconomicEngine is the "
        "canonical class banking policy authority."
    )
