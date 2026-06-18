"""Replace obligation reversal user FK with seat FK.

Obligation reversals are authored by the teacher seat that owns the class scope.
This migration backfills the canonical teacher seat from each assessment's class,
then drops the legacy user FK so deleted users can no longer null out history.

Revision ID: 2b3c4d5e6f70
Revises: 0008a1b2c3d4
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa

revision = '2b3c4d5e6f70'
down_revision = '0008a1b2c3d4'
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
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def get_foreign_keys_by_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []


def _backfill_reversed_by_seat_id():
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE obligation_reversal
        SET reversed_by_seat_id = (
            SELECT seats.id
            FROM assessment_events assessment
            JOIN seats
              ON seats.class_id = assessment.class_id
             AND seats.role = 'teacher'
            WHERE assessment.id = obligation_reversal.assessment_id
            ORDER BY seats.id ASC
            LIMIT 1
        )
        WHERE reversed_by_seat_id IS NULL
    """))
    remaining = conn.execute(sa.text(
        "SELECT COUNT(*) FROM obligation_reversal WHERE reversed_by_seat_id IS NULL"
    )).scalar()
    if remaining:
        raise RuntimeError(
            f"Unable to backfill {remaining} obligation_reversal row(s) with a teacher seat id."
        )


def _backfill_reversed_by_user_id():
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE obligation_reversal
        SET reversed_by_user_id = (
            SELECT seats.user_id
            FROM seats
            WHERE seats.id = obligation_reversal.reversed_by_seat_id
            LIMIT 1
        )
        WHERE reversed_by_user_id IS NULL
    """))


def upgrade():
    if not table_exists('obligation_reversal'):
        return

    if not column_exists('obligation_reversal', 'reversed_by_seat_id'):
        op.add_column(
            'obligation_reversal',
            sa.Column('reversed_by_seat_id', sa.Integer(), nullable=True),
        )

    _backfill_reversed_by_seat_id()

    for fk in get_foreign_keys_by_column('obligation_reversal', 'reversed_by_user_id'):
        if fk.get('name'):
            op.drop_constraint(fk['name'], 'obligation_reversal', type_='foreignkey')

    if column_exists('obligation_reversal', 'reversed_by_user_id'):
        op.drop_column('obligation_reversal', 'reversed_by_user_id')

    if not get_foreign_keys_by_column('obligation_reversal', 'reversed_by_seat_id'):
        op.create_foreign_key(
            'fk_obligation_reversal_reversed_by_seat',
            'obligation_reversal',
            'seats',
            ['reversed_by_seat_id'],
            ['id'],
            ondelete='CASCADE',
        )

    if not index_exists('obligation_reversal', 'ix_obligation_reversal_reversed_by_seat_id'):
        op.create_index(
            'ix_obligation_reversal_reversed_by_seat_id',
            'obligation_reversal',
            ['reversed_by_seat_id'],
        )

    op.alter_column(
        'obligation_reversal',
        'reversed_by_seat_id',
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade():
    if not table_exists('obligation_reversal'):
        return

    if not column_exists('obligation_reversal', 'reversed_by_user_id'):
        op.add_column(
            'obligation_reversal',
            sa.Column('reversed_by_user_id', sa.Integer(), nullable=True),
        )

    _backfill_reversed_by_user_id()

    for fk in get_foreign_keys_by_column('obligation_reversal', 'reversed_by_seat_id'):
        if fk.get('name'):
            op.drop_constraint(fk['name'], 'obligation_reversal', type_='foreignkey')

    if column_exists('obligation_reversal', 'reversed_by_seat_id'):
        op.drop_column('obligation_reversal', 'reversed_by_seat_id')

    if not get_foreign_keys_by_column('obligation_reversal', 'reversed_by_user_id'):
        op.create_foreign_key(
            'fk_obligation_reversal_reversed_by_user',
            'obligation_reversal',
            'users',
            ['reversed_by_user_id'],
            ['id'],
            ondelete='SET NULL',
        )

    if not index_exists('obligation_reversal', 'ix_obligation_reversal_reversed_by_user_id'):
        op.create_index(
            'ix_obligation_reversal_reversed_by_user_id',
            'obligation_reversal',
            ['reversed_by_user_id'],
        )
