"""Remove block and is_enabled from rent_settings; class_id is unique canonical scope

Revision ID: 677a7c3b06e0
Revises: 1c6893a8b375
Create Date: 2026-07-09 05:30:00.000000

block was a display-metadata field used for per-period rent overrides — not a valid
scoping key. class_id is the sole canonical scope. Removing block collapses per-block
rent settings to one row per class.

is_enabled is redundant: the existence of a rent_settings row already signals that
rent is configured for the class. Removing is_enabled; callers check `if rent_settings`.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '677a7c3b06e0'
down_revision = '1c6893a8b375'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return column_name in [col['name'] for col in inspector.get_columns(table_name)]
    except Exception:
        return False


def index_exists(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return index_name in [idx['name'] for idx in inspector.get_indexes(table_name)]
    except Exception:
        return False


def upgrade():
    # Deduplicate: if multiple rows per class_id exist, keep the most recent one.
    # This can happen if per-block rows were created before this migration.
    rent_settings = sa.table(
        'rent_settings',
        sa.column('id', sa.Integer()),
        sa.column('class_id', sa.Integer()),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(rent_settings.c.id, rent_settings.c.class_id).order_by(
            rent_settings.c.class_id,
            rent_settings.c.id.desc(),
        )
    ).fetchall()
    seen_class_ids = set()
    for row in rows:
        if row.class_id in seen_class_ids:
            conn.execute(sa.delete(rent_settings).where(rent_settings.c.id == row.id))
        else:
            seen_class_ids.add(row.class_id)

    # Make class_id unique now that duplicates are removed
    if index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.drop_index('ix_rent_settings_class_id', table_name='rent_settings')
    if not index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.create_index('ix_rent_settings_class_id', 'rent_settings', ['class_id'], unique=True)

    # Drop is_enabled — row existence is the gate
    if column_exists('rent_settings', 'is_enabled'):
        op.drop_column('rent_settings', 'is_enabled')

    # Drop block — class_id is the sole canonical scope
    if column_exists('rent_settings', 'block'):
        op.drop_column('rent_settings', 'block')


def downgrade():
    if not column_exists('rent_settings', 'block'):
        op.add_column('rent_settings', sa.Column('block', sa.String(length=10), nullable=True))
    if not column_exists('rent_settings', 'is_enabled'):
        op.add_column('rent_settings', sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'))
    # Restore non-unique index
    if index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.drop_index('ix_rent_settings_class_id', table_name='rent_settings')
    if not index_exists('rent_settings', 'ix_rent_settings_class_id'):
        op.create_index('ix_rent_settings_class_id', 'rent_settings', ['class_id'], unique=False)
