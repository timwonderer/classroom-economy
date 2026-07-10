"""Move student recovery fields to users table (DOM-IDEN-002 §V)

Adds reset_code, reset_code_generated_at, reset_code_expires_at to users.
Drops password_hash, money_action_cooldown_until, has_completed_setup from users.

Revision ID: e27bb00d7853
Revises: 572a1b9a2d74
Create Date: 2026-07-10 18:21:49.961778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

# ============================================================================
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = 'e27bb00d7853'
down_revision = '572a1b9a2d74'
branch_labels = None
depends_on = None


def upgrade():
    # Add student recovery fields to users (DOM-IDEN-002 §V)
    if not column_exists('users', 'reset_code'):
        op.add_column('users', sa.Column('reset_code', sa.String(length=8), nullable=True))
    if not column_exists('users', 'reset_code_generated_at'):
        op.add_column('users', sa.Column('reset_code_generated_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('users', 'reset_code_expires_at'):
        op.add_column('users', sa.Column('reset_code_expires_at', sa.DateTime(timezone=True), nullable=True))

    # Drop legacy fields removed in DOM-IDEN-002 v2.1
    if column_exists('users', 'password_hash'):
        op.drop_column('users', 'password_hash')
    if column_exists('users', 'money_action_cooldown_until'):
        op.drop_column('users', 'money_action_cooldown_until')
    if column_exists('users', 'has_completed_setup'):
        op.drop_column('users', 'has_completed_setup')


def downgrade():
    # Restore dropped columns
    if not column_exists('users', 'has_completed_setup'):
        op.add_column('users', sa.Column('has_completed_setup', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    if not column_exists('users', 'money_action_cooldown_until'):
        op.add_column('users', sa.Column('money_action_cooldown_until', postgresql.TIMESTAMP(timezone=True), nullable=True))
    if not column_exists('users', 'password_hash'):
        op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))

    # Remove recovery fields
    if column_exists('users', 'reset_code_expires_at'):
        op.drop_column('users', 'reset_code_expires_at')
    if column_exists('users', 'reset_code_generated_at'):
        op.drop_column('users', 'reset_code_generated_at')
    if column_exists('users', 'reset_code'):
        op.drop_column('users', 'reset_code')
