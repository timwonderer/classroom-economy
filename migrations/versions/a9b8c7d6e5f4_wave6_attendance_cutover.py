"""Wave 6: Add soft-delete to attendance_sessions, drop source_tap_event_id, drop tap_events table

Revision ID: a9b8c7d6e5f4
Revises: d1e2f3a4b5c6
Create Date: 2026-06-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a9b8c7d6e5f4'
down_revision = 'd1e2f3a4b5c6'
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


def upgrade():
    # 1. Add soft-delete columns to attendance_sessions
    if not column_exists('attendance_sessions', 'is_deleted'):
        op.add_column('attendance_sessions', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
        op.create_index('ix_attendance_sessions_is_deleted', 'attendance_sessions', ['is_deleted'])

    if not column_exists('attendance_sessions', 'deleted_at'):
        op.add_column('attendance_sessions', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    if not column_exists('attendance_sessions', 'deleted_by_seat_id'):
        op.add_column('attendance_sessions', sa.Column('deleted_by_seat_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_attendance_sessions_deleted_by_seat_id',
            'attendance_sessions', 'seats',
            ['deleted_by_seat_id'], ['id'],
            ondelete='SET NULL'
        )

    # 2. Drop source_tap_event_id FK (if still a FK) then drop the column
    if column_exists('attendance_sessions', 'source_tap_event_id'):
        fks = get_foreign_keys_by_column('attendance_sessions', 'source_tap_event_id')
        for fk in fks:
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'attendance_sessions', type_='foreignkey')

        if index_exists('attendance_sessions', 'ix_attendance_sessions_source_tap_event_id'):
            op.drop_index('ix_attendance_sessions_source_tap_event_id', table_name='attendance_sessions')

        op.drop_column('attendance_sessions', 'source_tap_event_id')

    # 3. Drop tap_events table
    if table_exists('tap_events'):
        op.drop_table('tap_events')


def downgrade():
    # 3. Recreate tap_events table
    if not table_exists('tap_events'):
        op.create_table(
            'tap_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=True),
            sa.Column('seat_id', sa.Integer(), sa.ForeignKey('seats.id', ondelete='SET NULL'), nullable=True),
            sa.Column('period', sa.String(10), nullable=False),
            sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.class_id', ondelete='CASCADE'), nullable=True),
            sa.Column('join_code', sa.String(20), nullable=True),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('reason', sa.String(50), nullable=True),
            sa.Column(
                'reason_code',
                sa.Enum('daily_limit', 'auto_switch', name='attendancereasoncode'),
                nullable=True,
            ),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('deleted_by', sa.Integer(), sa.ForeignKey('teachers.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index('ix_tap_events_student_id', 'tap_events', ['student_id'])
        op.create_index('ix_tap_events_seat_id', 'tap_events', ['seat_id'])
        op.create_index('ix_tap_events_class_id', 'tap_events', ['class_id'])
        op.create_index('ix_tap_events_join_code', 'tap_events', ['join_code'])
        op.create_index('ix_tap_events_reason_code', 'tap_events', ['reason_code'])
        op.create_index('ix_tap_events_is_deleted', 'tap_events', ['is_deleted'])
        op.create_index('ix_tap_event_student_period_timestamp', 'tap_events', ['student_id', 'period', 'timestamp'])
        op.create_index('ix_tap_event_seat_period_timestamp', 'tap_events', ['seat_id', 'period', 'timestamp'])

    # 2. Re-add source_tap_event_id
    if not column_exists('attendance_sessions', 'source_tap_event_id'):
        op.add_column('attendance_sessions', sa.Column('source_tap_event_id', sa.Integer(), nullable=True))
        op.create_index('ix_attendance_sessions_source_tap_event_id', 'attendance_sessions', ['source_tap_event_id'])

    # 1. Drop soft-delete columns
    if column_exists('attendance_sessions', 'deleted_by_seat_id'):
        fks = get_foreign_keys_by_column('attendance_sessions', 'deleted_by_seat_id')
        for fk in fks:
            if fk.get('name'):
                op.drop_constraint(fk['name'], 'attendance_sessions', type_='foreignkey')
        op.drop_column('attendance_sessions', 'deleted_by_seat_id')

    if column_exists('attendance_sessions', 'deleted_at'):
        op.drop_column('attendance_sessions', 'deleted_at')

    if column_exists('attendance_sessions', 'is_deleted'):
        if index_exists('attendance_sessions', 'ix_attendance_sessions_is_deleted'):
            op.drop_index('ix_attendance_sessions_is_deleted', table_name='attendance_sessions')
        op.drop_column('attendance_sessions', 'is_deleted')
