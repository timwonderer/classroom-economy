"""Add actor_seat_id to attendance_sessions and merge heads

Revision ID: 9f8e7d6c5b4a
Revises: f84c7ad2c1aa, a1b2c3d4e5f6
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9f8e7d6c5b4a"
down_revision = ("f84c7ad2c1aa", "a1b2c3d4e5f6")
branch_labels = None
depends_on = None


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


def upgrade():
    if not column_exists("attendance_sessions", "actor_seat_id"):
        op.add_column(
            "attendance_sessions",
            sa.Column("actor_seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=True),
        )
    if not index_exists("attendance_sessions", "ix_attendance_sessions_actor_seat_id"):
        op.create_index(
            "ix_attendance_sessions_actor_seat_id",
            "attendance_sessions",
            ["actor_seat_id"],
            unique=False,
        )


def downgrade():
    if index_exists("attendance_sessions", "ix_attendance_sessions_actor_seat_id"):
        op.drop_index("ix_attendance_sessions_actor_seat_id", table_name="attendance_sessions")
    if column_exists("attendance_sessions", "actor_seat_id"):
        op.drop_column("attendance_sessions", "actor_seat_id")
