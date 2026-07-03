"""Repoint all legacy identity FKs to users table

Drop student_id columns where seat_id exists, repoint teacher_id FKs from
teachers.id to users.id, delete student_teachers table, collapse
class_memberships admin_id+student_id into single user_id.

This is a clean-DB migration (v2 has no production data). All operations
are destructive and non-reversible in the downgrade — downgrade simply
drops and recreates from scratch.

Requires: All ORM FK declarations aligned with this migration.

Revision ID: f1f1f1f1f1f1
Revises: f0f0f0f0f0f0
Create Date: 2026-06-20 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1f1f1f1f1f1'
down_revision = 'f0f0f0f0f0f0'
branch_labels = None
depends_on = None


# --- Idempotency helpers ---

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


def has_foreign_key(table_name, constraint_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return any(fk.get('name') == constraint_name for fk in inspector.get_foreign_keys(table_name))
    except Exception:
        return False

def drop_fks_for_column(table_name, column_name):
    """Drop all FK constraints referencing a column."""
    for fk in get_foreign_keys_by_column(table_name, column_name):
        if fk.get('name'):
            op.drop_constraint(fk['name'], table_name, type_='foreignkey')

def drop_indexes_for_column(table_name, column_name):
    """Drop all indexes that include a column (skips unique-constraint-backed indexes)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    # Collect unique constraint names so we skip their backing indexes
    uc_names = {uc.get('name') for uc in inspector.get_unique_constraints(table_name) if uc.get('name')}
    for idx in inspector.get_indexes(table_name):
        name = idx.get('name')
        if column_name in idx.get('column_names', []) and name and name not in uc_names:
            try:
                op.drop_index(name, table_name=table_name)
            except Exception:
                pass  # Already dropped or constraint-backed

def drop_unique_constraints_for_column(table_name, column_name):
    """Drop unique constraints that include a column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for uc in inspector.get_unique_constraints(table_name):
        if column_name in uc.get('column_names', []) and uc.get('name'):
            op.drop_constraint(uc['name'], table_name, type_='unique')

def safe_drop_column(table_name, column_name):
    """Drop a column and all its FK/index/unique dependencies."""
    if not column_exists(table_name, column_name):
        print(f"  ⚠️  {table_name}.{column_name} already gone, skipping")
        return
    drop_fks_for_column(table_name, column_name)
    drop_unique_constraints_for_column(table_name, column_name)
    drop_indexes_for_column(table_name, column_name)
    op.drop_column(table_name, column_name)
    print(f"  ✅ Dropped {table_name}.{column_name}")

def repoint_teacher_fk(table_name, col='teacher_id'):
    """Drop FK from teachers.id and add FK to users.id for a teacher_id column."""
    if not column_exists(table_name, col):
        print(f"  ⚠️  {table_name}.{col} does not exist, skipping")
        return
    drop_fks_for_column(table_name, col)
    constraint_name = f'fk_{table_name}_{col}_users'
    if not has_foreign_key(table_name, constraint_name):
        op.create_foreign_key(
            constraint_name,
            table_name, 'users',
            [col], ['id'],
            ondelete='CASCADE',
        )
    print(f"  ✅ Repointed {table_name}.{col} → users.id")


def upgrade():
    # ============================================================
    # 1. Drop student_teachers table
    # ============================================================
    if table_exists('student_teachers'):
        op.drop_table('student_teachers')
        print("✅ Dropped student_teachers table")

    # ============================================================
    # 2. Drop student_id columns (seat_id is the canonical anchor)
    # ============================================================
    student_id_tables = [
        'seats',
        'student_blocks',
        'attendance_sessions',
        'seat_attendance_state',
        'tap_events',
        'hall_pass_logs',
        'student_items',
        'rent_payments',
        'rent_waivers',
        'student_insurance',
        'issues',
    ]
    print("\n--- Dropping student_id columns ---")
    for t in student_id_tables:
        safe_drop_column(t, 'student_id')

    # ============================================================
    # 3. Make seat_id NOT NULL where it was nullable
    # ============================================================
    print("\n--- Making seat_id NOT NULL ---")
    seat_not_null_tables = [
        'student_blocks',
        'student_items',
        'rent_waivers',
        'issues',
    ]
    for t in seat_not_null_tables:
        if column_exists(t, 'seat_id'):
            op.alter_column(t, 'seat_id', nullable=False)
            print(f"  ✅ {t}.seat_id → NOT NULL")

    # ============================================================
    # 4. Repoint teacher_id FKs: teachers.id → users.id
    # ============================================================
    print("\n--- Repointing teacher_id FKs to users.id ---")
    teacher_fk_tables = [
        'classes',          # ClassEconomy
        'transactions',
        'store_items',
        'redemption_audit_log',
        'insurance_policies',
        'analytics_snapshots',
        'analytics_events',
        'issues',
    ]
    for t in teacher_fk_tables:
        repoint_teacher_fk(t)

    # Announcement has two teacher FKs
    repoint_teacher_fk('announcements', 'teacher_id')
    repoint_teacher_fk('announcements', 'target_teacher_id')

    # ============================================================
    # 5. Repoint specific renamed columns
    # ============================================================
    print("\n--- Repointing renamed columns ---")

    # ClassEconomy: created_by_admin_id → created_by_user_id
    if column_exists('classes', 'created_by_admin_id'):
        drop_fks_for_column('classes', 'created_by_admin_id')
        drop_indexes_for_column('classes', 'created_by_admin_id')
        op.alter_column('classes', 'created_by_admin_id', new_column_name='created_by_user_id')
        if not has_foreign_key('classes', 'fk_classes_created_by_user_id_users'):
            op.create_foreign_key(
                'fk_classes_created_by_user_id_users',
                'classes', 'users',
                ['created_by_user_id'], ['id'],
                ondelete='SET NULL',
            )
        print("  ✅ classes.created_by_admin_id → created_by_user_id (users.id)")

    # RentWaiver: created_by_teacher_id → created_by_user_id
    if column_exists('rent_waivers', 'created_by_teacher_id'):
        drop_fks_for_column('rent_waivers', 'created_by_teacher_id')
        drop_indexes_for_column('rent_waivers', 'created_by_teacher_id')
        op.alter_column('rent_waivers', 'created_by_teacher_id', new_column_name='created_by_user_id')
        if not has_foreign_key('rent_waivers', 'fk_rent_waivers_created_by_user_id_users'):
            op.create_foreign_key(
                'fk_rent_waivers_created_by_user_id_users',
                'rent_waivers', 'users',
                ['created_by_user_id'], ['id'],
            )
        print("  ✅ rent_waivers.created_by_teacher_id → created_by_user_id (users.id)")

    # TapEvent: deleted_by → repoint to users.id
    if column_exists('tap_events', 'deleted_by'):
        drop_fks_for_column('tap_events', 'deleted_by')
        if not has_foreign_key('tap_events', 'fk_tap_events_deleted_by_users'):
            op.create_foreign_key(
                'fk_tap_events_deleted_by_users',
                'tap_events', 'users',
                ['deleted_by'], ['id'],
                ondelete='SET NULL',
            )
        print("  ✅ tap_events.deleted_by → users.id")

    # ============================================================
    # 6. TeacherCredential: drop teacher_id, keep user_id
    # ============================================================
    print("\n--- TeacherCredential ---")
    safe_drop_column('teacher_credentials', 'teacher_id')
    if column_exists('teacher_credentials', 'user_id'):
        op.alter_column('teacher_credentials', 'user_id', nullable=False)
        print("  ✅ teacher_credentials.user_id → NOT NULL")

    # ============================================================
    # 7. TeacherOnboarding: teacher_id → user_id
    # ============================================================
    print("\n--- TeacherOnboarding ---")
    if column_exists('teacher_onboarding', 'teacher_id'):
        drop_fks_for_column('teacher_onboarding', 'teacher_id')
        drop_indexes_for_column('teacher_onboarding', 'teacher_id')
        drop_unique_constraints_for_column('teacher_onboarding', 'teacher_id')
        op.alter_column('teacher_onboarding', 'teacher_id', new_column_name='user_id')
        if not has_foreign_key('teacher_onboarding', 'fk_teacher_onboarding_user_id_users'):
            op.create_foreign_key(
                'fk_teacher_onboarding_user_id_users',
                'teacher_onboarding', 'users',
                ['user_id'], ['id'],
                ondelete='CASCADE',
            )
        if not index_exists('teacher_onboarding', 'uq_teacher_onboarding_user_id'):
            op.create_unique_constraint('uq_teacher_onboarding_user_id', 'teacher_onboarding', ['user_id'])
        print("  ✅ teacher_onboarding.teacher_id → user_id (users.id)")

    # ============================================================
    # 8. RecoveryRequest: teacher_id → user_id
    # ============================================================
    print("\n--- RecoveryRequest ---")
    if column_exists('recovery_requests', 'teacher_id'):
        drop_fks_for_column('recovery_requests', 'teacher_id')
        drop_indexes_for_column('recovery_requests', 'teacher_id')
        op.alter_column('recovery_requests', 'teacher_id', new_column_name='user_id')
        if not has_foreign_key('recovery_requests', 'fk_recovery_requests_user_id_users'):
            op.create_foreign_key(
                'fk_recovery_requests_user_id_users',
                'recovery_requests', 'users',
                ['user_id'], ['id'],
            )
        print("  ✅ recovery_requests.teacher_id → user_id (users.id)")

    # ============================================================
    # 9. StudentRecoveryCode: student_id → user_id
    # ============================================================
    print("\n--- StudentRecoveryCode ---")
    if column_exists('student_recovery_codes', 'student_id'):
        drop_fks_for_column('student_recovery_codes', 'student_id')
        drop_indexes_for_column('student_recovery_codes', 'student_id')
        op.alter_column('student_recovery_codes', 'student_id', new_column_name='user_id')
        if not has_foreign_key('student_recovery_codes', 'fk_student_recovery_codes_user_id_users'):
            op.create_foreign_key(
                'fk_student_recovery_codes_user_id_users',
                'student_recovery_codes', 'users',
                ['user_id'], ['id'],
            )
        print("  ✅ student_recovery_codes.student_id → user_id (users.id)")

    # ============================================================
    # 10. ClassMembership: collapse admin_id + student_id → user_id
    # ============================================================
    print("\n--- ClassMembership ---")
    if table_exists('class_memberships'):
        if not column_exists('class_memberships', 'user_id'):
            op.add_column('class_memberships', sa.Column('user_id', sa.Integer(), nullable=True))
            print("  ✅ Added class_memberships.user_id")

        safe_drop_column('class_memberships', 'admin_id')
        safe_drop_column('class_memberships', 'student_id')

        if column_exists('class_memberships', 'user_id'):
            op.alter_column('class_memberships', 'user_id', nullable=False)
            if not has_foreign_key('class_memberships', 'fk_class_memberships_user_id_users'):
                op.create_foreign_key(
                    'fk_class_memberships_user_id_users',
                    'class_memberships', 'users',
                    ['user_id'], ['id'],
                    ondelete='CASCADE',
                )
            if not index_exists('class_memberships', 'uq_class_membership_user'):
                op.create_unique_constraint(
                    'uq_class_membership_user',
                    'class_memberships',
                    ['class_id', 'user_id'],
                )
            if not index_exists('class_memberships', 'ix_class_memberships_user_id'):
                op.create_index('ix_class_memberships_user_id', 'class_memberships', ['user_id'])
            print("  ✅ class_memberships → single user_id (users.id)")
    else:
        print("  ⚠️  class_memberships missing, skipping")

    # ============================================================
    # 11. UserReport: _student_id → seat_id (if not already done)
    # ============================================================
    print("\n--- UserReport ---")
    if column_exists('user_reports', '_student_id'):
        drop_fks_for_column('user_reports', '_student_id')
        drop_indexes_for_column('user_reports', '_student_id')
        op.drop_column('user_reports', '_student_id')
        print("  ✅ Dropped user_reports._student_id")
    if not column_exists('user_reports', 'seat_id'):
        op.add_column('user_reports', sa.Column('seat_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_user_reports_seat_id_seats',
            'user_reports', 'seats',
            ['seat_id'], ['id'],
            ondelete='SET NULL',
        )
        op.create_index('ix_user_reports_seat_id', 'user_reports', ['seat_id'])
        print("  ✅ Added user_reports.seat_id → seats.id")

    # ============================================================
    # 12. Fix Issue index: student_id → seat_id
    # ============================================================
    print("\n--- Issue indexes ---")
    if index_exists('issues', 'ix_issues_student_status'):
        op.drop_index('ix_issues_student_status', table_name='issues')
    if not index_exists('issues', 'ix_issues_seat_status'):
        op.create_index('ix_issues_seat_status', 'issues', ['seat_id', 'status'])
        print("  ✅ Created ix_issues_seat_status")

    print("\n✅ Migration complete")


def downgrade():
    # Clean DB, no real downgrade needed. Drop everything and let
    # create_all rebuild if needed.
    raise NotImplementedError(
        "This migration is not reversible. Drop and recreate the database."
    )
