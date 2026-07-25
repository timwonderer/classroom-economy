"""Add tap_enabled to SeatAttendanceState

Revision ID: cb55646cb43e
Revises: 042824e29710
Create Date: 2026-06-30 03:49:40.056766

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cb55646cb43e'
down_revision = '042824e29710'
branch_labels = None
depends_on = None

def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))
    except sa.exc.NoSuchTableError:
        return False

def upgrade():
    if not table_exists('seat_attendance_state'):
        return

    if not column_exists('seat_attendance_state', 'tap_enabled'):
        # 1. Add tap_enabled to seat_attendance_state
        op.add_column(
            'seat_attendance_state',
            sa.Column('tap_enabled', sa.Boolean(), server_default=sa.true(), nullable=False),
        )

    if not table_exists('student_blocks'):
        return

    conn = op.get_bind()
    if column_exists('student_blocks', 'tap_enabled'):
        # 2. Backfill tap_enabled from student_blocks
        conn.execute(
            sa.text("""
                UPDATE seat_attendance_state sas
                SET tap_enabled = sb.tap_enabled
                FROM student_blocks sb
                WHERE sas.seat_id = sb.seat_id
                  AND sas.period = sb.period
            """)
        )

    if table_exists('entitlement_events') and column_exists('student_blocks', 'rent_hall_passes'):
        # 3. Insert GRANT events into entitlement_events for any rent_hall_passes
        # INV-OBL-002: Entitlement balances MUST NOT be stored as authoritative state
        conn.execute(
            sa.text("""
                INSERT INTO entitlement_events (
                    seat_id, class_id, assessment_id, trigger_id, quantity_delta, event_type, occurred_at
                )
                SELECT
                    sb.seat_id,
                    s.class_id,
                    NULL,
                    'legacy_rent_hall_pass_backfill_' || sb.id,
                    sb.rent_hall_passes,
                    'GRANT',
                    NOW()
                FROM student_blocks sb
                JOIN seats s ON sb.seat_id = s.id
                WHERE sb.rent_hall_passes > 0
            """)
        )

def downgrade():
    if column_exists('seat_attendance_state', 'tap_enabled'):
        op.drop_column('seat_attendance_state', 'tap_enabled')
