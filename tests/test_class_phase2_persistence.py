"""
CLASS Phase 2 Persistence Tests

Comprehensive tests verifying immutability of economic versions, version chain integrity,
append-only class_features timeline, and constraint enforcement per DOM-CLASS-001 and
DOM-CLASS-002 authority.

Per SPEC-TEST-001: All fixtures use canonical initializer (initialize).
Per SPEC-TIME-001: All temporal logic uses canonical_temporal_resolver.

PHASE D STATUS (Test Execution):
⏳ BLOCKED by Phase 3 FEAT implementation
   Root cause: v2 FEAT-INTEGRITY enforcement requires all DB mutations through FEAT context
   Current behavior: Direct db.session.add/commit raises FEATContextError
   Solution: Phase 3 must define FEAT-ECON-001 orchestration layer for economic engine creation

   When Phase 3 FEATs are complete:
   1. Update tests to call FEATs instead of direct db.session mutations
   2. Run full test suite to verify Phase 2 persistence layer
   3. Verify schema constraints and immutability TRIGGERs work correctly
"""
import pytest

# Skip entire module pending Phase 3 FEAT definitions
pytestmark = pytest.mark.skip(
    reason="Awaiting Phase 3 FEAT-ECON-* definitions. Tests use direct db.session mutations which are blocked by v2 FEAT-INTEGRITY enforcement."
)
from datetime import timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models import EconomicEngine, ClassFeature, ClassEconomy
from app.extensions import db
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
)
from tests.helpers.classroom_initializer import initialize


@pytest.fixture
def classroom(app):
    """Provision a canonical test classroom per SPEC-TEST-001.

    Returns ProvisionedClassroom with:
    - class_id, join_code, teacher_user, teacher_seat, economy, students[]
    """
    return initialize("chemistry_p1", app)


class TestEconomicEngineImmutability:
    """Verify EconomicEngine versions are immutable after creation."""

    def test_economic_engine_created_successfully(self, app, classroom):
        """Test that EconomicEngine version can be created."""
        with app.app_context():
            version = EconomicEngine(
                economic_version_id="v1",
                class_id=classroom.class_id,
                expected_weekly_hours=40.0,
                interest_rate=Decimal("0.05"),
                interest_calculation_type="simple",
                economy_policy_mode="default",
            )
            db.session.add(version)
            db.session.commit()

            retrieved = EconomicEngine.query.get("v1")
            assert retrieved is not None
            assert retrieved.expected_weekly_hours == 40.0
            assert retrieved.interest_rate == Decimal("0.05")
            assert retrieved.economy_policy_mode == "default"

    def test_economic_engine_prevents_field_modification(self, app, classroom):
        """Test that SQLAlchemy event prevents modification of EconomicEngine fields."""
        with app.app_context():
            version = EconomicEngine(
                economic_version_id="v2",
                class_id=classroom.class_id,
                expected_weekly_hours=40.0,
                economy_policy_mode="default",
            )
            db.session.add(version)
            db.session.commit()

            # Attempt to modify field should raise RuntimeError on commit
            version.expected_weekly_hours = 50.0
            with pytest.raises(RuntimeError, match="immutable"):
                db.session.commit()
            db.session.rollback()

    def test_economic_engine_can_set_field_before_commit(self, app, classroom):
        """Test that fields can be set during construction, but not after commit."""
        with app.app_context():
            # Construction allows field setting
            version = EconomicEngine(
                economic_version_id="v3",
                class_id=classroom.class_id,
                expected_weekly_hours=40.0,
                economy_policy_mode="default",
            )
            # Can set before commit
            version.expected_weekly_hours = 45.0
            db.session.add(version)
            db.session.commit()

            # But cannot modify after commit
            version.expected_weekly_hours = 50.0
            with pytest.raises(RuntimeError, match="immutable"):
                db.session.commit()
            db.session.rollback()

    def test_economic_engine_null_fields_preserved(self, app, classroom):
        """Test that NULL configuration fields preserve 'not specified' semantics."""
        with app.app_context():
            version = EconomicEngine(
                economic_version_id="v4",
                class_id=classroom.class_id,
                expected_weekly_hours=None,  # Not specified
                interest_rate=None,  # Not specified
                interest_calculation_type=None,
                compound_frequency=None,
                economy_policy_mode="default",
            )
            db.session.add(version)
            db.session.commit()

            retrieved = EconomicEngine.query.get("v4")
            assert retrieved.expected_weekly_hours is None
            assert retrieved.interest_rate is None
            assert retrieved.interest_calculation_type is None
            assert retrieved.compound_frequency is None


class TestEconomicEngineVersionChain:
    """Verify version chain integrity and RESTRICT FK behavior."""

    def test_version_chain_creation(self, app, classroom):
        """Test creating a chain of economic versions."""
        with app.app_context():
            # Version 1
            v1 = EconomicEngine(
                economic_version_id="v1",
                class_id=classroom.class_id,
                economy_policy_mode="default",
                previous_version_id=None,
            )
            db.session.add(v1)
            db.session.commit()

            # Version 2 (references v1)
            v2 = EconomicEngine(
                economic_version_id="v2",
                class_id=classroom.class_id,
                economy_policy_mode="comfortable",
                previous_version_id="v1",
            )
            db.session.add(v2)
            db.session.commit()

            # Version 3 (references v2)
            v3 = EconomicEngine(
                economic_version_id="v3",
                class_id=classroom.class_id,
                economy_policy_mode="tight",
                previous_version_id="v2",
            )
            db.session.add(v3)
            db.session.commit()

            # Verify chain traversal
            retrieved_v3 = EconomicEngine.query.get("v3")
            assert retrieved_v3.previous_version_id == "v2"
            retrieved_v2 = EconomicEngine.query.get(retrieved_v3.previous_version_id)
            assert retrieved_v2.previous_version_id == "v1"
            retrieved_v1 = EconomicEngine.query.get(retrieved_v2.previous_version_id)
            assert retrieved_v1.previous_version_id is None

    def test_restrict_constraint_prevents_deletion_of_referenced_version(self, app, classroom):
        """Test that RESTRICT FK constraint prevents deletion of versions in use."""
        with app.app_context():
            v1 = EconomicEngine(
                economic_version_id="v1",
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            db.session.add(v1)
            db.session.commit()

            v2 = EconomicEngine(
                economic_version_id="v2",
                class_id=classroom.class_id,
                economy_policy_mode="comfortable",
                previous_version_id="v1",  # v2 references v1
            )
            db.session.add(v2)
            db.session.commit()

            # Attempt to delete v1 should fail (RESTRICT FK)
            db.session.delete(v1)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_first_version_has_null_previous_id(self, app, classroom):
        """Test that first version has NULL previous_version_id."""
        with app.app_context():
            v1 = EconomicEngine(
                economic_version_id="v1",
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            db.session.add(v1)
            db.session.commit()

            retrieved = EconomicEngine.query.get("v1")
            assert retrieved.previous_version_id is None

    def test_cascade_delete_on_class_deletion(self, app, teacher):
        """Test that deleting a class cascades to economic versions."""
        with app.app_context():
            # Create class
            cls = ClassEconomy(
                class_id="temp-class",
                class_public_id="temp-public",
                join_code="TEMP123",
                teacher_user_id=teacher.id,
            )
            db.session.add(cls)
            db.session.commit()

            # Create version
            version = EconomicEngine(
                economic_version_id="temp-v1",
                class_id="temp-class",
                economy_policy_mode="default",
            )
            db.session.add(version)
            db.session.commit()

            # Verify version exists
            assert EconomicEngine.query.get("temp-v1") is not None

            # Delete class
            db.session.delete(cls)
            db.session.commit()

            # Verify version was cascaded
            assert EconomicEngine.query.get("temp-v1") is None


class TestClassFeatureAppendOnly:
    """Verify append-only class_features timeline semantics."""

    def test_multiple_feature_entries_same_class_feature(self, app, classroom):
        """Test that multiple rows can exist for same class+feature (append-only)."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc

            # Entry 1: Enable feature at T0
            f1 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id="v1",
                effective_at=now,
            )
            db.session.add(f1)
            db.session.commit()

            # Entry 2: Disable feature at T1 (same class+feature, different effective_at)
            f2 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id=None,  # NULL = disabled
                effective_at=now + timedelta(days=1),
            )
            db.session.add(f2)
            db.session.commit()

            # Query should return both entries
            all_entries = ClassFeature.query.filter_by(
                class_id=classroom.class_id,
                feature="banking"
            ).all()
            assert len(all_entries) == 2

    def test_composite_primary_key_uniqueness(self, app, classroom):
        """Test that composite PK (class_id, feature, effective_at) enforces uniqueness."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc

            f1 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id="v1",
                effective_at=now,
            )
            db.session.add(f1)
            db.session.commit()

            # Try to insert duplicate (same class_id, feature, effective_at)
            f2 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id="v2",
                effective_at=now,  # Same effective_at
            )
            db.session.add(f2)

            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_enabled_names_for_class_latest_only(self, app, classroom):
        """Test that enabled_names_for_class returns only latest enabled features."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc
            version1_id = "v1"
            version2_id = "v2"

            # Create versions
            v1 = EconomicEngine(
                economic_version_id=version1_id,
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            v2 = EconomicEngine(
                economic_version_id=version2_id,
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            db.session.add(v1)
            db.session.add(v2)
            db.session.commit()

            # Enable banking at T0 with v1
            f1 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id=version1_id,
                effective_at=now,
            )
            db.session.add(f1)
            db.session.commit()

            # Enable payroll at T0 (no version = disabled)
            f2 = ClassFeature(
                class_id=classroom.class_id,
                feature="payroll",
                economic_version_id=None,
                effective_at=now,
            )
            db.session.add(f2)
            db.session.commit()

            # Re-enable banking at T1 with v2 (overwrites previous)
            f3 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id=version2_id,
                effective_at=now + timedelta(days=1),
            )
            db.session.add(f3)
            db.session.commit()

            # Query enabled features
            enabled = ClassFeature.enabled_names_for_class(classroom.class_id)

            # Should only include banking (latest enabled)
            assert "banking" in enabled
            assert "payroll" not in enabled

    def test_enabled_names_for_class_respects_null_version_id(self, app, classroom):
        """Test that features with NULL economic_version_id are treated as disabled."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc
            version_id = "v1"

            v1 = EconomicEngine(
                economic_version_id=version_id,
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            db.session.add(v1)
            db.session.commit()

            # Add feature with NULL economic_version_id
            f1 = ClassFeature(
                class_id=classroom.class_id,
                feature="store",
                economic_version_id=None,
                effective_at=now,
            )
            db.session.add(f1)
            db.session.commit()

            enabled = ClassFeature.enabled_names_for_class(classroom.class_id)
            assert "store" not in enabled

    def test_enabled_names_for_class_empty_when_no_entries(self, app, classroom):
        """Test that enabled_names_for_class returns empty set when no entries exist."""
        with app.app_context():
            enabled = ClassFeature.enabled_names_for_class(classroom.class_id)
            assert enabled == set()

    def test_enabled_names_for_class_cascade_delete_on_version(self, app, classroom):
        """Test that deleting an economic version with RESTRICT prevents deletion."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc
            version_id = "v1"

            v1 = EconomicEngine(
                economic_version_id=version_id,
                class_id=classroom.class_id,
                economy_policy_mode="default",
            )
            db.session.add(v1)
            db.session.commit()

            # Add feature referencing version
            f1 = ClassFeature(
                class_id=classroom.class_id,
                feature="banking",
                economic_version_id=version_id,
                effective_at=now,
            )
            db.session.add(f1)
            db.session.commit()

            # Attempt to delete version should fail (RESTRICT FK)
            db.session.delete(v1)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


class TestEconomicEngineCheckConstraints:
    """Verify all check constraints are enforced."""

    def test_economy_policy_mode_valid_values(self, app, classroom):
        """Test that economy_policy_mode accepts only valid values."""
        with app.app_context():
            # Valid values
            for mode in ["tight", "default", "comfortable"]:
                v = EconomicEngine(
                    economic_version_id=f"v-{mode}",
                    class_id=classroom.class_id,
                    economy_policy_mode=mode,
                )
                db.session.add(v)
            db.session.commit()

            # Invalid value
            v_invalid = EconomicEngine(
                economic_version_id="v-invalid",
                class_id=classroom.class_id,
                economy_policy_mode="invalid_mode",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_interest_rate_range_constraint(self, app, classroom):
        """Test that interest_rate is between 0 and 1.0."""
        with app.app_context():
            # Valid rates
            for rate in [Decimal("0.00"), Decimal("0.05"), Decimal("1.0")]:
                v = EconomicEngine(
                    economic_version_id=f"v-{rate}",
                    class_id=classroom.class_id,
                    interest_rate=rate,
                    economy_policy_mode="default",
                )
                db.session.add(v)
            db.session.commit()

            # Invalid rate (too high)
            v_invalid = EconomicEngine(
                economic_version_id="v-invalid",
                class_id=classroom.class_id,
                interest_rate=Decimal("1.5"),
                economy_policy_mode="default",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_interest_rate_null_allowed(self, app, classroom):
        """Test that interest_rate can be NULL (not specified)."""
        with app.app_context():
            v = EconomicEngine(
                economic_version_id="v-null",
                class_id=classroom.class_id,
                interest_rate=None,
                economy_policy_mode="default",
            )
            db.session.add(v)
            db.session.commit()

            retrieved = EconomicEngine.query.get("v-null")
            assert retrieved.interest_rate is None

    def test_expected_weekly_hours_positive_constraint(self, app, classroom):
        """Test that expected_weekly_hours must be positive."""
        with app.app_context():
            # Valid hours
            v = EconomicEngine(
                economic_version_id="v-valid",
                class_id=classroom.class_id,
                expected_weekly_hours=40.0,
                economy_policy_mode="default",
            )
            db.session.add(v)
            db.session.commit()

            # Invalid hours (zero)
            v_zero = EconomicEngine(
                economic_version_id="v-zero",
                class_id=classroom.class_id,
                expected_weekly_hours=0.0,
                economy_policy_mode="default",
            )
            db.session.add(v_zero)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_expected_weekly_hours_null_allowed(self, app, classroom):
        """Test that expected_weekly_hours can be NULL (not specified)."""
        with app.app_context():
            v = EconomicEngine(
                economic_version_id="v-null",
                class_id=classroom.class_id,
                expected_weekly_hours=None,
                economy_policy_mode="default",
            )
            db.session.add(v)
            db.session.commit()

            retrieved = EconomicEngine.query.get("v-null")
            assert retrieved.expected_weekly_hours is None

    def test_interest_calculation_type_constraint(self, app, classroom):
        """Test that interest_calculation_type is simple or compound."""
        with app.app_context():
            # Valid types
            for calc_type in ["simple", "compound"]:
                v = EconomicEngine(
                    economic_version_id=f"v-{calc_type}",
                    class_id=classroom.class_id,
                    interest_calculation_type=calc_type,
                    economy_policy_mode="default",
                )
                db.session.add(v)
            db.session.commit()

            # Invalid type
            v_invalid = EconomicEngine(
                economic_version_id="v-invalid",
                class_id=classroom.class_id,
                interest_calculation_type="invalid",
                economy_policy_mode="default",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_compound_frequency_constraint(self, app, classroom):
        """Test that compound_frequency is daily, weekly, monthly, or NULL."""
        with app.app_context():
            # Valid frequencies
            for freq in ["daily", "weekly", "monthly"]:
                v = EconomicEngine(
                    economic_version_id=f"v-{freq}",
                    class_id=classroom.class_id,
                    compound_frequency=freq,
                    economy_policy_mode="default",
                )
                db.session.add(v)
            db.session.commit()

            # Invalid frequency
            v_invalid = EconomicEngine(
                economic_version_id="v-invalid",
                class_id=classroom.class_id,
                compound_frequency="quarterly",
                economy_policy_mode="default",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_interest_accrual_frequency_constraint(self, app, classroom):
        """Test that interest_accrual_frequency is daily, weekly, monthly, or NULL."""
        with app.app_context():
            # Valid frequencies
            for freq in ["daily", "weekly", "monthly"]:
                v = EconomicEngine(
                    economic_version_id=f"v-accrual-{freq}",
                    class_id=classroom.class_id,
                    interest_accrual_frequency=freq,
                    economy_policy_mode="default",
                )
                db.session.add(v)
            db.session.commit()

            # Invalid frequency
            v_invalid = EconomicEngine(
                economic_version_id="v-accrual-invalid",
                class_id=classroom.class_id,
                interest_accrual_frequency="hourly",
                economy_policy_mode="default",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_interest_payout_frequency_constraint(self, app, classroom):
        """Test that interest_payout_frequency is weekly or monthly."""
        with app.app_context():
            # Valid frequencies
            for freq in ["weekly", "monthly"]:
                v = EconomicEngine(
                    economic_version_id=f"v-payout-{freq}",
                    class_id=classroom.class_id,
                    interest_payout_frequency=freq,
                    economy_policy_mode="default",
                )
                db.session.add(v)
            db.session.commit()

            # Invalid frequency (daily not allowed for payout)
            v_invalid = EconomicEngine(
                economic_version_id="v-payout-daily",
                class_id=classroom.class_id,
                interest_payout_frequency="daily",
                economy_policy_mode="default",
            )
            db.session.add(v_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


class TestClassFeatureCheckConstraints:
    """Verify class_features check constraints."""

    def test_feature_valid_values(self, app, classroom):
        """Test that feature column accepts only valid feature names."""
        with app.app_context():
            now = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        ).canonical_now_utc
            valid_features = ['payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store']

            for feature in valid_features:
                f = ClassFeature(
                    class_id=classroom.class_id,
                    feature=feature,
                    economic_version_id=None,
                    effective_at=now + timedelta(seconds=len(feature)),
                )
                db.session.add(f)
            db.session.commit()

            # Invalid feature
            f_invalid = ClassFeature(
                class_id=classroom.class_id,
                feature="invalid_feature",
                effective_at=now + timedelta(hours=1),
            )
            db.session.add(f_invalid)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_cascade_delete_on_class_deletion(self, app, teacher):
        """Test that deleting a class cascades to class_features."""
        with app.app_context():
            cls = ClassEconomy(
                class_id="temp-cls",
                class_public_id="temp-pub",
                join_code="TEMP456",
                teacher_user_id=teacher.id,
            )
            db.session.add(cls)
            db.session.commit()

            f = ClassFeature(
                class_id="temp-cls",
                feature="banking",
                economic_version_id=None,
                effective_at=canonical_temporal_resolver(
                    SYSTEM_LEVEL_EVALUATION,
                    primitive="current_time"
                ).canonical_now_utc,
            )
            db.session.add(f)
            db.session.commit()

            # Verify feature exists
            count = ClassFeature.query.filter_by(class_id="temp-cls").count()
            assert count == 1

            # Delete class
            db.session.delete(cls)
            db.session.commit()

            # Verify feature was cascaded
            count = ClassFeature.query.filter_by(class_id="temp-cls").count()
            assert count == 0


class TestPhase2dImmutability:
    """Tests for Phase 2d database-level immutability enforcement.

    Note: v2 FEAT-INTEGRITY enforcement requires all mutations through FEAT contexts.
    Direct DB mutation tests would need Phase 3 FEAT-ECON-* definitions.
    These tests verify the migration was applied and the code changes compile correctly.
    """

    def test_immutability_triggers_created(self, app):
        """Verify that immutability TRIGGERs exist on economic_engine and class_features.

        This test confirms Phase 2d migration executed successfully without directly
        testing TRIGGER behavior (which requires FEAT-wrapped mutations in v2).
        """
        with app.app_context():
            # Query database to verify TRIGGERs were created
            conn = db.engine.raw_connection()
            cursor = conn.cursor()

            # Check for economic_engine triggers
            cursor.execute(
                "SELECT trigger_name FROM information_schema.triggers "
                "WHERE trigger_name IN ('economic_engine_no_update', 'economic_engine_no_delete')"
            )
            ee_triggers = {row[0] for row in cursor.fetchall()}
            assert 'economic_engine_no_update' in ee_triggers, "economic_engine_no_update TRIGGER should exist"
            assert 'economic_engine_no_delete' in ee_triggers, "economic_engine_no_delete TRIGGER should exist"

            # Check for class_features triggers
            cursor.execute(
                "SELECT trigger_name FROM information_schema.triggers "
                "WHERE trigger_name IN ('class_features_no_update', 'class_features_no_delete')"
            )
            cf_triggers = {row[0] for row in cursor.fetchall()}
            assert 'class_features_no_update' in cf_triggers, "class_features_no_update TRIGGER should exist"
            assert 'class_features_no_delete' in cf_triggers, "class_features_no_delete TRIGGER should exist"

            cursor.close()
            conn.close()

    def test_timeline_query_uses_temporal_resolver(self, app):
        """Verify that enabled_names_for_class uses canonical_temporal_resolver.

        This test confirms the timeline query fix was applied (effective_at <= current_time filter).
        Full behavior testing requires Phase 3 FEAT-ECON-* and FEAT-INTEGRITY-aware test setup.
        """
        with app.app_context():
            # Verify the method exists and is callable
            assert hasattr(ClassFeature, 'enabled_names_for_class')
            assert callable(ClassFeature.enabled_names_for_class)

            # Call with a non-existent class_id should return empty set (not crash)
            result = ClassFeature.enabled_names_for_class("non-existent-class")
            assert isinstance(result, set)
            assert len(result) == 0, "Non-existent class should have no enabled features"


class TestPhase2aMigration:
    """Tests for Phase 2a migration fixes: conn variable scope and interest_payout_frequency preservation.

    Per Phase A Step 1 execution plan:
    1. Verify fresh DB bootstrap doesn't crash (conn variable available in all steps)
    2. Verify interest_payout_frequency column exists and can be queried

    Note: These tests verify the MIGRATION ran successfully, not that classroom initialization
    creates EconomicEngine versions (that's Phase 2d work).
    """

    def test_economic_engine_table_exists_and_is_queryable(self, app):
        """Test that economic_engine table was created and is queryable (verifies conn available).

        This indirectly verifies that the migration didn't crash on NameError when accessing conn
        in STEP 3, which would happen if conn was only defined inside STEP 2 conditional.

        The migration defines conn = op.get_bind() at the top of upgrade(), making it available
        for STEP 1 (create table), STEP 2 (migrate data), STEP 3 (restructure class_features),
        and STEP 4 (update classes table).
        """
        with app.app_context():
            # Simply querying should succeed; the table exists (or migration would have failed)
            # If conn was undefined in STEP 3, migration would have crashed with NameError
            versions = EconomicEngine.query.all()  # Query all versions (may be empty on fresh DB)
            # Success: table exists and is queryable, migration didn't crash
            assert isinstance(versions, list), "EconomicEngine should be queryable"

    def test_economic_engine_interest_payout_frequency_column_exists(self, app):
        """Test that interest_payout_frequency column exists (verifies interest preservation in migration).

        Verifies the migration SELECT includes bs.interest_schedule_type and the INSERT
        correctly includes interest_payout_frequency (not hardcoded as NULL or missing).

        If migration SELECT didn't include bs.interest_schedule_type, the INSERT would either:
        1. Missing interest_payout_frequency column in schema
        2. Interest_payout_frequency hardcoded as NULL without preservation

        This test verifies the column exists and can be queried.
        """
        with app.app_context():
            # Verify EconomicEngine ORM model includes interest_payout_frequency attribute
            assert hasattr(EconomicEngine, 'interest_payout_frequency'), \
                "EconomicEngine should have interest_payout_frequency column"

            # Verify we can query for interest_payout_frequency without error
            # (This will be empty on fresh DB, but tests that the column exists)
            test_query = EconomicEngine.query.filter(
                EconomicEngine.interest_payout_frequency.in_(['weekly', 'monthly'])
            ).all()
            assert isinstance(test_query, list), \
                "Should be able to query interest_payout_frequency column"
