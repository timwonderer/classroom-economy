"""Finalize PROD domain schema alignment for the live database.

Revision ID: c3d4e5f8a9b
Revises: b2c3d4e5f8a
Create Date: 2026-07-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f8a9b"
down_revision = "b2c3d4e5f8a"
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
    # attendance_sessions: seat-actor owned productivity rows with user-level single-active enforcement.
    if table_exists("attendance_sessions"):
        if column_exists("attendance_sessions", "user_id") and not column_exists("attendance_sessions", "target_user_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.alter_column("user_id", new_column_name="target_user_id")
        elif not column_exists("attendance_sessions", "target_user_id"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
                )

        if column_exists("attendance_sessions", "created_at") and not column_exists("attendance_sessions", "timestamp"):
            if column_exists("attendance_sessions", "created_at"):
                with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                    batch_op.alter_column("created_at", new_column_name="timestamp")
        elif not column_exists("attendance_sessions", "timestamp"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))

        if not column_exists("attendance_sessions", "mechanism"):
            with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
                batch_op.add_column(sa.Column("mechanism", sa.String(length=20), nullable=False, server_default="teacher"))

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

    # hall_pass_logs: immutable approved-pass fact table.
    if table_exists("hall_pass_logs"):
        if column_exists("hall_pass_logs", "request_time") and not column_exists("hall_pass_logs", "timestamp"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.alter_column("request_time", new_column_name="timestamp")
        elif not column_exists("hall_pass_logs", "timestamp"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.add_column(sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))

        if not column_exists("hall_pass_logs", "class_id"):
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.add_column(sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False))
        else:
            with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                batch_op.alter_column("class_id", existing_type=sa.String(length=36), nullable=False)

        for column_name, column_type, kwargs in (
            ("requested_by_seat_id", sa.Integer(), {"nullable": True, "fk": True}),
            ("approved_by_seat_id", sa.Integer(), {"nullable": True, "fk": True}),
            ("correlation_id", sa.String(length=100), {"nullable": True, "index": True}),
            ("hall_pass_id", sa.String(length=100), {"nullable": True, "index": True}),
            ("destination", sa.String(length=255), {"nullable": True}),
        ):
            if not column_exists("hall_pass_logs", column_name):
                with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
                    if kwargs.get("fk"):
                        batch_op.add_column(
                            sa.Column(column_name, column_type, sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=kwargs["nullable"])
                        )
                    else:
                        batch_op.add_column(sa.Column(column_name, column_type, nullable=kwargs["nullable"]))
                if kwargs.get("index"):
                    op.create_index(f"ix_hall_pass_logs_{column_name}", "hall_pass_logs", [column_name], unique=False)

        for column_name in ("seat_id", "reason", "status", "period", "join_code", "decision_time", "left_time", "return_time"):
            drop_column_if_exists("hall_pass_logs", column_name)

    # payroll_event: append-only payroll record table.
    if not table_exists("payroll_event"):
        op.create_table(
            "payroll_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("class_id", sa.String(length=36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=False),
            sa.Column("target_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="CASCADE"), nullable=False),
            sa.Column("correlation_id", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("policy_version_id", sa.Integer(), sa.ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=False),
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

    # policy lineage pointer on settings.
    if table_exists("payroll_settings"):
        if not column_exists("payroll_settings", "policy_version_id"):
            with op.batch_alter_table("payroll_settings", schema=None) as batch_op:
                batch_op.add_column(sa.Column("policy_version_id", sa.Integer(), nullable=True))
        if column_exists("payroll_settings", "policy_version_id") and not index_exists("payroll_settings", "ix_payroll_settings_policy_version_id"):
            op.create_index("ix_payroll_settings_policy_version_id", "payroll_settings", ["policy_version_id"], unique=False)
        if column_exists("payroll_settings", "policy_version_id") and not foreign_key_exists("payroll_settings", "fk_payroll_settings_policy_version_id"):
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
    raise NotImplementedError("Downgrade intentionally unsupported for this migration.")
