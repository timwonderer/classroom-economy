"""Create canonical attendance session/state tables and backfill from tap events.

Revision ID: c6a8f6d1e2b3
Revises: b1c2d3e4f5a6
Create Date: 2026-05-29
"""

from datetime import timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c6a8f6d1e2b3"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def unique_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _to_utc(dt_value):
    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def _tap_reason_enum():
    """Use plain text for retired transitional TapEvent reason values."""
    return sa.String(length=32)


def _class_timezone_map(conn):
    rows = conn.execute(
        sa.text("SELECT class_id, class_timezone FROM classes WHERE class_id IS NOT NULL")
    ).mappings().all()
    return {row["class_id"]: row["class_timezone"] or "UTC" for row in rows}


def _resolve_done_date(class_timezone_map, class_id, event_ts_utc):
    tz_name = class_timezone_map.get(class_id) or "UTC"
    try:
        import pytz

        local_dt = event_ts_utc.astimezone(pytz.timezone(tz_name))
        return local_dt.date()
    except Exception:
        return event_ts_utc.date()


def _upsert_state(conn, payload):
    existing = conn.execute(
        sa.text(
            """
            SELECT id
            FROM seat_attendance_state
            WHERE seat_id = :seat_id
              AND class_id = :class_id
              AND period = :period
            LIMIT 1
            """
        ),
        {
            "seat_id": payload["seat_id"],
            "class_id": payload["class_id"],
            "period": payload["period"],
        },
    ).mappings().first()

    if existing:
        conn.execute(
            sa.text(
                """
                UPDATE seat_attendance_state
                SET student_id = :student_id,
                    is_active = :is_active,
                    open_session_id = :open_session_id,
                    done_for_day_date = :done_for_day_date,
                    last_event_at = :last_event_at,
                    last_event_status = :last_event_status,
                    last_reason = :last_reason,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {**payload, "id": existing["id"]},
        )
    else:
        created_at = payload.get("created_at") or payload.get("updated_at")
        conn.execute(
            sa.text(
                """
                INSERT INTO seat_attendance_state (
                    student_id, seat_id, class_id, period, is_active,
                    open_session_id, done_for_day_date, created_at,
                    last_event_at, last_event_status, last_reason, updated_at
                ) VALUES (
                    :student_id, :seat_id, :class_id, :period, :is_active,
                    :open_session_id, :done_for_day_date, :created_at,
                    :last_event_at, :last_event_status, :last_reason, :updated_at
                )
                """
            ),
            {**payload, "created_at": created_at},
        )


def _backfill_from_tap_events(conn):
    if not table_exists("tap_events"):
        return

    # student_id may have been dropped by the identity-repoint migration.
    # On a clean v2 DB there are zero tap_events anyway, so skip backfill entirely.
    if not column_exists("tap_events", "student_id"):
        return

    existing_sessions = conn.execute(sa.text("SELECT COUNT(1) FROM attendance_sessions")).scalar() or 0
    if existing_sessions > 0:
        return

    rows = conn.execute(
        sa.text(
            """
            SELECT
                id,
                student_id,
                seat_id,
                class_id,
                period,
                status,
                "timestamp",
                reason,
                reason_code
            FROM tap_events
            WHERE is_deleted = false
              AND seat_id IS NOT NULL
              AND class_id IS NOT NULL
            ORDER BY seat_id, class_id, period, "timestamp", id
            """
        )
    ).mappings().all()

    class_timezone_map = _class_timezone_map(conn)
    open_session_by_key = {}

    for row in rows:
        event_ts = _to_utc(row["timestamp"])
        if not event_ts:
            continue
        key = (row["seat_id"], row["class_id"], row["period"])
        open_session_id = open_session_by_key.get(key)

        if row["status"] == "active":
            if not open_session_id:
                open_session_id = conn.execute(
                    sa.text(
                        """
                        INSERT INTO attendance_sessions (
                            student_id, seat_id, class_id, period,
                            started_at, start_reason, source_tap_event_id,
                            created_at, updated_at
                        ) VALUES (
                            :student_id, :seat_id, :class_id, :period,
                            :started_at, :start_reason, :source_tap_event_id,
                            :created_at, :updated_at
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "student_id": row["student_id"],
                        "seat_id": row["seat_id"],
                        "class_id": row["class_id"],
                        "period": row["period"],
                        "started_at": event_ts,
                        "start_reason": row["reason"],
                        "source_tap_event_id": row["id"],
                        "created_at": event_ts,
                        "updated_at": event_ts,
                    },
                ).scalar()
                open_session_by_key[key] = open_session_id

            _upsert_state(
                conn,
                {
                    "student_id": row["student_id"],
                    "seat_id": row["seat_id"],
                    "class_id": row["class_id"],
                    "period": row["period"],
                    "is_active": True,
                    "open_session_id": open_session_id,
                    "done_for_day_date": None,
                    "last_event_at": event_ts,
                    "last_event_status": row["status"],
                    "last_reason": row["reason"],
                    "updated_at": event_ts,
                },
            )
            continue

        if open_session_id:
            started_at = conn.execute(
                sa.text("SELECT started_at FROM attendance_sessions WHERE id = :id"),
                {"id": open_session_id},
            ).scalar()
            started_at = _to_utc(started_at) if started_at else event_ts
            ended_at = event_ts if event_ts >= started_at else started_at
            duration_seconds = int(max(0, (ended_at - started_at).total_seconds()))

            conn.execute(
                sa.text(
                    """
                    UPDATE attendance_sessions
                    SET ended_at = :ended_at,
                        duration_seconds = :duration_seconds,
                        end_reason = :end_reason,
                        end_reason_code = :end_reason_code,
                        source_tap_event_id = :source_tap_event_id,
                        updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": open_session_id,
                    "ended_at": ended_at,
                    "duration_seconds": duration_seconds,
                    "end_reason": row["reason"],
                    "end_reason_code": row["reason_code"],
                    "source_tap_event_id": row["id"],
                    "updated_at": event_ts,
                },
            )
            open_session_by_key.pop(key, None)
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO attendance_sessions (
                        student_id, seat_id, class_id, period,
                        started_at, ended_at, duration_seconds,
                        start_reason, end_reason, end_reason_code, source_tap_event_id,
                        created_at, updated_at
                    ) VALUES (
                        :student_id, :seat_id, :class_id, :period,
                        :started_at, :ended_at, :duration_seconds,
                        :start_reason, :end_reason, :end_reason_code, :source_tap_event_id,
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "student_id": row["student_id"],
                    "seat_id": row["seat_id"],
                    "class_id": row["class_id"],
                    "period": row["period"],
                    "started_at": event_ts,
                    "ended_at": event_ts,
                    "duration_seconds": 0,
                    "start_reason": row["reason"],
                    "end_reason": row["reason"],
                    "end_reason_code": row["reason_code"],
                    "source_tap_event_id": row["id"],
                    "created_at": event_ts,
                    "updated_at": event_ts,
                },
            )

        reason_text = (row["reason"] or "").strip().lower()
        done_date = None
        if row["status"] == "inactive" and reason_text in {"done", "done for the day"}:
            done_date = _resolve_done_date(class_timezone_map, row["class_id"], event_ts)

        _upsert_state(
            conn,
            {
                "student_id": row["student_id"],
                "seat_id": row["seat_id"],
                "class_id": row["class_id"],
                "period": row["period"],
                "is_active": False,
                "open_session_id": None,
                "done_for_day_date": done_date,
                "last_event_at": event_ts,
                "last_event_status": row["status"],
                "last_reason": row["reason"],
                "updated_at": event_ts,
            },
        )


def upgrade():
    if not table_exists("attendance_sessions"):
        op.create_table(
            "attendance_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("seat_id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("period", sa.String(length=10), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("start_reason", sa.String(length=50), nullable=True),
            sa.Column("end_reason", sa.String(length=50), nullable=True),
            sa.Column(
                "end_reason_code",
                _tap_reason_enum(),
                nullable=True,
            ),
            sa.Column("source_tap_event_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            if not column_exists("attendance_sessions", "seat_id"):
                batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
            if not column_exists("attendance_sessions", "class_id"):
                batch_op.add_column(sa.Column("class_id", sa.String(length=36), nullable=True))
            if not column_exists("attendance_sessions", "period"):
                batch_op.add_column(sa.Column("period", sa.String(length=10), nullable=True))
            if not column_exists("attendance_sessions", "started_at"):
                batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
            if not column_exists("attendance_sessions", "ended_at"):
                batch_op.add_column(sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
            if not column_exists("attendance_sessions", "duration_seconds"):
                batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
            if not column_exists("attendance_sessions", "start_reason"):
                batch_op.add_column(sa.Column("start_reason", sa.String(length=50), nullable=True))
            if not column_exists("attendance_sessions", "end_reason"):
                batch_op.add_column(sa.Column("end_reason", sa.String(length=50), nullable=True))
            if not column_exists("attendance_sessions", "end_reason_code"):
                batch_op.add_column(
                    sa.Column(
                        "end_reason_code",
                        _tap_reason_enum(),
                        nullable=True,
                    )
                )
            if not column_exists("attendance_sessions", "source_tap_event_id"):
                batch_op.add_column(sa.Column("source_tap_event_id", sa.Integer(), nullable=True))
            if not column_exists("attendance_sessions", "created_at"):
                batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
            if not column_exists("attendance_sessions", "updated_at"):
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    if not index_exists("attendance_sessions", "ix_attendance_sessions_seat_class_period_start"):
        op.create_index(
            "ix_attendance_sessions_seat_class_period_start",
            "attendance_sessions",
            ["seat_id", "class_id", "period", "started_at"],
            unique=False,
        )

    if not table_exists("seat_attendance_state"):
        op.create_table(
            "seat_attendance_state",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("seat_id", sa.Integer(), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("period", sa.String(length=10), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("open_session_id", sa.Integer(), nullable=True),
            sa.Column("done_for_day_date", sa.Date(), nullable=True),
            sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_event_status", sa.String(length=10), nullable=True),
            sa.Column("last_reason", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("seat_id", "class_id", "period", name="uq_attendance_state_scope"),
        )
    else:
        with op.batch_alter_table("seat_attendance_state", schema=None) as batch_op:
            if not column_exists("seat_attendance_state", "seat_id"):
                batch_op.add_column(sa.Column("seat_id", sa.Integer(), nullable=True))
            if not column_exists("seat_attendance_state", "class_id"):
                batch_op.add_column(sa.Column("class_id", sa.String(length=36), nullable=True))
            if not column_exists("seat_attendance_state", "period"):
                batch_op.add_column(sa.Column("period", sa.String(length=10), nullable=True))
            if not column_exists("seat_attendance_state", "is_active"):
                batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=True))
            if not column_exists("seat_attendance_state", "open_session_id"):
                batch_op.add_column(sa.Column("open_session_id", sa.Integer(), nullable=True))
            if not column_exists("seat_attendance_state", "done_for_day_date"):
                batch_op.add_column(sa.Column("done_for_day_date", sa.Date(), nullable=True))
            if not column_exists("seat_attendance_state", "last_event_at"):
                batch_op.add_column(sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True))
            if not column_exists("seat_attendance_state", "last_event_status"):
                batch_op.add_column(sa.Column("last_event_status", sa.String(length=10), nullable=True))
            if not column_exists("seat_attendance_state", "last_reason"):
                batch_op.add_column(sa.Column("last_reason", sa.String(length=50), nullable=True))
            if not column_exists("seat_attendance_state", "created_at"):
                batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
            if not column_exists("seat_attendance_state", "updated_at"):
                batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    if not index_exists("seat_attendance_state", "ix_attendance_state_seat_period"):
        op.create_index(
            "ix_attendance_state_seat_period",
            "seat_attendance_state",
            ["seat_id", "period"],
            unique=False,
        )

    conn = op.get_bind()
    # Ensure scope uniqueness on legacy stub tables after required columns are present.
    if table_exists("seat_attendance_state") and not unique_constraint_exists(
        "seat_attendance_state", "uq_attendance_state_scope"
    ):
        conn.execute(
            sa.text(
                """
                ALTER TABLE seat_attendance_state
                ADD CONSTRAINT uq_attendance_state_scope UNIQUE (seat_id, class_id, period)
                """
            )
        )

    _backfill_from_tap_events(conn)


def downgrade():
    if table_exists("seat_attendance_state"):
        if index_exists("seat_attendance_state", "ix_attendance_state_student_period"):
            op.drop_index("ix_attendance_state_student_period", table_name="seat_attendance_state")
        op.drop_table("seat_attendance_state")

    if table_exists("attendance_sessions"):
        if index_exists("attendance_sessions", "ix_attendance_sessions_seat_class_period_start"):
            op.drop_index("ix_attendance_sessions_seat_class_period_start", table_name="attendance_sessions")
        op.drop_table("attendance_sessions")
