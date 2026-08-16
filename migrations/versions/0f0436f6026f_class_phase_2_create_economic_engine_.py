"""CLASS Phase 2: Create economic_engine table, migrate to immutable versioning, restructure class_features

Revision ID: 0f0436f6026f
Revises: 3a69db4907b4
Create Date: 2026-08-08 23:05:20.750018

"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

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
    """Check if a foreign key constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        fks = [fk['name'] for fk in inspector.get_foreign_keys(table_name)]
        return fk_name in fks
    except Exception:
        return False

def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        constraints = [c['name'] for c in inspector.get_unique_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False

def get_foreign_keys_by_column(table_name, column_name):
    """Get foreign key constraints that reference a specific column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    try:
        return [
            fk for fk in inspector.get_foreign_keys(table_name)
            if column_name in fk['constrained_columns']
        ]
    except Exception:
        return []

# revision identifiers, used by Alembic.
revision = '0f0436f6026f'
down_revision = '3a69db4907b4'
branch_labels = None
depends_on = None


def upgrade():
    print("=" * 80)
    print("CLASS Phase 2: Persistence Reconstruction")
    print("=" * 80)

    # Get database connection once at start (available for all steps)
    conn = op.get_bind()

    # ==========================================================================
    # STEP 1: Create economic_engine table (immutable versioning)
    # ==========================================================================
    if not table_exists('economic_engine'):
        op.create_table('economic_engine',
            sa.Column('economic_version_id', sa.String(length=36), nullable=False),
            sa.Column('class_id', sa.String(length=36), nullable=False),
            sa.Column('previous_version_id', sa.String(length=36), nullable=True),
            sa.Column('expected_weekly_hours', sa.Float(), nullable=True),
            sa.Column('interest_rate', sa.Numeric(precision=8, scale=6), nullable=True),
            sa.Column('interest_calculation_type', sa.String(length=20), nullable=True),
            sa.Column('compound_frequency', sa.String(length=20), nullable=True),
            sa.Column('interest_accrual_frequency', sa.String(length=20), nullable=True),
            sa.Column('interest_payout_frequency', sa.String(length=20), nullable=True),
            sa.Column('economy_policy_mode', sa.String(length=20), server_default='default', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("economy_policy_mode IN ('tight', 'default', 'comfortable')", name='ck_economic_engine_mode'),
            sa.CheckConstraint('expected_weekly_hours IS NULL OR expected_weekly_hours > 0', name='ck_economic_engine_hours'),
            sa.CheckConstraint('interest_rate IS NULL OR (interest_rate >= 0 AND interest_rate <= 1.0)', name='ck_economic_engine_rate'),
            sa.CheckConstraint("interest_calculation_type IS NULL OR interest_calculation_type IN ('simple', 'compound')", name='ck_economic_engine_calc_type'),
            sa.CheckConstraint("compound_frequency IS NULL OR compound_frequency IN ('daily', 'weekly', 'monthly')", name='ck_economic_engine_compound_freq'),
            sa.CheckConstraint("interest_accrual_frequency IS NULL OR interest_accrual_frequency IN ('daily', 'weekly', 'monthly')", name='ck_economic_engine_accrual_freq'),
            sa.CheckConstraint("interest_payout_frequency IS NULL OR interest_payout_frequency IN ('weekly', 'monthly')", name='ck_economic_engine_payout_freq'),
            sa.ForeignKeyConstraint(['class_id'], ['classes.class_id'], ondelete='CASCADE', name='fk_economic_engine_class_id'),
            sa.ForeignKeyConstraint(['previous_version_id'], ['economic_engine.economic_version_id'], ondelete='RESTRICT', name='fk_economic_engine_previous_version_id'),
            sa.PrimaryKeyConstraint('economic_version_id')
        )
        if not index_exists('economic_engine', 'ix_economic_engine_class_id'):
            op.create_index('ix_economic_engine_class_id', 'economic_engine', ['class_id'], unique=False)
        if not index_exists('economic_engine', 'ix_economic_engine_class_version'):
            op.create_index('ix_economic_engine_class_version', 'economic_engine', ['class_id', 'created_at'], unique=False)
        if not index_exists('economic_engine', 'ix_economic_engine_previous_version_id'):
            op.create_index('ix_economic_engine_previous_version_id', 'economic_engine', ['previous_version_id'], unique=False)
        print("✅ Created economic_engine table")
    else:
        print("⚠️  Table 'economic_engine' already exists, skipping creation...")

    # ==========================================================================
    # STEP 2: Migrate data from feature_settings + payroll_settings + banking_settings
    # ==========================================================================
    if table_exists('feature_settings') and table_exists('economic_engine'):
        print("\n📊 Migrating configuration data to economic_engine...")

        # `payroll_settings.expected_weekly_hours` was later moved to `economic_engine`
        # itself (see migration a4e8f19d7c31). Older schemas may still carry the column
        # (backfill it if present); newer schemas created via the bootstrap from current
        # models will not have it (select NULL in that case).
        ps_hours_expr = (
            "ps.expected_weekly_hours"
            if column_exists('payroll_settings', 'expected_weekly_hours')
            else "NULL::float"
        )

        # Query existing configuration from legacy tables
        rows_to_insert = conn.execute(text(f"""
            SELECT
                fs.class_id,
                {ps_hours_expr} AS expected_weekly_hours,
                bs.savings_apy,
                bs.interest_calculation_type,
                bs.compound_frequency,
                bs.interest_schedule_type,
                fs.economy_policy_mode,
                fs.created_at
            FROM feature_settings fs
            LEFT JOIN payroll_settings ps ON fs.class_id = ps.class_id AND ps.block IS NULL
            LEFT JOIN banking_settings bs ON fs.class_id = bs.class_id AND bs.block IS NULL
            WHERE NOT EXISTS (SELECT 1 FROM economic_engine WHERE economic_engine.class_id = fs.class_id)
        """)).fetchall()

        inserted_count = 0
        for row in rows_to_insert:
            class_id, hours, rate, calc_type, compound_freq, payout_freq, mode, created_at = row
            version_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO economic_engine
                (economic_version_id, class_id, previous_version_id, expected_weekly_hours, interest_rate,
                 interest_calculation_type, compound_frequency, interest_accrual_frequency, interest_payout_frequency,
                 economy_policy_mode, created_at)
                VALUES (:version_id, :class_id, NULL, :hours, :rate, :calc_type, :compound_freq, NULL, :payout_freq, :mode, :created_at)
            """), {
                'version_id': version_id,
                'class_id': class_id,
                'hours': hours,  # NULL if not configured; preserved as-is
                'rate': rate,  # NULL if not configured; preserved as-is
                'calc_type': calc_type,
                'compound_freq': compound_freq,
                'payout_freq': payout_freq,  # banking_settings.interest_schedule_type; NULL if not configured
                'mode': mode,
                'created_at': created_at
            })
            inserted_count += 1

        print(f"   ✅ Inserted {inserted_count} initial economic versions")
        print("   ℹ️  NULL configuration fields mean 'not specified' (teacher did not configure)")
        print("   ℹ️  Runtime must fail explicitly if consuming unconfigured field")
    else:
        print("⚠️  feature_settings table not found; skipping data migration")

    # ==========================================================================
    # STEP 3: Restructure class_features for append-only timeline
    # ==========================================================================
    print("\n🔄 Restructuring class_features for append-only timeline...")

    if table_exists('class_features'):
        # 3.1: Rename feature_name → feature
        if column_exists('class_features', 'feature_name') and not column_exists('class_features', 'feature'):
            with op.batch_alter_table('class_features', schema=None) as batch_op:
                batch_op.alter_column('feature_name', new_column_name='feature')
            print("   ✅ Renamed feature_name → feature")

        # 3.2: Add economic_version_id column
        if not column_exists('class_features', 'economic_version_id'):
            with op.batch_alter_table('class_features', schema=None) as batch_op:
                batch_op.add_column(sa.Column('economic_version_id', sa.String(36), nullable=True))
            if not foreign_key_exists('class_features', 'fk_class_features_economic_version_id'):
                op.create_foreign_key('fk_class_features_economic_version_id', 'class_features', 'economic_engine', ['economic_version_id'], ['economic_version_id'], ondelete='RESTRICT')
            print("   ✅ Added economic_version_id column")

        # 3.3: Add effective_at column
        if not column_exists('class_features', 'effective_at'):
            with op.batch_alter_table('class_features', schema=None) as batch_op:
                batch_op.add_column(sa.Column('effective_at', sa.DateTime(timezone=True), nullable=True))
            # Backfill: assume existing rows were immediately activated at created_at
            conn.execute(text("UPDATE class_features SET effective_at = created_at WHERE effective_at IS NULL"))
            # Make NOT NULL
            with op.batch_alter_table('class_features', schema=None) as batch_op:
                batch_op.alter_column('effective_at', nullable=False)
            if not index_exists('class_features', 'ix_class_features_effective_at'):
                op.create_index('ix_class_features_effective_at', 'class_features', ['effective_at'])
            print("   ✅ Added effective_at column (backfilled from created_at)")

        # 3.4: Drop old UNIQUE(class_id, feature_name) constraint
        if constraint_exists('class_features', 'uq_class_features_class_feature'):
            with op.batch_alter_table('class_features', schema=None) as batch_op:
                batch_op.drop_constraint('uq_class_features_class_feature', type_='unique')
            print("   ✅ Dropped old UNIQUE(class_id, feature) constraint")

        # 3.5: Remove surrogate id column (deferred to Phase 2b due to complexity)
        # Note: Dropping the PK requires table recreation; defer to Phase 2b migration
        if column_exists('class_features', 'id'):
            print("   ⚠️  Note: Remove id surrogate key in Phase 2b (requires table recreation)")
    else:
        print("⚠️  class_features table not found; skipping restructuring")

    # ==========================================================================
    # STEP 4: Update classes table (rename user_id → teacher_user_id, remove columns)
    # ==========================================================================
    print("\n📝 Updating classes table...")

    if table_exists('classes'):
        # 4.1: Rename user_id → teacher_user_id
        if column_exists('classes', 'user_id'):
            if not column_exists('classes', 'teacher_user_id'):
                # First, copy data
                conn.execute(text("ALTER TABLE classes ADD COLUMN teacher_user_id INTEGER"))
                conn.execute(text("UPDATE classes SET teacher_user_id = user_id WHERE teacher_user_id IS NULL"))

                # Validate backfill: ensure no NULL teacher_user_id remains (class ownership is mandatory)
                null_owner_count = conn.execute(
                    text("SELECT COUNT(*) FROM classes WHERE teacher_user_id IS NULL")
                ).scalar()
                if null_owner_count > 0:
                    raise RuntimeError(
                        f"Backfill failed: {null_owner_count} classes have NULL teacher_user_id. "
                        "Classes must have an owner (teacher_user_id is NOT NULL). "
                        "Verify user_id backfill completed successfully before retrying."
                    )
                print(f"   ✅ Backfill verified: all {conn.execute(text('SELECT COUNT(*) FROM classes')).scalar()} classes have teacher_user_id")

                # Drop old FK and column
                for fk in get_foreign_keys_by_column('classes', 'user_id'):
                    op.drop_constraint(fk['name'], 'classes', type_='foreignkey')

                # Enforce NOT NULL constraint before dropping user_id
                with op.batch_alter_table('classes', schema=None) as batch_op:
                    # Alter teacher_user_id to NOT NULL (mandatory class ownership)
                    batch_op.alter_column('teacher_user_id', nullable=False)
                    # Then drop the old user_id column
                    batch_op.drop_column('user_id')
                print("   ✅ Set teacher_user_id to NOT NULL (mandatory class ownership)")

                # Add new FK
                op.create_foreign_key('fk_classes_teacher_user_id', 'classes', 'users', ['teacher_user_id'], ['id'], ondelete='CASCADE')
                if not index_exists('classes', 'ix_classes_teacher_user_id'):
                    op.create_index('ix_classes_teacher_user_id', 'classes', ['teacher_user_id'])
                print("   ✅ Renamed user_id → teacher_user_id with FK (NOT NULL)")
            else:
                # teacher_user_id already exists, just drop user_id if it exists
                for fk in get_foreign_keys_by_column('classes', 'user_id'):
                    op.drop_constraint(fk['name'], 'classes', type_='foreignkey')
                with op.batch_alter_table('classes', schema=None) as batch_op:
                    batch_op.drop_column('user_id')
                print("   ✅ Removed redundant user_id column (teacher_user_id already exists)")
        else:
            print("   ℹ️  Column 'user_id' not found (already migrated or created as teacher_user_id)")

        # 4.2: Remove updated_at column
        if column_exists('classes', 'updated_at'):
            with op.batch_alter_table('classes', schema=None) as batch_op:
                batch_op.drop_column('updated_at')
            print("   ✅ Removed updated_at column (ORM metadata, not architectural)")

        # 4.3: Remove created_by_user_id column
        if column_exists('classes', 'created_by_user_id'):
            # Drop FK first
            for fk in get_foreign_keys_by_column('classes', 'created_by_user_id'):
                op.drop_constraint(fk['name'], 'classes', type_='foreignkey')

            with op.batch_alter_table('classes', schema=None) as batch_op:
                batch_op.drop_column('created_by_user_id')
            print("   ✅ Removed created_by_user_id column (redundant; teacher_user_id is sole owner)")
    else:
        print("⚠️  classes table not found; skipping updates")

    # ==========================================================================
    # STEP 5: Drop feature_settings table (DEFERRED - consumers must migrate first)
    # ==========================================================================
    print("\n⏳ Cleanup deferred: feature_settings still referenced by runtime code")
    print("   Consumers (economy_rebalance.py, economy_policy.py, routes) must migrate first.")
    print("   After consumer migration complete: feature_settings will be dropped in Phase A follow-up.")

    # NOTE: DO NOT DROP feature_settings yet. Runtime code still queries:
    #   - app/utils/economy_rebalance.py: FeatureSettings.query
    #   - app/utils/economy_policy.py: FeatureSettings.query.filter_by(), FeatureSettings()
    #   - app/routes/admin.py: get_admin_feature_settings_for_class_id()
    #   - app/routes/student.py: get_feature_settings_for_student()
    #
    # Drop will be executed after Phase C (route migration) completes.
    # See: Phase A Step 4-5 in remediation plan

    print("\n" + "=" * 80)
    print("✅ CLASS Phase 2 Migration Complete")
    print("=" * 80)


def downgrade():
    print("=" * 80)
    print("CLASS Phase 2 Downgrade")
    print("=" * 80)

    # Phase 2 represents a structural shift that cannot be safely reversed.
    # Downgrade is not supported; raising exception to alert operator.
    raise RuntimeError(
        "Downgrade from Phase 2 is not supported. "
        "Phase 2 represents an immutable architectural shift to event-based economic versioning. "
        "If rollback is truly necessary, restore from database backup instead of downgrade. "
        "Contact ops team for guidance."
    )
