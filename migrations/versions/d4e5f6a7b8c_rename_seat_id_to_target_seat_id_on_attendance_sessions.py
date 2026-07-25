"""Rename seat_id to target_seat_id and add actor_seat_id on attendance_sessions.

Revision ID: d4e5f6a7b8c
Revises: c3d4e5f8a9b
Create Date: 2026-07-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c"
down_revision = "c3d4e5f8a9b"
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


def upgrade():
    # 1. Rename seat_id → target_seat_id on attendance_sessions (DOM-PROD-001 §XI.1)
    if column_exists("attendance_sessions", "seat_id") and not column_exists("attendance_sessions", "target_seat_id"):
        # Drop the old index on seat_id
        if index_exists("attendance_sessions", "ix_attendance_sessions_seat_id"):
            op.drop_index("ix_attendance_sessions_seat_id", table_name="attendance_sessions")

        # Drop the old FK on seat_id
        for fk in get_foreign_keys_by_column("attendance_sessions", "seat_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "attendance_sessions", type_="foreignkey")

        # Rename the column
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.alter_column("seat_id", new_column_name="target_seat_id")

        # Re-create FK and index under the new name
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "attendance_sessions_target_seat_id_fkey",
                "seats",
                ["target_seat_id"],
                ["id"],
                ondelete="CASCADE",
            )

        if not index_exists("attendance_sessions", "ix_attendance_sessions_target_seat_id"):
            op.create_index(
                "ix_attendance_sessions_target_seat_id",
                "attendance_sessions",
                ["target_seat_id"],
                unique=False,
            )

    # 2. Add actor_seat_id if missing
    if not column_exists("attendance_sessions", "actor_seat_id"):
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "actor_seat_id",
                    sa.Integer(),
                    sa.ForeignKey("seats.id", ondelete="SET NULL"),
                    nullable=False,
                )
            )
        if not index_exists("attendance_sessions", "ix_attendance_sessions_actor_seat_id"):
            op.create_index(
                "ix_attendance_sessions_actor_seat_id",
                "attendance_sessions",
                ["actor_seat_id"],
                unique=False,
            )
    else:
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.alter_column("actor_seat_id", existing_type=sa.Integer(), nullable=False)

    # 3. Tighten target_user_id to non-nullable
    if column_exists("attendance_sessions", "target_user_id"):
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.alter_column("target_user_id", existing_type=sa.Integer(), nullable=False)

    # 4. Tighten hall_pass_logs nullable columns
    if column_exists("hall_pass_logs", "requested_by_seat_id"):
        with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
            batch_op.alter_column("requested_by_seat_id", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("approved_by_seat_id", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("correlation_id", existing_type=sa.String(length=100), nullable=False)
            batch_op.alter_column("hall_pass_id", existing_type=sa.String(length=100), nullable=False)


def downgrade():
    # Reverse nullability tightening on hall_pass_logs
    if column_exists("hall_pass_logs", "requested_by_seat_id"):
        with op.batch_alter_table("hall_pass_logs", schema=None) as batch_op:
            batch_op.alter_column("requested_by_seat_id", existing_type=sa.Integer(), nullable=True)
            batch_op.alter_column("approved_by_seat_id", existing_type=sa.Integer(), nullable=True)
            batch_op.alter_column("correlation_id", existing_type=sa.String(length=100), nullable=True)
            batch_op.alter_column("hall_pass_id", existing_type=sa.String(length=100), nullable=True)

    # Reverse nullability tightening on attendance_sessions
    if column_exists("attendance_sessions", "target_user_id"):
        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.alter_column("target_user_id", existing_type=sa.Integer(), nullable=True)

    # Reverse: rename target_seat_id back to seat_id, drop actor_seat_id
    if column_exists("attendance_sessions", "actor_seat_id"):
        for fk in get_foreign_keys_by_column("attendance_sessions", "actor_seat_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "attendance_sessions", type_="foreignkey")
        if index_exists("attendance_sessions", "ix_attendance_sessions_actor_seat_id"):
            op.drop_index("ix_attendance_sessions_actor_seat_id", table_name="attendance_sessions")
        op.drop_column("attendance_sessions", "actor_seat_id")

    if column_exists("attendance_sessions", "target_seat_id") and not column_exists("attendance_sessions", "seat_id"):
        if index_exists("attendance_sessions", "ix_attendance_sessions_target_seat_id"):
            op.drop_index("ix_attendance_sessions_target_seat_id", table_name="attendance_sessions")
        for fk in get_foreign_keys_by_column("attendance_sessions", "target_seat_id"):
            if fk.get("name"):
                op.drop_constraint(fk["name"], "attendance_sessions", type_="foreignkey")

        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.alter_column("target_seat_id", new_column_name="seat_id")

        with op.batch_alter_table("attendance_sessions", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "attendance_sessions_seat_id_fkey",
                "seats",
                ["seat_id"],
                ["id"],
                ondelete="CASCADE",
            )
        op.create_index("ix_attendance_sessions_seat_id", "attendance_sessions", ["seat_id"], unique=False)
