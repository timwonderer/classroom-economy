"""add demo_students table

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2025-11-23 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7g8h9'
down_revision = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    # Create demo_students table
    op.create_table('demo_students',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('config_checking_balance', sa.Float(), nullable=True),
        sa.Column('config_savings_balance', sa.Float(), nullable=True),
        sa.Column('config_hall_passes', sa.Integer(), nullable=True),
        sa.Column('config_insurance_plan', sa.String(length=50), nullable=True),
        sa.Column('config_is_rent_enabled', sa.Boolean(), nullable=True),
        sa.Column('config_period', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )


def downgrade():
    # Drop demo_students table
    op.drop_table('demo_students')
