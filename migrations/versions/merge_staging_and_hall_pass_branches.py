"""Merge staging and hall pass branches

Revision ID: merge_001
Revises: 8a4ca17f506f, f5a1e3e4d7c8
Create Date: 2025-11-15 17:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_001'
down_revision = ('8a4ca17f506f', 'f5a1e3e4d7c8')
branch_labels = None
depends_on = None


def upgrade():
    """
    This is a merge migration combining two branches:
    - 8a4ca17f506f: Latest staging (removed cumulative_sec columns)
    - f5a1e3e4d7c8: Hall pass feature (added hall_passes column and hall_pass_logs table)
    
    The hall pass migration already created:
    1. hall_passes column (renamed from passes_left)
    2. hall_pass_logs table
    
    Since the hall pass migration hasn't run on staging yet, we need to apply those changes.
    """
    
    # Check if hall_passes column exists before trying to rename
    # This handles the case where the migration might run in different orders
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('students')]
    
    # Only apply hall pass changes if they haven't been applied yet
    if 'passes_left' in columns and 'hall_passes' not in columns:
        with op.batch_alter_table('students', schema=None) as batch_op:
            batch_op.add_column(sa.Column('hall_passes', sa.Integer(), nullable=True))
        
        # Copy data from passes_left to hall_passes
        op.execute('UPDATE students SET hall_passes = passes_left')
        
        with op.batch_alter_table('students', schema=None) as batch_op:
            batch_op.drop_column('passes_left')
    
    # Create hall_pass_logs table if it doesn't exist
    tables = inspector.get_table_names()
    if 'hall_pass_logs' not in tables:
        op.create_table('hall_pass_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('reason', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('request_time', sa.DateTime(), nullable=False),
            sa.Column('decision_time', sa.DateTime(), nullable=True),
            sa.Column('left_time', sa.DateTime(), nullable=True),
            sa.Column('return_time', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    """
    Downgrade is tricky for merge migrations.
    This will revert the hall pass changes.
    """
    op.drop_table('hall_pass_logs')
    
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('passes_left', sa.Integer(), nullable=True))
    
    op.execute('UPDATE students SET passes_left = hall_passes')
    
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('hall_passes')
