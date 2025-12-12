"""Add student verification for teacher account recovery

Revision ID: dd4ee5ff6aa7
Revises: cc3dd4ee5ff6
Create Date: 2025-12-12

This migration adds student-verified account recovery for teachers.
Recovery requests expire after 5 days and require students to verify
with their passphrase before generating recovery codes.

Security features:
- Teacher initiates with student usernames + DOB sum
- Students get notification banner in their account
- Students must authenticate with passphrase to generate code
- Each student gets unique 6-digit code
- Teacher collects all codes to complete recovery
- 5-day expiration window

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd4ee5ff6aa7'
down_revision = 'cc3dd4ee5ff6'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade():
    status_enum = sa.Enum('pending', 'verified', 'expired', 'cancelled', name='recovery_request_status_enum')

    # Create recovery_requests table
    if not table_exists('recovery_requests'):
        op.create_table('recovery_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('admin_id', sa.Integer(), nullable=False),
            sa.Column('dob_sum', sa.Integer(), nullable=False),
            sa.Column('status', status_enum, nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_recovery_requests_admin_id'), 'recovery_requests', ['admin_id'], unique=False)

    # Create student_recovery_codes table
    if not table_exists('student_recovery_codes'):
        op.create_table('student_recovery_codes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('recovery_request_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('code_hash', sa.String(length=64), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('notified_at', sa.DateTime(), nullable=False),
            sa.Column('dismissed', sa.Boolean(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['recovery_request_id'], ['recovery_requests.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_student_recovery_codes_recovery_request_id'), 'student_recovery_codes', ['recovery_request_id'], unique=False)
        op.create_index(op.f('ix_student_recovery_codes_student_id'), 'student_recovery_codes', ['student_id'], unique=False)


def downgrade():
    status_enum = sa.Enum('pending', 'verified', 'expired', 'cancelled', name='recovery_request_status_enum')

    if table_exists('student_recovery_codes'):
        op.drop_index(op.f('ix_student_recovery_codes_student_id'), table_name='student_recovery_codes')
        op.drop_index(op.f('ix_student_recovery_codes_recovery_request_id'), table_name='student_recovery_codes')
        op.drop_table('student_recovery_codes')

    if table_exists('recovery_requests'):
        op.drop_index(op.f('ix_recovery_requests_admin_id'), table_name='recovery_requests')
        op.drop_table('recovery_requests')

    status_enum.drop(op.get_bind(), checkfirst=True)
