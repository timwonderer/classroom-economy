"""Add class_public_id to classes; deidentify issues and DOM-SUP tables per DOM-IDEN-007

Revision ID: 6b2c3d4e5f6a
Revises: 5a1b2c3d4e5f
Create Date: 2026-07-16 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid

# ============================================================================
# IDEMPOTENCY HELPERS (REQUIRED)
# ============================================================================

def table_exists(table_name):
    """Check if a table exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
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
# MIGRATION
# ============================================================================

revision = '6b2c3d4e5f6a'
down_revision = '5a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    # =========================================================================
    # STEP 1: Add class_public_id to classes table
    # =========================================================================
    if not column_exists('classes', 'class_public_id'):
        op.add_column('classes', sa.Column('class_public_id', sa.String(36), nullable=True))
        print("✅ Added classes.class_public_id")

    # Backfill with UUIDs for existing rows
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT class_id FROM classes WHERE class_public_id IS NULL")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE classes SET class_public_id = :pub_id WHERE class_id = :cid"),
            {"pub_id": str(uuid.uuid4()), "cid": row[0]},
        )
    if rows:
        print(f"✅ Backfilled class_public_id for {len(rows)} existing classes")

    # Make NOT NULL and UNIQUE after backfill
    op.alter_column('classes', 'class_public_id', nullable=False)
    if not index_exists('classes', 'ix_classes_class_public_id'):
        op.create_index('ix_classes_class_public_id', 'classes', ['class_public_id'], unique=True)
        print("✅ Created unique index on classes.class_public_id")

    # =========================================================================
    # STEP 2: Issues table — add class_public_id, drop internal identity cols
    # =========================================================================

    # Add class_public_id and reviewer_public_id columns
    if not column_exists('issues', 'class_public_id'):
        op.add_column('issues', sa.Column('class_public_id', sa.String(36), nullable=True, index=True))
        print("✅ Added issues.class_public_id")

    if not column_exists('issues', 'reviewer_public_id'):
        op.add_column('issues', sa.Column('reviewer_public_id', sa.String(64), nullable=True, index=True))
        print("✅ Added issues.reviewer_public_id")

    # Backfill from existing class_id → classes.class_public_id only when the
    # legacy column still exists.
    if column_exists('issues', 'class_id'):
        conn.execute(sa.text("""
            UPDATE issues i
            SET class_public_id = c.class_public_id
            FROM classes c
            WHERE i.class_id = c.class_id
              AND i.class_public_id IS NULL
        """))
        print("✅ Backfilled issues.class_public_id from classes")

    # Drop internal identity FKs and columns
    for fk in get_foreign_keys_by_column('issues', 'user_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'issues', type_='foreignkey')
            print(f"✅ Dropped FK {fk['name']} on issues")

    for fk in get_foreign_keys_by_column('issues', 'seat_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'issues', type_='foreignkey')
            print(f"✅ Dropped FK {fk['name']} on issues")

    for fk in get_foreign_keys_by_column('issues', 'class_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'issues', type_='foreignkey')
            print(f"✅ Dropped FK {fk['name']} on issues")

    # Drop old composite indexes before dropping columns
    if index_exists('issues', 'ix_issues_teacher_status'):
        op.drop_index('ix_issues_teacher_status', table_name='issues')
    if index_exists('issues', 'ix_issues_student_status'):
        op.drop_index('ix_issues_student_status', table_name='issues')

    if column_exists('issues', 'user_id'):
        op.drop_column('issues', 'user_id')
        print("✅ Dropped issues.user_id")

    if column_exists('issues', 'seat_id'):
        op.drop_column('issues', 'seat_id')
        print("✅ Dropped issues.seat_id")

    if column_exists('issues', 'class_id'):
        op.drop_column('issues', 'class_id')
        print("✅ Dropped issues.class_id")

    if column_exists('issues', 'class_label'):
        op.drop_column('issues', 'class_label')
        print("✅ Dropped issues.class_label")

    # =========================================================================
    # STEP 3: issue_status_history — class_id → class_public_id,
    #         changed_by_id → changed_by_public_id
    # =========================================================================
    if not column_exists('issue_status_history', 'class_public_id'):
        op.add_column('issue_status_history', sa.Column('class_public_id', sa.String(36), nullable=True))
        print("✅ Added issue_status_history.class_public_id")

    if not column_exists('issue_status_history', 'changed_by_public_id'):
        op.add_column('issue_status_history', sa.Column('changed_by_public_id', sa.String(64), nullable=True))
        print("✅ Added issue_status_history.changed_by_public_id")

    if column_exists('issue_status_history', 'class_id'):
        conn.execute(sa.text("""
            UPDATE issue_status_history ish
            SET class_public_id = c.class_public_id
            FROM classes c
            WHERE ish.class_id = c.class_id
              AND ish.class_public_id IS NULL
              AND ish.class_id IS NOT NULL
        """))

    # Backfill changed_by_public_id from changed_by_id → seats or users only
    # when the legacy column still exists.
    if column_exists('issue_status_history', 'changed_by_id'):
        conn.execute(sa.text("""
            UPDATE issue_status_history ish
            SET changed_by_public_id = s.public_id
            FROM seats s
            INNER JOIN users u ON s.user_id = u.id
            WHERE ish.changed_by_id = u.id
              AND ish.changed_by_public_id IS NULL
              AND ish.changed_by_id IS NOT NULL
        """))

    for fk in get_foreign_keys_by_column('issue_status_history', 'class_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'issue_status_history', type_='foreignkey')

    if column_exists('issue_status_history', 'class_id'):
        op.drop_column('issue_status_history', 'class_id')
    if column_exists('issue_status_history', 'changed_by_id'):
        op.drop_column('issue_status_history', 'changed_by_id')
    print("✅ Replaced issue_status_history internal identity columns")

    # =========================================================================
    # STEP 4: issue_resolution_actions — class_id → class_public_id,
    #         performed_by_id → performed_by_public_id
    # =========================================================================
    if not column_exists('issue_resolution_actions', 'class_public_id'):
        op.add_column('issue_resolution_actions', sa.Column('class_public_id', sa.String(36), nullable=True))
        print("✅ Added issue_resolution_actions.class_public_id")

    if not column_exists('issue_resolution_actions', 'performed_by_public_id'):
        op.add_column('issue_resolution_actions', sa.Column('performed_by_public_id', sa.String(64), nullable=True))
        print("✅ Added issue_resolution_actions.performed_by_public_id")

    if column_exists('issue_resolution_actions', 'class_id'):
        conn.execute(sa.text("""
            UPDATE issue_resolution_actions ira
            SET class_public_id = c.class_public_id
            FROM classes c
            WHERE ira.class_id = c.class_id
              AND ira.class_public_id IS NULL
              AND ira.class_id IS NOT NULL
        """))

    # Backfill performed_by_public_id from performed_by_id → seats only when
    # the legacy column still exists.
    if column_exists('issue_resolution_actions', 'performed_by_id'):
        conn.execute(sa.text("""
            UPDATE issue_resolution_actions ira
            SET performed_by_public_id = s.public_id
            FROM seats s
            INNER JOIN users u ON s.user_id = u.id
            WHERE ira.performed_by_id = u.id
              AND ira.performed_by_public_id IS NULL
              AND ira.performed_by_id IS NOT NULL
        """))

    for fk in get_foreign_keys_by_column('issue_resolution_actions', 'class_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'issue_resolution_actions', type_='foreignkey')

    if column_exists('issue_resolution_actions', 'class_id'):
        op.drop_column('issue_resolution_actions', 'class_id')
    if column_exists('issue_resolution_actions', 'performed_by_id'):
        op.drop_column('issue_resolution_actions', 'performed_by_id')
    print("✅ Replaced issue_resolution_actions internal identity columns")

    # =========================================================================
    # STEP 5: ticket_correlation_pack — class_id → class_public_id
    # =========================================================================
    if not column_exists('ticket_correlation_pack', 'class_public_id'):
        op.add_column('ticket_correlation_pack', sa.Column('class_public_id', sa.String(36), nullable=True))
        print("✅ Added ticket_correlation_pack.class_public_id")

    if column_exists('ticket_correlation_pack', 'class_id'):
        conn.execute(sa.text("""
            UPDATE ticket_correlation_pack tcp
            SET class_public_id = c.class_public_id
            FROM classes c
            WHERE tcp.class_id = c.class_id
              AND tcp.class_public_id IS NULL
              AND tcp.class_id IS NOT NULL
        """))

    for fk in get_foreign_keys_by_column('ticket_correlation_pack', 'class_id'):
        if fk['name']:
            op.drop_constraint(fk['name'], 'ticket_correlation_pack', type_='foreignkey')

    if column_exists('ticket_correlation_pack', 'class_id'):
        op.drop_column('ticket_correlation_pack', 'class_id')
        print("✅ Replaced ticket_correlation_pack.class_id with class_public_id")

    # =========================================================================
    # STEP 6: Drop user_reports — absorbed into issues pipeline
    # =========================================================================
    if table_exists('user_reports'):
        op.drop_table('user_reports')
        print("✅ Dropped user_reports (absorbed into issues)")

    # =========================================================================
    # STEP 7: announcements — rename target_teacher_id → target_user_id,
    #         system_admin_id → created_by_user_id
    # =========================================================================
    if column_exists('announcements', 'target_teacher_id') and not column_exists('announcements', 'target_user_id'):
        op.alter_column('announcements', 'target_teacher_id', new_column_name='target_user_id')
        print("✅ Renamed announcements.target_teacher_id → target_user_id")

    if column_exists('announcements', 'system_admin_id') and not column_exists('announcements', 'created_by_user_id'):
        op.alter_column('announcements', 'system_admin_id', new_column_name='created_by_user_id')
        print("✅ Renamed announcements.system_admin_id → created_by_user_id")


def downgrade():
    # ---- announcements: restore column names ----
    if column_exists('announcements', 'target_user_id') and not column_exists('announcements', 'target_teacher_id'):
        op.alter_column('announcements', 'target_user_id', new_column_name='target_teacher_id')

    if column_exists('announcements', 'created_by_user_id') and not column_exists('announcements', 'system_admin_id'):
        op.alter_column('announcements', 'created_by_user_id', new_column_name='system_admin_id')

    # ---- user_reports: recreate stub for rollback ----
    if not table_exists('user_reports'):
        op.create_table(
            'user_reports',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('anonymous_code', sa.String(64), nullable=False),
            sa.Column('user_type', sa.String(20), nullable=False),
            sa.Column('class_id', sa.String(36), nullable=True),
            sa.Column('seat_id', sa.Integer(), nullable=True),
            sa.Column('student_id', sa.Integer(), nullable=True),
            sa.Column('report_type', sa.String(20), nullable=False, server_default='bug'),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', sa.String(20), server_default='new'),
            sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        print("✅ Recreated stub user_reports for rollback")

    # ---- ticket_correlation_pack: restore class_id ----
    if not column_exists('ticket_correlation_pack', 'class_id'):
        op.add_column('ticket_correlation_pack', sa.Column('class_id', sa.String(36), nullable=True))
    if column_exists('ticket_correlation_pack', 'class_public_id'):
        op.drop_column('ticket_correlation_pack', 'class_public_id')

    # ---- issue_resolution_actions: restore internal columns ----
    if not column_exists('issue_resolution_actions', 'class_id'):
        op.add_column('issue_resolution_actions', sa.Column('class_id', sa.String(36), nullable=True))
    if not column_exists('issue_resolution_actions', 'performed_by_id'):
        op.add_column('issue_resolution_actions', sa.Column('performed_by_id', sa.Integer(), nullable=True))
    if column_exists('issue_resolution_actions', 'performed_by_public_id'):
        op.drop_column('issue_resolution_actions', 'performed_by_public_id')
    if column_exists('issue_resolution_actions', 'class_public_id'):
        op.drop_column('issue_resolution_actions', 'class_public_id')

    # ---- issue_status_history: restore internal columns ----
    if not column_exists('issue_status_history', 'class_id'):
        op.add_column('issue_status_history', sa.Column('class_id', sa.String(36), nullable=True))
    if not column_exists('issue_status_history', 'changed_by_id'):
        op.add_column('issue_status_history', sa.Column('changed_by_id', sa.Integer(), nullable=True))
    if column_exists('issue_status_history', 'changed_by_public_id'):
        op.drop_column('issue_status_history', 'changed_by_public_id')
    if column_exists('issue_status_history', 'class_public_id'):
        op.drop_column('issue_status_history', 'class_public_id')

    # ---- issues: restore internal identity columns ----
    if not column_exists('issues', 'user_id'):
        op.add_column('issues', sa.Column('user_id', sa.Integer(), nullable=True))
    if not column_exists('issues', 'seat_id'):
        op.add_column('issues', sa.Column('seat_id', sa.Integer(), nullable=True))
    if not column_exists('issues', 'class_id'):
        op.add_column('issues', sa.Column('class_id', sa.String(36), nullable=True))
    if not column_exists('issues', 'class_label'):
        op.add_column('issues', sa.Column('class_label', sa.String(50), nullable=True))
    if column_exists('issues', 'reviewer_public_id'):
        op.drop_column('issues', 'reviewer_public_id')
    if column_exists('issues', 'class_public_id'):
        op.drop_column('issues', 'class_public_id')

    # ---- classes: drop class_public_id ----
    if index_exists('classes', 'ix_classes_class_public_id'):
        op.drop_index('ix_classes_class_public_id', table_name='classes')
    if column_exists('classes', 'class_public_id'):
        op.drop_column('classes', 'class_public_id')
