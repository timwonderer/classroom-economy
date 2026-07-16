"""Retarget sysadmin FK columns from system_admins to users

Revision ID: 042824e29710
Revises: 10a2b3c4d5e7
Create Date: 2026-06-28 07:07:49.649617

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '042824e29710'
down_revision = '10a2b3c4d5e7'
branch_labels = None
depends_on = None

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """Get FKs for a column (for downgrade without hardcoded names)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

# ============================================================================
# DATA BACKFILL: Map system_admins.id -> users.id via username_lookup_hash
# ============================================================================

_BACKFILL_SQL = """
    UPDATE {table}
    SET {column} = u.id
    FROM system_admins sa
    JOIN users u ON u.username_lookup_hash = sa.username_lookup_hash
    WHERE {table}.{column} = sa.id
      AND u.user_role = 'sysadmin'
"""

_REVERSE_SQL = """
    UPDATE {table}
    SET {column} = sa.id
    FROM users u
    JOIN system_admins sa ON sa.username_lookup_hash = u.username_lookup_hash
    WHERE {table}.{column} = u.id
      AND u.user_role = 'sysadmin'
"""

# ============================================================================
# MIGRATION
# ============================================================================

# FK retargets: (table, column, old_fk_name, old_target, new_target, ondelete)
_FK_CHANGES = [
    ('user_reports', 'reviewed_by_sysadmin_id', 'user_reports_reviewed_by_sysadmin_id_fkey',
     'system_admins', 'users', None),
    ('issues', 'sysadmin_id', 'issues_sysadmin_id_fkey',
     'system_admins', 'users', None),
    ('announcements', 'system_admin_id', 'announcements_system_admin_id_fkey',
     'system_admins', 'users', 'CASCADE'),
]


def upgrade():
    conn = op.get_bind()

    if not table_exists('system_admins'):
        print("  ⚠️  system_admins missing, skipping sysadmin retargets")
        return

    # 1. Retarget 3 FK columns from system_admins.id -> users.id
    for table, column, old_fk, old_target, new_target, ondelete in _FK_CHANGES:
        if not table_exists(table):
            print(f"  ⚠️  {table} missing, skipping")
            continue
        # Backfill data first
        conn.execute(sa.text(_BACKFILL_SQL.format(table=table, column=column)))
        print(f"  ✅ Backfilled {table}.{column} system_admins.id → users.id")

        # Drop old FK if it exists
        if foreign_key_exists(table, old_fk):
            op.drop_constraint(old_fk, table, type_='foreignkey')
            print(f"  ✅ Dropped FK {old_fk}")

        # Create new FK to users.id
        new_fk_name = f'fk_{table}_{column}_users'
        if not foreign_key_exists(table, new_fk_name):
            fk_kwargs = {}
            if ondelete:
                fk_kwargs['ondelete'] = ondelete
            op.create_foreign_key(
                new_fk_name,
                table, 'users', [column], ['id'], **fk_kwargs
            )
            print(f"  ✅ Created FK {new_fk_name} → users.id")

    # 2. Drop system_admin_credentials.sysadmin_id column (user_id already exists)
    if table_exists('system_admin_credentials') and column_exists('system_admin_credentials', 'sysadmin_id'):
        if foreign_key_exists('system_admin_credentials', 'system_admin_credentials_sysadmin_id_fkey'):
            op.drop_constraint('system_admin_credentials_sysadmin_id_fkey',
                               'system_admin_credentials', type_='foreignkey')
            print("  ✅ Dropped FK system_admin_credentials_sysadmin_id_fkey")
        op.drop_column('system_admin_credentials', 'sysadmin_id')
        print("  ✅ Dropped column system_admin_credentials.sysadmin_id")

    # 3. Make system_admin_credentials.user_id NOT NULL (was nullable)
    if table_exists('system_admin_credentials') and column_exists('system_admin_credentials', 'user_id'):
        op.alter_column('system_admin_credentials', 'user_id',
                        existing_type=sa.Integer(),
                        nullable=False)
        print("  ✅ Set system_admin_credentials.user_id NOT NULL")


def downgrade():
    conn = op.get_bind()

    # 1. Restore system_admin_credentials.sysadmin_id
    if table_exists('system_admin_credentials') and column_exists('system_admin_credentials', 'user_id'):
        op.alter_column('system_admin_credentials', 'user_id',
                        existing_type=sa.Integer(),
                        nullable=True)

    if table_exists('system_admin_credentials') and not column_exists('system_admin_credentials', 'sysadmin_id'):
        op.add_column('system_admin_credentials',
                      sa.Column('sysadmin_id', sa.Integer(), nullable=True))

        # Backfill sysadmin_id from users → system_admins
        conn.execute(sa.text("""
            UPDATE system_admin_credentials sac
            SET sysadmin_id = sa.id
            FROM users u
            JOIN system_admins sa ON sa.username_lookup_hash = u.username_lookup_hash
            WHERE sac.user_id = u.id
              AND u.user_role = 'sysadmin'
        """))

        op.alter_column('system_admin_credentials', 'sysadmin_id',
                        existing_type=sa.Integer(),
                        nullable=False)

        if not foreign_key_exists('system_admin_credentials', 'system_admin_credentials_sysadmin_id_fkey'):
            op.create_foreign_key(
                'system_admin_credentials_sysadmin_id_fkey',
                'system_admin_credentials', 'system_admins',
                ['sysadmin_id'], ['id'], ondelete='CASCADE'
            )

    # 2. Reverse FK retargets
    for table, column, old_fk, old_target, new_target, ondelete in _FK_CHANGES:
        new_fk_name = f'fk_{table}_{column}_users'
        # Reverse backfill: users.id -> system_admins.id
        conn.execute(sa.text(_REVERSE_SQL.format(table=table, column=column)))

        # Drop new FK
        fks = get_foreign_keys_by_column(table, column)
        for fk in fks:
            if fk.get('referred_table') == 'users' and fk.get('name'):
                op.drop_constraint(fk['name'], table, type_='foreignkey')

        # Restore old FK to system_admins.id
        if not foreign_key_exists(table, old_fk):
            fk_kwargs = {}
            if ondelete:
                fk_kwargs['ondelete'] = ondelete
            op.create_foreign_key(
                old_fk, table, 'system_admins', [column], ['id'], **fk_kwargs
            )
