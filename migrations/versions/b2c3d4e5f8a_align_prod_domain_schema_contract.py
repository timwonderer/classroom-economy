"""Align PROD domain tables with the revised schema contract.

Revision ID: b2c3d4e5f8a
Revises: a1b2c3d4e5f7
Create Date: 2026-07-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f8a"
down_revision = "a1b2c3d4e5f7"
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
        return column_name in [col["name"] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx["name"] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def unique_constraint_exists(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return constraint_name in [uc["name"] for uc in inspector.get_unique_constraints(table_name)]
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table_name)]
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk["constrained_columns"]
        ]
    except Exception:
        return []


def drop_column_if_exists(table_name, column_name):
    if not column_exists(table_name, column_name):
        return

    for fk in get_foreign_keys_by_column(table_name, column_name):
        if fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")

    op.drop_column(table_name, column_name)


def upgrade():
    # attendance_sessions: canonical seat-actor-class timeline with user-level
    # single-active enforcement.
    if table_exists("attendance_sessions"):
        # Rename seat_id → target_seat_id (DOM-PROD-001 schema contract)
        if column_exists("attendance_sessions", "seat_id") and not column_exists("attendance_sessions", "target_seat_id"):
            if index_exists("attendance_sessions", "ix_attendance_sessions_seat_class_start"):
                op.drop_index("ix_attendance_sessions_seat_class_start", table_name="attendance_sessions")
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.alter_column("seat_id", new_column_name="target_seat_id")

        if column_exists("attendance_sessions", "user_id") and not column_exists("attendance_sessions", "target_user_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.alter_column("user_id", new_column_name="target_user_id")
        elif not column_exists("attendance_sessions", "target_user_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "target_user_id",
                        sa.Integer(),
                        sa.ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True,
                    )
                )

        if not column_exists("attendance_sessions", "actor_seat_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "actor_seat_id",
                        sa.Integer(),
                        sa.ForeignKey("seats.id", ondelete="SET NULL"),
                        nullable=True,
                    )
                )

        if not column_exists("attendance_sessions", "mechanism"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("mechanism", sa.String(length=20), nullable=False, server_default="self"))

        if column_exists("attendance_sessions", "created_at") and not column_exists("attendance_sessions", "timestamp"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.alter_column("created_at", new_column_name="timestamp")
        elif not column_exists("attendance_sessions", "timestamp"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "timestamp",
                        sa.DateTime(timezone=True),
                        nullable=False,
                        server_default=sa.text("now()"),
                    )
                )

        if not column_exists("attendance_sessions", "status"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))

        if not column_exists("attendance_sessions", "reason_code"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("reason_code", sa.String(length=32), nullable=False, server_default="start_work"))

        if not column_exists("attendance_sessions", "hall_pass_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("hall_pass_id", sa.String(length=100), nullable=True))

        for column_name in (
            "period",
            "started_at",
            "ended_at",
            "duration_seconds",
            "start_reason",
            "end_reason",
            "end_reason_code",
            "is_deleted",
            "deleted_at",
            "deleted_by_seat_id",
            "created_at",
            "updated_at",
        ):
            drop_column_if_exists("attendance_sessions", column_name)

        if not index_exists("attendance_sessions", "ix_attendance_sessions_target_user_id_active"):
            op.create_index(
                "ix_attendance_sessions_target_user_id_active",
                "attendance_sessions",
                ["target_user_id"],
                unique=True,
                postgresql_where=sa.text("status = 'active' AND target_user_id IS NOT NULL"),
            )

    # hall_pass_logs: immutable approved-pass history.
    if table_exists("hall_pass_logs"):
        if column_exists("hall_pass_logs", "request_time") and not column_exists("hall_pass_logs", "timestamp"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.alter_column("request_time", new_column_name="timestamp")
        elif not column_exists("hall_pass_logs", "timestamp"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.add_column(sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))

        for column_name in (
            "seat_id",
            "reason",
            "status",
            "period",
            "join_code",
            "decision_time",
            "left_time",
            "return_time",
            "request_time",
        ):
            drop_column_if_exists("hall_pass_logs", column_name)

        if not column_exists("hall_pass_logs", "class_id"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.add_column(sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False))
        else:
            # tighten to documented non-null contract if the table already exists
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)

        for column_name, column_type in (
            ("requested_by_seat_id", sa.Integer()),
            ("approved_by_seat_id", sa.Integer()),
            ("correlation_id", sa.String(length=100)),
            ("hall_pass_id", sa.String(length=100)),
            ("destination", sa.String(length=255)),
        ):
            if not column_exists("hall_pass_logs", column_name):
                with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                    if column_name in ("requested_by_seat_id", "approved_by_seat_id"):
                        batch_op.add_column(sa.Column(column_name, column_type, sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=True))
                    elif column_name == "correlation_id":
                        batch_op.add_column(sa.Column(column_name, column_type, nullable=True, index=True))
                    elif column_name == "hall_pass_id":
                        batch_op.add_column(sa.Column(column_name, column_type, nullable=True, index=True))
                    else:
                        batch_op.add_column(sa.Column(column_name, column_type, nullable=True))

    # payroll_event: canonical append-only payroll event table.
    if not table_exists("payroll_event"):
        op.create_table(
            "payroll_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=False),
            sa.Column("target_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("correlation_id", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("mechanism", sa.String(length=20), nullable=False),
            sa.Column("payroll_event_type", sa.String(length=20), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.UniqueConstraint(
                "class_id",
                "target_seat_id",
                "correlation_id",
                "idempotency_key",
                "payroll_event_type",
                name="uq_payroll_event_replay_guard",
            ),
        )
    else:
        if column_exists("payroll_event", "payroll_run_type") and not column_exists("payroll_event", "payroll_event_type"):
            with op.batch_alter_table("payroll_event", schema=None) as batch_op:
                batch_op.alter_column("payroll_run_type", new_column_name="payroll_event_type")

        if not column_exists("payroll_event", "payroll_event_type"):
            with op.batch_alter_table("payroll_event", schema=None) as batch_op:
                batch_op.add_column(sa.Column("payroll_event_type", sa.String(length=20), nullable=False))

        if not column_exists("payroll_event", "summary_json"):
            with op.batch_alter_table("payroll_event", schema=None) as batch_op:
                batch_op.add_column(sa.Column("summary_json", sa.JSON(), nullable=True))

        if not column_exists("payroll_event", "recorded_at"):
            with op.batch_alter_table("payroll_event", schema=None) as batch_op:
                batch_op.add_column(sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False))

        if not unique_constraint_exists("payroll_event", "uq_payroll_event_replay_guard"):
            with op.batch_alter_table("payroll_event", schema=None) as batch_op:
                batch_op.create_unique_constraint(
                    "uq_payroll_event_replay_guard",
                    ["class_id", "target_seat_id", "correlation_id", "idempotency_key", "payroll_event_type"],
                )

    # payroll_settings gets the policy lineage pointer only.
    if table_exists("payroll_settings"):
        if not column_exists("payroll_settings", "policy_version_id"):
            with op.batch_alter_table("payroll_settings", schema=None) as batch_op:
                batch_op.add_column(sa.Column("policy_version_id", sa.Integer(), nullable=True))

        if column_exists("payroll_settings", "policy_version_id"):
            if not index_exists("payroll_settings", "ix_payroll_settings_policy_version_id"):
                op.create_index(
                    "ix_payroll_settings_policy_version_id",
                    "payroll_settings",
                    ["policy_version_id"],
                    unique=False,
                )
            if not foreign_key_exists("payroll_settings", "fk_payroll_settings_policy_version_id"):
                with op.batch_alter_table("payroll_settings", schema=None) as batch_op:
                    batch_op.create_foreign_key(
                        "fk_payroll_settings_policy_version_id",
                        "policy_versions",
                        ["policy_version_id"],
                        ["id"],
                        ondelete="SET NULL",
                    )

    if table_exists("seat_attendance_state"):
        op.drop_table("seat_attendance_state")


def downgrade():
    raise NotImplementedError(
        "Downgrade is intentionally unsupported for this constitutional schema remediation."
    )
