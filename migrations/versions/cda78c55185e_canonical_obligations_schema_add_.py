"""Canonical obligations schema: add internal_ref, correlation_id, viewable_at, bill_cycle_id; create bill_cycles table; fix satisfaction uniqueness

Revision ID: cda78c55185e
Revises: 0006
Create Date: 2026-07-24 07:04:16.372841

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

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
    """
    Get foreign key constraints that reference a specific column.
    
    Use this instead of hardcoding FK names in downgrade.
    """
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
# MIGRATION FUNCTIONS
# ============================================================================

# revision identifiers, used by Alembic.
revision = 'cda78c55185e'
down_revision = '9bb0d3678c86'
# Note: This migration follows 9bb0d3678c86 (redemption_events cleanup)
branch_labels = None
depends_on = None


def upgrade():
    # ========================================================================
    # CANONICAL OBLIGATIONS SCHEMA MIGRATION
    # ========================================================================

    # 1. Create bill_cycles table (new canonical table)
    if not table_exists('bill_cycles'):
        op.create_table('bill_cycles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('internal_ref', sa.String(length=200), nullable=False),
        sa.Column('cycle_number', sa.Integer(), nullable=False),
        sa.Column('source_version_id', sa.String(length=200), nullable=True),
        sa.Column('cycle_boundary_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('next_assessment_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('internal_ref', 'cycle_number', name='uq_bill_cycles_ref_cycle')
        )
        op.create_index(op.f('ix_bill_cycles_internal_ref'), 'bill_cycles', ['internal_ref'], unique=False)
        print("✅ Created bill_cycles table")
    else:
        print("⚠️  bill_cycles table already exists, skipping...")

    # 2. Add canonical fields to assessment_events
    if not column_exists('assessment_events', 'internal_ref'):
        op.add_column('assessment_events', sa.Column('internal_ref', sa.String(length=200), nullable=False))
        print("✅ Added internal_ref to assessment_events")
    else:
        print("⚠️  internal_ref already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'correlation_id'):
        op.add_column('assessment_events', sa.Column('correlation_id', sa.String(length=200), nullable=False))
        print("✅ Added correlation_id to assessment_events")
    else:
        print("⚠️  correlation_id already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'viewable_at'):
        op.add_column('assessment_events', sa.Column('viewable_at', sa.DateTime(timezone=True), nullable=True))
        print("✅ Added viewable_at to assessment_events")
    else:
        print("⚠️  viewable_at already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'created_at'):
        op.add_column('assessment_events', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
        print("✅ Added created_at to assessment_events")
    else:
        print("⚠️  created_at already exists on assessment_events, skipping...")

    if not column_exists('assessment_events', 'bill_cycle_id'):
        op.add_column('assessment_events', sa.Column('bill_cycle_id', sa.Integer(), nullable=True))
        print("✅ Added bill_cycle_id to assessment_events")
    else:
        print("⚠️  bill_cycle_id already exists on assessment_events, skipping...")

    # 3. Make amount_snap nullable in assessment_events (per DOM-OBL-001, amounts not stored here)
    if column_exists('assessment_events', 'amount_snap'):
        op.alter_column('assessment_events', 'amount_snap',
                   existing_type=sa.NUMERIC(precision=12, scale=2),
                   nullable=True)
        print("✅ Made amount_snap nullable on assessment_events")

    # 4. Create indexes on canonical fields
    if not index_exists('assessment_events', 'ix_assessment_events_bill_cycle_id'):
        op.create_index(op.f('ix_assessment_events_bill_cycle_id'), 'assessment_events', ['bill_cycle_id'], unique=False)
        print("✅ Created ix_assessment_events_bill_cycle_id")

    if not index_exists('assessment_events', 'ix_assessment_events_correlation_id'):
        op.create_index(op.f('ix_assessment_events_correlation_id'), 'assessment_events', ['correlation_id'], unique=True)
        print("✅ Created ix_assessment_events_correlation_id")

    if not index_exists('assessment_events', 'ix_assessment_events_internal_ref'):
        op.create_index(op.f('ix_assessment_events_internal_ref'), 'assessment_events', ['internal_ref'], unique=False)
        print("✅ Created ix_assessment_events_internal_ref")

    # 5. Create FK from assessment_events to bill_cycles
    if not foreign_key_exists('assessment_events', 'assessment_events_bill_cycle_id_fkey'):
        op.create_foreign_key(None, 'assessment_events', 'bill_cycles', ['bill_cycle_id'], ['id'], ondelete='SET NULL')
        print("✅ Created FK: assessment_events.bill_cycle_id → bill_cycles.id")

    # ========================================================================
    # OBLIGATION SATISFACTION SCHEMA MIGRATION
    # ========================================================================
    # Note: obligation_satisfaction is now optional - may not exist if migration 0006+ skipped creating it
    # All these changes will be skipped if the table doesn't exist (will be handled by migration 0008)

    if table_exists('obligation_satisfaction'):
        # 6. Fix obligation_satisfaction to allow multiple PAYMENT events
        # Remove unique constraint on assessment_id and add it back as non-unique index
        if index_exists('obligation_satisfaction', 'ix_obligation_satisfaction_assessment_id') and \
           'ix_obligation_satisfaction_assessment_id' in [
               idx['name'] for idx in sa.inspect(op.get_bind()).get_indexes('obligation_satisfaction')
               if idx.get('unique')
           ]:
            # The old index is unique; need to drop and recreate as non-unique
            op.drop_index(op.f('ix_obligation_satisfaction_assessment_id'), table_name='obligation_satisfaction')
            op.create_index(op.f('ix_obligation_satisfaction_assessment_id'), 'obligation_satisfaction', ['assessment_id'], unique=False)
            print("✅ Changed ix_obligation_satisfaction_assessment_id from unique to non-unique")

        # 7. Add canonical satisfaction fields
        if not column_exists('obligation_satisfaction', 'ledger_transaction_id'):
            op.add_column('obligation_satisfaction', sa.Column('ledger_transaction_id', sa.Integer(), nullable=True))
            print("✅ Added ledger_transaction_id to obligation_satisfaction")
        else:
            print("⚠️  ledger_transaction_id already exists on obligation_satisfaction, skipping...")

        if not column_exists('obligation_satisfaction', 'occurred_at'):
            op.add_column('obligation_satisfaction', sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False))
            print("✅ Added occurred_at to obligation_satisfaction")
        else:
            print("⚠️  occurred_at already exists on obligation_satisfaction, skipping...")

        if not column_exists('obligation_satisfaction', 'created_at'):
            op.add_column('obligation_satisfaction', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
            print("✅ Added created_at to obligation_satisfaction")
        else:
            print("⚠️  created_at already exists on obligation_satisfaction, skipping...")

        # 8. Remove legacy derived fields (per DOM-OBL-001 Section VIII)
        legacy_cols = ['amount_paid', 'was_late', 'late_fee_charged', 'satisfied_at', 'transaction_id']
        for col_name in legacy_cols:
            if column_exists('obligation_satisfaction', col_name):
                op.drop_column('obligation_satisfaction', col_name)
                print(f"✅ Dropped legacy column {col_name} from obligation_satisfaction")

        # 9. Create/fix indexes on satisfaction table
        if not index_exists('obligation_satisfaction', 'ix_obligation_satisfaction_ledger_transaction_id'):
            op.create_index(op.f('ix_obligation_satisfaction_ledger_transaction_id'), 'obligation_satisfaction', ['ledger_transaction_id'], unique=False)
            print("✅ Created ix_obligation_satisfaction_ledger_transaction_id")

        # 10. Create FK from satisfaction to ledger
        if not foreign_key_exists('obligation_satisfaction', 'obligation_satisfaction_ledger_transaction_id_fkey'):
            op.create_foreign_key(None, 'obligation_satisfaction', 'ledger_transaction', ['ledger_transaction_id'], ['id'], ondelete='SET NULL')
            print("✅ Created FK: obligation_satisfaction.ledger_transaction_id → ledger_transaction.id")
    else:
        print("⏭️  obligation_satisfaction table does not exist (will be handled by migration 0008)")

    # Note: Other Alembic-detected changes are handled separately in other migrations.
    # This migration focuses exclusively on canonical obligations schema evolution.


def downgrade():
    # ========================================================================
    # DOWNGRADE CANONICAL OBLIGATIONS SCHEMA
    # ========================================================================
    print("ℹ️  Downgrading canonical obligations schema...")

    # This is a placeholder downgrade that prints a warning.
    # Full downgrade reversal is complex due to legacy field interdependencies.
    # If you need to downgrade, consider:
    # 1. Restoring from database backup
    # 2. Creating a new reverse migration
    # 3. Manual intervention

    print("⚠️  WARNING: Downgrade of canonical obligations schema is not fully implemented.")
    print("The upgrade added canonical fields (internal_ref, correlation_id, bill_cycles table, etc).")
    print("To fully downgrade, restore from a database backup or create a targeted downgrade migration.")

    # Minimal downgrade: drop new bill_cycles table if it exists
    if table_exists('bill_cycles'):
        op.drop_index(op.f('ix_bill_cycles_internal_ref'), table_name='bill_cycles')
        op.drop_table('bill_cycles')
        print("✅ Dropped bill_cycles table")

    print("⚠️  Downgrade incomplete. Manual database intervention may be required.")
    op.drop_index(op.f('ix_store_purchases_collective_goal_instance_code'), table_name='store_purchases')
    op.create_index(op.f('ix_store_purchases_collective_goal'), 'store_purchases', ['collective_goal_instance_code'], unique=False)
    op.drop_constraint(None, 'store_items', type_='foreignkey')
    op.create_foreign_key(op.f('fk_store_items_teacher_id_users'), 'store_items', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.add_column('seats', sa.Column('block_identifier', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.add_column('seats', sa.Column('block', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.add_column('rent_settings', sa.Column('active_version_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('rent_settings', sa.Column('next_version_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_index(op.f('ix_redemption_events_timestamp'), table_name='redemption_events')
    op.drop_index(op.f('ix_redemption_events_initiated_by_user_id'), table_name='redemption_events')
    op.drop_index(op.f('ix_recovery_requests_user_id'), table_name='recovery_requests')
    op.add_column('payroll_settings', sa.Column('policy_version_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('fk_payroll_settings_policy_version_id'), 'payroll_settings', 'policy_versions', ['policy_version_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_payroll_settings_policy_version_id'), 'payroll_settings', ['policy_version_id'], unique=False)
    op.add_column('obligation_satisfaction', sa.Column('late_fee_charged', sa.NUMERIC(precision=12, scale=2), autoincrement=False, nullable=True))
    op.add_column('obligation_satisfaction', sa.Column('satisfied_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False))
    op.add_column('obligation_satisfaction', sa.Column('amount_paid', sa.NUMERIC(precision=12, scale=2), autoincrement=False, nullable=True))
    op.add_column('obligation_satisfaction', sa.Column('was_late', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.add_column('obligation_satisfaction', sa.Column('transaction_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'obligation_satisfaction', type_='foreignkey')
    op.create_foreign_key(op.f('obligation_satisfaction_transaction_id_fkey'), 'obligation_satisfaction', 'ledger_transaction', ['transaction_id'], ['id'], ondelete='SET NULL')
    op.drop_index(op.f('ix_obligation_satisfaction_ledger_transaction_id'), table_name='obligation_satisfaction')
    op.drop_index('ix_obligation_satisfaction_assessment', table_name='obligation_satisfaction')
    op.drop_index(op.f('ix_obligation_satisfaction_assessment_id'), table_name='obligation_satisfaction')
    op.create_index(op.f('ix_obligation_satisfaction_assessment_id'), 'obligation_satisfaction', ['assessment_id'], unique=True)
    op.create_index(op.f('ix_obligation_satisfaction_transaction_id'), 'obligation_satisfaction', ['transaction_id'], unique=False)
    op.drop_column('obligation_satisfaction', 'created_at')
    op.drop_column('obligation_satisfaction', 'occurred_at')
    op.drop_column('obligation_satisfaction', 'ledger_transaction_id')
    op.drop_constraint(None, 'ledger_transaction', type_='foreignkey')
    op.drop_index(op.f('ix_ledger_transaction_target_seat_id'), table_name='ledger_transaction')
    op.drop_index(op.f('ix_ledger_transaction_actor_seat_id'), table_name='ledger_transaction')
    op.create_index(op.f('uq_insurance_reimbursement_source_policy'), 'ledger_transaction', ['original_transaction_id', 'policy_id'], unique=True, postgresql_where="(((type)::text = 'insurance_reimbursement'::text) AND (original_transaction_id IS NOT NULL) AND (policy_id IS NOT NULL))")
    op.alter_column('ledger_transaction', 'mechanism',
               existing_type=sa.Enum('self', 'teacher', 'system', name='ledger_mechanism_enum'),
               type_=sa.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'self'::character varying"))
    op.add_column('ledger_balance_snapshot', sa.Column('reconciled_through_transaction_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('fk_ledger_balance_snapshot_reconciled_through_transaction_id'), 'ledger_balance_snapshot', 'ledger_transaction', ['reconciled_through_transaction_id'], ['id'])
    op.drop_index('ix_issues_class_status', table_name='issues')
    op.drop_index('ix_issues_actor_status', table_name='issues')
    op.drop_index(op.f('ix_issue_status_history_class_public_id'), table_name='issue_status_history')
    op.drop_index(op.f('ix_issue_resolution_actions_class_public_id'), table_name='issue_resolution_actions')
    op.drop_index('ix_identity_profiles_type_name', table_name='identity_profiles')
    op.create_index(op.f('ix_identity_profiles_type'), 'identity_profiles', ['profile_type'], unique=False)
    op.alter_column('identity_profiles', 'class_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
    op.alter_column('identity_profiles', 'seat_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.add_column('classes', sa.Column('teacher_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('classes', sa.Column('join_code_token', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'classes', type_='foreignkey')
    op.create_foreign_key(op.f('fk_classes_teacher_id_users'), 'classes', 'users', ['teacher_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_classes_user_id'), table_name='classes')
    op.drop_index(op.f('ix_classes_created_by_user_id'), table_name='classes')
    op.create_index(op.f('ix_classes_teacher_id'), 'classes', ['teacher_id'], unique=False)
    op.create_index(op.f('ix_classes_join_code_token'), 'classes', ['join_code_token'], unique=True)
    op.drop_column('classes', 'user_id')
    op.drop_index(op.f('ix_attendance_sessions_target_user_id'), table_name='attendance_sessions')
    op.drop_constraint(None, 'assessment_events', type_='foreignkey')
    op.drop_index(op.f('ix_assessment_events_internal_ref'), table_name='assessment_events')
    op.drop_index(op.f('ix_assessment_events_correlation_id'), table_name='assessment_events')
    op.drop_index(op.f('ix_assessment_events_bill_cycle_id'), table_name='assessment_events')
    op.create_index(op.f('ix_assessment_events_rent_policy_version_id'), 'assessment_events', ['policy_version_id'], unique=False)
    op.alter_column('assessment_events', 'amount_snap',
               existing_type=sa.NUMERIC(precision=12, scale=2),
               nullable=False)
    op.drop_column('assessment_events', 'bill_cycle_id')
    op.drop_column('assessment_events', 'created_at')
    op.drop_column('assessment_events', 'viewable_at')
    op.drop_column('assessment_events', 'correlation_id')
    op.drop_column('assessment_events', 'internal_ref')
    op.add_column('announcements', sa.Column('target_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('announcements', sa.Column('created_by_user_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'announcements', type_='foreignkey')
    op.drop_constraint(None, 'announcements', type_='foreignkey')
    op.create_foreign_key(op.f('fk_announcements_target_teacher_id_users'), 'announcements', 'users', ['target_user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(op.f('fk_announcements_system_admin_id_users'), 'announcements', 'users', ['created_by_user_id'], ['id'], ondelete='CASCADE')
    op.drop_index('ix_announcements_system_admin', table_name='announcements')
    op.create_index(op.f('ix_announcements_system_admin'), 'announcements', ['created_by_user_id', 'is_active'], unique=False)
    op.drop_column('announcements', 'target_teacher_id')
    op.drop_column('announcements', 'system_admin_id')
    op.create_table('job_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('job_events_pkey'))
    )
    op.create_table('interpretation_snapshots',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('interpretation_snapshots_pkey'))
    )
    op.create_table('incident_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('incident_events_pkey'))
    )
    op.create_table('health_check_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('health_check_events_pkey'))
    )
    op.create_table('incident_summary',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('incident_summary_pkey'))
    )
    op.create_table('alert_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('alert_events_pkey'))
    )
    op.create_table('invariant_run_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('invariant_run_events_pkey'))
    )
    op.create_table('operational_events',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('operational_events_pkey'))
    )
    op.create_table('interpretation_annotations',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('interpretation_annotations_pkey'))
    )
    op.drop_index(op.f('ix_bill_cycles_internal_ref'), table_name='bill_cycles')
    op.drop_table('bill_cycles')
    # ### end Alembic commands ###
