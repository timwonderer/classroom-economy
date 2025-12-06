"""Add join_code to related tables for complete period-level isolation

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f7
Create Date: 2025-12-06 00:00:00.000000

CRITICAL: This migration completes the P0 fix for multi-period isolation by adding
join_code to all remaining tables that need it. This ensures students enrolled in
multiple periods with the same teacher see properly isolated data.

Note: The transaction table already has join_code (added in migration 00212c18b0ac).

Tables updated:
- student_items: Store purchases scoped by class period
- student_insurance: Insurance enrollments scoped by class period
- hall_pass_logs: Hall pass requests scoped by class period
- rent_payments: Rent payments scoped by class period

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5g6'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    """Add join_code columns to related tables."""

    tables_to_update = [
        {
            'name': 'student_items',
            'indexes': [
                ('ix_student_items_join_code', ['join_code']),
                ('ix_student_items_student_join_code', ['student_id', 'join_code'])
            ],
        },
        {
            'name': 'student_insurance',
            'indexes': [
                ('ix_student_insurance_join_code', ['join_code']),
                ('ix_student_insurance_student_join_code', ['student_id', 'join_code'])
            ],
        },
        {
            'name': 'hall_pass_logs',
            'indexes': [
                ('ix_hall_pass_logs_join_code', ['join_code']),
                ('ix_hall_pass_logs_student_join_code', ['student_id', 'join_code'])
            ],
        },
        {
            'name': 'rent_payments',
            'indexes': [
                ('ix_rent_payments_join_code', ['join_code']),
                ('ix_rent_payments_student_join_code', ['student_id', 'join_code'])
            ],
        },
    ]

    column_name = 'join_code'

    for table in tables_to_update:
        table_name = table['name']
        if not column_exists(table_name, column_name):
            op.add_column(
                table_name,
                sa.Column(column_name, sa.String(20), nullable=True)
            )
            print(f"✅ Added {column_name} column to {table_name} table")
        else:
            print(f"⚠️  Column '{column_name}' already exists on '{table_name}', skipping...")

        for index_name, columns in table['indexes']:
            if not index_exists(table_name, index_name):
                op.create_index(index_name, table_name, columns)
                print(f"✅ Added index {index_name}")
            else:
                print(f"⚠️  Index '{index_name}' already exists, skipping...")

    print("")
    print("⚠️  WARNING: Existing records will have NULL join_code")
    print("⚠️  Action required: Backfill join_code for historical data")
    print("⚠️  See below for table-specific SQL examples to backfill join_code:")
    print("")
    print("----")
    print("student_items: If you have a student_items.period column, you can backfill join_code like:")
    print("""UPDATE student_items
    SET join_code = (
        SELECT join_code FROM enrollments
        WHERE enrollments.student_id = student_items.student_id
          AND enrollments.period = student_items.period
        LIMIT 1
    )
    WHERE join_code IS NULL;""")
    print("")
    print("student_insurance: If you have a period or enrollment reference, use:")
    print("""UPDATE student_insurance
    SET join_code = (
        SELECT join_code FROM enrollments
        WHERE enrollments.student_id = student_insurance.student_id
          AND enrollments.period = student_insurance.period
        LIMIT 1
    )
    WHERE join_code IS NULL;""")
    print("")
    print("hall_pass_logs: If hall_pass_logs.period exists, use:")
    print("""UPDATE hall_pass_logs
    SET join_code = (
        SELECT join_code FROM enrollments
        WHERE enrollments.student_id = hall_pass_logs.student_id
          AND enrollments.period = hall_pass_logs.period
        LIMIT 1
    )
    WHERE join_code IS NULL;""")
    print("")
    print("rent_payments: If rent_payments.period exists, use:")
    print("""UPDATE rent_payments
    SET join_code = (
        SELECT join_code FROM enrollments
        WHERE enrollments.student_id = rent_payments.student_id
          AND enrollments.period = rent_payments.period
        LIMIT 1
    )
    WHERE join_code IS NULL;""")
    print("----")
    print("If your schema differs, see docs/security/CRITICAL_SAME_TEACHER_LEAK.md#backfill-join_code for more details.")
    print("")
    print("----")
    print("Table-specific SQL examples to backfill join_code using enrollments.period mapping:")
    print("")
    print("student_items:")
    print("""UPDATE student_items\nSET join_code = (\n    SELECT join_code FROM enrollments\n    WHERE enrollments.student_id = student_items.student_id\n      AND enrollments.period = student_items.period\n    LIMIT 1\n)\nWHERE join_code IS NULL;""")
    print("")
    print("student_insurance:")
    print("""UPDATE student_insurance\nSET join_code = (\n    SELECT join_code FROM enrollments\n    WHERE enrollments.student_id = student_insurance.student_id\n      AND enrollments.period = student_insurance.period\n    LIMIT 1\n)\nWHERE join_code IS NULL;""")
    print("")
    print("hall_pass_logs:")
    print("""UPDATE hall_pass_logs\nSET join_code = (\n    SELECT join_code FROM enrollments\n    WHERE enrollments.student_id = hall_pass_logs.student_id\n      AND enrollments.period = hall_pass_logs.period\n    LIMIT 1\n)\nWHERE join_code IS NULL;""")
    print("")
    print("rent_payments:")
    print("""UPDATE rent_payments\nSET join_code = (\n    SELECT join_code FROM enrollments\n    WHERE enrollments.student_id = rent_payments.student_id\n      AND enrollments.period = rent_payments.period\n    LIMIT 1\n)\nWHERE join_code IS NULL;""")
    print("----")
    print("If your schema differs, see docs/security/CRITICAL_SAME_TEACHER_LEAK.md#backfill-join_code for more details.")
    print("")
    print("✅ Migration complete - P0 multi-period isolation schema ready")


def downgrade():
    """Remove join_code columns from related tables."""

    tables_to_update = [
        {
            'name': 'student_items',
            'indexes': [
                'ix_student_items_join_code',
                'ix_student_items_student_join_code'
            ],
        },
        {
            'name': 'student_insurance',
            'indexes': [
                'ix_student_insurance_join_code',
                'ix_student_insurance_student_join_code'
            ],
        },
        {
            'name': 'hall_pass_logs',
            'indexes': [
                'ix_hall_pass_logs_join_code',
                'ix_hall_pass_logs_student_join_code'
            ],
        },
        {
            'name': 'rent_payments',
            'indexes': [
                'ix_rent_payments_join_code',
                'ix_rent_payments_student_join_code'
            ],
        },
    ]

    column_name = 'join_code'

    for table in reversed(tables_to_update):
        table_name = table['name']
        if not table_exists(table_name):
            print(f"⚠️  Table '{table_name}' does not exist, skipping downgrade steps")
            continue

        for index_name in table['indexes']:
            if index_exists(table_name, index_name):
                op.drop_index(index_name, table_name=table_name)
                print(f"❌ Dropped index {index_name}")

        if column_exists(table_name, column_name):
            op.drop_column(table_name, column_name)
            print(f"❌ Removed {column_name} column from {table_name} table")
