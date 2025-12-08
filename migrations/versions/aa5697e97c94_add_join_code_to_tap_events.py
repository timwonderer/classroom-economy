"""Add join_code to tap_events for class scoping

Revision ID: aa5697e97c94
Revises: 2060c104e884
Create Date: 2025-12-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


author = 'codex'
# revision identifiers, used by Alembic.
revision = 'aa5697e97c94'
down_revision = '2060c104e884'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tap_events', sa.Column('join_code', sa.String(length=20), nullable=True))
    op.create_index('ix_tap_events_join_code', 'tap_events', ['join_code'], unique=False)

    # Backfill join_code for existing tap events based on claimed seats
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        UPDATE tap_events AS te
        SET join_code = tb.join_code
        FROM teacher_blocks AS tb
        WHERE te.join_code IS NULL
          AND te.student_id = tb.student_id
          AND upper(te.period) = upper(tb.block)
          AND tb.is_claimed = TRUE
          AND tb.join_code IS NOT NULL
        """
    ))


def downgrade():
    op.drop_index('ix_tap_events_join_code', table_name='tap_events')
    op.drop_column('tap_events', 'join_code')
