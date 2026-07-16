"""Drop legacy absorbed tables: obligation_assessment, student_insurance, ticket_correlation_packs, audit_log

Revision ID: 5a1b2c3d4e5f
Revises: 4bf6de0868a4
Create Date: 2026-07-16 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

# ============================================================================
# MIGRATION
# ============================================================================

revision = '5a1b2c3d4e5f'
down_revision = '4bf6de0868a4'
branch_labels = None
depends_on = None

# Tables absorbed by canonical equivalents:
# - obligation_assessment → absorbed by assessment_events (DOM-OBL-001)
# - student_insurance → absorbed by entitlement_events (DOM-OBL-001)
# - ticket_correlation_packs (plural) → replaced by ticket_correlation_pack (singular, DOM-SUP-001)
# - audit_log → replaced by audit_events + chain_heads (DOM-OPS-001)

TABLES_TO_DROP = [
    'obligation_assessment',
    'student_insurance',
    'ticket_correlation_packs',
    'audit_log',
]


def upgrade():
    for table_name in TABLES_TO_DROP:
        if table_exists(table_name):
            op.drop_table(table_name)
            print(f"✅ Dropped table {table_name}")
        else:
            print(f"⚠️  Table {table_name} does not exist, skipping")


def downgrade():
    # Recreate stub tables for rollback safety.
    # These are minimal stubs — the tables were empty or unused at drop time.

    if not table_exists('audit_log'):
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        print("✅ Recreated stub table audit_log")

    if not table_exists('ticket_correlation_packs'):
        op.create_table(
            'ticket_correlation_packs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        print("✅ Recreated stub table ticket_correlation_packs")

    if not table_exists('student_insurance'):
        op.create_table(
            'student_insurance',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        print("✅ Recreated stub table student_insurance")

    if not table_exists('obligation_assessment'):
        op.create_table(
            'obligation_assessment',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        print("✅ Recreated stub table obligation_assessment")
