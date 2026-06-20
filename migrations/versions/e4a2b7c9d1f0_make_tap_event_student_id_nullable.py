"""Make tap_events.student_id nullable for seat/class-scoped canonical writes.

Revision ID: e4a2b7c9d1f0
Revises: f2c9d1a6b7e8
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4a2b7c9d1f0"
down_revision = "f2c9d1a6b7e8"
branch_labels = None
depends_on = None


def column_nullable(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        for column in inspector.get_columns(table_name):
            if column.get("name") == column_name:
                return bool(column.get("nullable"))
    except sa.exc.NoSuchTableError:
        return None
    return None


def _backfill_student_ids_from_seats():
    op.execute(
        sa.text(
            """
            UPDATE tap_events AS te
            SET student_id = s.student_id
            FROM seats AS s
            WHERE te.student_id IS NULL
              AND te.seat_id = s.id
              AND s.student_id IS NOT NULL
            """
        )
    )


def upgrade():
    nullable = column_nullable("tap_events", "student_id")
    if nullable is False:
        op.alter_column("tap_events", "student_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    _backfill_student_ids_from_seats()

    conn = op.get_bind()
    missing_count = conn.execute(
        sa.text("SELECT COUNT(1) FROM tap_events WHERE student_id IS NULL")
    ).scalar()
    if missing_count:
        raise RuntimeError(
            "Cannot downgrade e4a2b7c9d1f0: tap_events contains rows with NULL student_id "
            "that cannot be backfilled from seats."
        )

    nullable = column_nullable("tap_events", "student_id")
    if nullable is True:
        op.alter_column("tap_events", "student_id", existing_type=sa.Integer(), nullable=False)
