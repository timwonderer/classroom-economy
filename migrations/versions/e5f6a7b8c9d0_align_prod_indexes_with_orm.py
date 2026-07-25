"""Align PROD indexes with the canonical ORM contract.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c"
branch_labels = None
depends_on = None


def table_exists(table_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx["name"] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def create_index_if_missing(index_name, table_name, columns, *, unique=False, postgresql_where=None):
    if table_exists(table_name) and not index_exists(table_name, index_name):
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=unique,
            postgresql_where=postgresql_where,
        )


def upgrade():
    create_index_if_missing("ix_attendance_sessions_timestamp", "attendance_sessions", ["timestamp"])
    create_index_if_missing("ix_attendance_sessions_reason_code", "attendance_sessions", ["reason_code"])
    create_index_if_missing("ix_attendance_sessions_hall_pass_id", "attendance_sessions", ["hall_pass_id"])

    create_index_if_missing("ix_hall_pass_logs_requested_by_seat_id", "hall_pass_logs", ["requested_by_seat_id"])
    create_index_if_missing("ix_hall_pass_logs_approved_by_seat_id", "hall_pass_logs", ["approved_by_seat_id"])

    create_index_if_missing("ix_payroll_event_class_id", "payroll_event", ["class_id"])
    create_index_if_missing("ix_payroll_event_actor_seat_id", "payroll_event", ["actor_seat_id"])
    create_index_if_missing("ix_payroll_event_target_seat_id", "payroll_event", ["target_seat_id"])
    create_index_if_missing("ix_payroll_event_correlation_id", "payroll_event", ["correlation_id"])
    create_index_if_missing("ix_payroll_event_idempotency_key", "payroll_event", ["idempotency_key"])
    create_index_if_missing("ix_payroll_event_policy_version_id", "payroll_event", ["policy_version_id"])
    create_index_if_missing("ix_payroll_event_recorded_at", "payroll_event", ["recorded_at"])


def downgrade():
    raise NotImplementedError("Downgrade intentionally unsupported for this v2 schema alignment migration.")
