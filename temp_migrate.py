from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_sysadmin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_sysadmin_id'], ['system_admins.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_announcements_is_active'), 'announcements', ['is_active'], unique=False)

    op.create_table('announcement_dismissals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('announcement_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_type', sa.String(length=20), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['announcement_id'], ['announcements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('announcement_id', 'user_id', 'user_type', name='uq_announcement_dismissal_user')
    )
    op.create_index(op.f('ix_announcement_dismissals_announcement_id'), 'announcement_dismissals', ['announcement_id'], unique=False)
    op.create_index(op.f('ix_announcement_dismissals_user_id'), 'announcement_dismissals', ['user_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_announcement_dismissals_user_id'), table_name='announcement_dismissals')
    op.drop_index(op.f('ix_announcement_dismissals_announcement_id'), table_name='announcement_dismissals')
    op.drop_table('announcement_dismissals')
    op.drop_index(op.f('ix_announcements_is_active'), table_name='announcements')
    op.drop_table('announcements')
