"""Drop legacy store tables after canonical store cutover.

Revision ID: 10a2b3c4d5e6
Revises: 4beac340ed58
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "10a2b3c4d5e6"
down_revision = "4beac340ed58"
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
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade():
    op.drop_table("redemption_audit_logs")
    op.drop_table("store_item_blocks")
    op.drop_table("student_items")


def downgrade():
    if not table_exists("student_items"):
        op.create_table(
            "student_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("store_item_id", sa.Integer(), sa.ForeignKey("store_items.id"), nullable=False),
            sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("join_code", sa.String(20), nullable=True, index=True),
            sa.Column("correlation_id", sa.String(100), nullable=False, index=True),
            sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="purchased"),
            sa.Column("redemption_details", sa.Text(), nullable=True),
            sa.Column("redemption_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("purchase_transaction_id", sa.Integer(), sa.ForeignKey("ledger_transaction.id"), nullable=True, index=True),
            sa.Column("is_from_bundle", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("bundle_remaining", sa.Integer(), nullable=True),
            sa.Column("quantity_purchased", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("uses_remaining", sa.Integer(), nullable=True),
            sa.Column("collective_goal_instance_code", sa.String(36), nullable=True, index=True),
        )
        if not index_exists("student_items", "ix_student_items_class_id"):
            op.create_index("ix_student_items_class_id", "student_items", ["class_id"])
        if not index_exists("student_items", "ix_student_items_seat_id"):
            op.create_index("ix_student_items_seat_id", "student_items", ["seat_id"])
        if not index_exists("student_items", "ix_student_items_join_code"):
            op.create_index("ix_student_items_join_code", "student_items", ["join_code"])
        if not index_exists("student_items", "ix_student_items_correlation_id"):
            op.create_index("ix_student_items_correlation_id", "student_items", ["correlation_id"])
        if not index_exists("student_items", "ix_student_items_purchase_transaction_id"):
            op.create_index("ix_student_items_purchase_transaction_id", "student_items", ["purchase_transaction_id"])

    if not table_exists("store_item_blocks"):
        op.create_table(
            "store_item_blocks",
            sa.Column("store_item_id", sa.Integer(), sa.ForeignKey("store_items.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("block", sa.String(10), primary_key=True),
            sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("join_code", sa.String(20), nullable=True, index=True),
        )
        if not index_exists("store_item_blocks", "ix_store_item_blocks_item"):
            op.create_index("ix_store_item_blocks_item", "store_item_blocks", ["store_item_id"])
        if not index_exists("store_item_blocks", "ix_store_item_blocks_block"):
            op.create_index("ix_store_item_blocks_block", "store_item_blocks", ["block"])

    if not table_exists("redemption_audit_logs"):
        op.create_table(
            "redemption_audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("student_item_id", sa.Integer(), sa.ForeignKey("student_items.id"), nullable=True, index=True),
            sa.Column("student_display_name", sa.String(120), nullable=False),
            sa.Column("class_display_label", sa.String(120), nullable=False),
            sa.Column("action", sa.String(20), nullable=False, index=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("class_id", sa.String(36), sa.ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("seat_id", sa.Integer(), sa.ForeignKey("seats.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("join_code", sa.String(20), nullable=True, index=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
            sa.Column("source", sa.String(20), nullable=False, server_default="live", index=True),
        )
        if not index_exists("redemption_audit_logs", "ix_redemption_audit_logs_teacher_timestamp"):
            op.create_index("ix_redemption_audit_logs_teacher_timestamp", "redemption_audit_logs", ["teacher_id", "timestamp"])
        if not index_exists("redemption_audit_logs", "ix_redemption_audit_logs_student_item_id"):
            op.create_index("ix_redemption_audit_logs_student_item_id", "redemption_audit_logs", ["student_item_id"])
        if not index_exists("redemption_audit_logs", "ix_redemption_audit_logs_timestamp"):
            op.create_index("ix_redemption_audit_logs_timestamp", "redemption_audit_logs", ["timestamp"])
        if not index_exists("redemption_audit_logs", "ix_redemption_audit_logs_source"):
            op.create_index("ix_redemption_audit_logs_source", "redemption_audit_logs", ["source"])
