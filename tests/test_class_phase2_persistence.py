"""
CLASS Phase 2 Persistence Tests

Verifies the persistence-layer invariants of the versioned economic engine and the
append-only class_features timeline per DOM-CLASS-001 / DOM-CLASS-002 authority:

  1. Exactly one EconomicEngine root per class (previous_version_id IS NULL).
  2. Historical versions are immutable (no in-place UPDATE).
  3. previous_version_id lineage stays within the owning class.
  4. Referenced versions cannot be deleted (RESTRICT / append-only enforcement).
  5. class_features is an append-only history.
  6. Effective-version resolution returns the latest enabled row per feature.
  7. In-place mutation / deletion of historical rows is prohibited.

Rewrite note (Priority A, 2026-08-23)
-------------------------------------
These tests were previously module-skipped because they mutated state via direct
`db.session.add`/`commit` on domain models, which v2 FEAT-INTEGRITY enforcement
(app/feats/base.py) now blocks outside a verified FEAT context.

The invariants split into two categories, tested through two lawful mechanisms:

* Valid-state / behavioral invariants (1, 3, 5, 6) are established through the
  CANONICAL PRODUCERS: the ClassEconomy after_insert listener seeds the single
  root engine + default 'payroll' feature; FEAT-CLASS-004 enables/disables
  features; FEAT-CLASS-005 evolves the engine into new immutable versions. No
  direct ORM mutation of domain models occurs.

* Persistence-ENFORCEMENT invariants (2, 4, 7 + CHECK/PK constraints) test that
  the DATABASE rejects illegal states. Canonical producers cannot exercise these
  — they validate inputs and never emit illegal rows. The only faithful way to
  probe the persistence boundary is to issue raw SQL through
  `db.session.execute(text(...))`. Raw SQL does not populate
  session.new/dirty/deleted, so it is NOT the ORM-object mutation that
  FEAT-INTEGRITY guards; it reaches the DB boundary directly, which is exactly
  what a persistence-constraint test must do. Assertions are unchanged in
  strength — illegal writes must still raise.

Phase 2d immutability triggers (economic_engine_no_update/no_delete,
class_features_no_update/no_delete) are present on the test database and raise
`InternalError` ("... immutable ...") on any UPDATE/DELETE. They are unconditional
and therefore SUBSUME the RESTRICT foreign keys: no historical row can be deleted
at all. Tests for deletion-prevention assert the block and note that the trigger
is the proximate enforcer with RESTRICT as defense-in-depth.

Class hard-deletion vs. append-only history (see the two cascade tests):
EconomicEngine.class_id and ClassFeature.class_id declare `ondelete='CASCADE'`.
The append-only no_delete triggers are NOT an absolute bar — they yield to the
sanctioned session flag `cth.class_universe_destroying='on'`, which the canonical
hard-deletion path `_hard_delete_class_scope` (app/routes/admin.py) sets via
`SET LOCAL` before deleting the `classes` row. A naive `DELETE FROM classes`
(without the flag) is correctly blocked; the canonical boundary permits the
cascade. The cascade tests drive that canonical flag+delete boundary and assert
the owned engine/feature history is physically removed.

Per SPEC-TEST-001: classroom state is provisioned via the canonical initializer.
Per SPEC-TIME-001: temporal values come from canonical_temporal_resolver.
"""
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InternalError

from app.models import EconomicEngine, ClassFeature
from app.extensions import db
from app.services.class_configuration_query_service import get_initial_economic_engine
from app.services.context_resolver import CanonicalContext
from app.feats.class_configuration.feat_class_004_feature_enablement import (
    execute_enable_feature,
    execute_disable_feature,
)
from app.feats.class_configuration.feat_class_005_economic_engine_evolution import (
    execute_evolve_economic_engine,
)
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
)
from tests.helpers.classroom_initializer import initialize


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

@pytest.fixture
def classroom(app):
    """Provision a canonical test classroom per SPEC-TEST-001.

    The ClassEconomy after_insert listener seeds exactly one root EconomicEngine
    (previous_version_id IS NULL) and enables only the 'payroll' feature.
    """
    return initialize("chemistry_p1", app)


def _now():
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION, primitive="current_time"
    ).canonical_now_utc


def _ctx(classroom):
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _raw_insert_engine(class_id, *, version_id=None, mode="default",
                       previous_version_id=None, **fields):
    """Insert an economic_engine row via raw SQL, bypassing the ORM (and thus
    FEAT-INTEGRITY) to probe DB-level constraints directly. Returns version id.

    Raises the underlying DB error (IntegrityError / InternalError) on violation.
    """
    version_id = version_id or str(uuid.uuid4())
    cols = {
        "economic_version_id": version_id,
        "class_id": class_id,
        "economy_policy_mode": mode,
        "previous_version_id": previous_version_id,
        "created_at": _now(),
    }
    cols.update(fields)
    col_names = ", ".join(cols.keys())
    placeholders = ", ".join(f":{k}" for k in cols.keys())
    db.session.execute(
        text(f"INSERT INTO economic_engine ({col_names}) VALUES ({placeholders})"),
        cols,
    )
    db.session.commit()
    return version_id


def _raw_insert_feature(class_id, feature, effective_at, *, economic_version_id=None):
    """Insert a class_features row via raw SQL. Returns nothing; raises on violation."""
    cols = {
        "class_id": class_id,
        "feature": feature,
        "effective_at": effective_at,
        "economic_version_id": economic_version_id,
        "deleted_at": None,
        "created_at": _now(),
    }
    col_names = ", ".join(cols.keys())
    placeholders = ", ".join(f":{k}" for k in cols.keys())
    db.session.execute(
        text(f"INSERT INTO class_features ({col_names}) VALUES ({placeholders})"),
        cols,
    )
    db.session.commit()


# --------------------------------------------------------------------------- #
# Invariant 2 & 7: EconomicEngine immutability
# --------------------------------------------------------------------------- #

class TestEconomicEngineImmutability:
    """Historical EconomicEngine versions are immutable after persistence."""

    def test_economic_engine_created_successfully(self, app, classroom):
        """A configured engine version is created through the canonical evolution
        FEAT and persists its field values."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            assert root is not None

            result = execute_evolve_economic_engine(
                canonical_context=_ctx(classroom),
                class_id=classroom.class_id,
                updates={
                    "expected_weekly_hours": 40.0,
                    "interest_rate": 0.05,
                    "interest_calculation_type": "simple",
                    "economy_policy_mode": "comfortable",
                },
                feature_list=["payroll"],  # only payroll is enabled by default
                idempotency_key="phase2-create",
            )
            assert result.success is True, result.error_message

            created = EconomicEngine.query.get(result.new_engine_id)
            assert created is not None
            assert float(created.expected_weekly_hours) == 40.0
            assert float(created.interest_rate) == 0.05
            assert created.interest_calculation_type == "simple"
            assert created.economy_policy_mode == "comfortable"

    def test_economic_engine_prevents_field_modification(self, app, classroom):
        """An in-place UPDATE of a persisted engine row is rejected by the
        append-only immutability trigger (invariant 2/7)."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)

            with pytest.raises(InternalError, match="immutable"):
                db.session.execute(
                    text("UPDATE economic_engine SET expected_weekly_hours = 50 "
                         "WHERE economic_version_id = :v"),
                    {"v": root.economic_version_id},
                )
                db.session.commit()
            db.session.rollback()

            # Row is unchanged.
            still = EconomicEngine.query.get(root.economic_version_id)
            assert still.expected_weekly_hours == root.expected_weekly_hours

    def test_economic_engine_mutation_path_is_new_version(self, app, classroom):
        """The lawful way to 'change' configuration is a NEW version; the prior
        version is left untouched (append-only lineage, invariant 3/7)."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            root_id = root.economic_version_id
            root_mode = root.economy_policy_mode

            result = execute_evolve_economic_engine(
                canonical_context=_ctx(classroom),
                class_id=classroom.class_id,
                updates={"economy_policy_mode": "tight"},
                feature_list=["payroll"],
                idempotency_key="phase2-newversion",
            )
            assert result.success is True, result.error_message
            assert result.new_engine_id != root_id

            # Prior version is unchanged; new version carries the update and links back.
            prior = EconomicEngine.query.get(root_id)
            assert prior.economy_policy_mode == root_mode
            new = EconomicEngine.query.get(result.new_engine_id)
            assert new.economy_policy_mode == "tight"
            assert new.previous_version_id == root_id

    def test_economic_engine_null_fields_preserved(self, app, classroom):
        """The seeded root engine preserves NULL 'not specified' banking fields."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            assert root.interest_rate is None
            assert root.interest_calculation_type is None
            assert root.compound_frequency is None
            assert root.interest_accrual_frequency is None


# --------------------------------------------------------------------------- #
# Invariant 1, 3, 4: version chain integrity
# --------------------------------------------------------------------------- #

class TestEconomicEngineVersionChain:
    """Version chain integrity and deletion-prevention behavior."""

    def test_exactly_one_root_per_class(self, app, classroom):
        """A provisioned class has exactly one root engine (invariant 1)."""
        with app.app_context():
            roots = EconomicEngine.query.filter_by(
                class_id=classroom.class_id, previous_version_id=None
            ).all()
            assert len(roots) == 1
            initial = get_initial_economic_engine(classroom.class_id)
            assert roots[0].economic_version_id == initial.economic_version_id

    def test_version_chain_creation(self, app, classroom):
        """Successive evolutions build a same-class previous_version_id chain
        (invariant 3), rooted at the single NULL-predecessor root."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            ctx = _ctx(classroom)

            r1 = execute_evolve_economic_engine(
                canonical_context=ctx, class_id=classroom.class_id,
                updates={"economy_policy_mode": "comfortable"},
                feature_list=["payroll"], idempotency_key="chain-1",
            )
            assert r1.success is True, r1.error_message

            r2 = execute_evolve_economic_engine(
                canonical_context=ctx, class_id=classroom.class_id,
                updates={"economy_policy_mode": "tight"},
                feature_list=["payroll"], idempotency_key="chain-2",
            )
            assert r2.success is True, r2.error_message

            v3 = EconomicEngine.query.get(r2.new_engine_id)
            v2 = EconomicEngine.query.get(v3.previous_version_id)
            v1 = EconomicEngine.query.get(v2.previous_version_id)
            assert v2.economic_version_id == r1.new_engine_id
            assert v1.economic_version_id == root.economic_version_id
            assert v1.previous_version_id is None
            # Whole chain stays within the owning class.
            for v in (v1, v2, v3):
                assert v.class_id == classroom.class_id

    def test_first_version_has_null_previous_id(self, app, classroom):
        """The root version has a NULL previous_version_id (invariant 1/3)."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            assert root.previous_version_id is None

    def test_referenced_version_cannot_be_deleted(self, app, classroom):
        """A version referenced by a later version cannot be deleted (invariant 4).

        Proximate enforcer is the append-only no_delete trigger, which subsumes
        the RESTRICT foreign key (no historical version is deletable at all)."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            r = execute_evolve_economic_engine(
                canonical_context=_ctx(classroom), class_id=classroom.class_id,
                updates={"economy_policy_mode": "comfortable"},
                feature_list=["payroll"], idempotency_key="restrict-1",
            )
            assert r.success is True, r.error_message

            with pytest.raises(InternalError, match="immutable"):
                db.session.execute(
                    text("DELETE FROM economic_engine WHERE economic_version_id = :v"),
                    {"v": root.economic_version_id},
                )
                db.session.commit()
            db.session.rollback()

            assert EconomicEngine.query.get(root.economic_version_id) is not None

    def test_same_class_lineage_enforced_by_composite_fk(self, app, classroom):
        """previous_version_id must reference a version IN THE SAME CLASS.

        The composite FK (class_id, previous_version_id) -> (class_id,
        economic_version_id) rejects a raw INSERT whose previous_version_id names
        a version id that does not exist under this class_id (invariant 3)."""
        with app.app_context():
            with pytest.raises(IntegrityError):
                _raw_insert_engine(
                    classroom.class_id,
                    previous_version_id="nonexistent-version-id",
                )
            db.session.rollback()

    def test_cascade_delete_on_class_deletion(self, app, classroom):
        """Deleting a class through the CANONICAL universe-destruction boundary
        physically removes its EconomicEngine history.

        The append-only economic_engine_no_delete trigger is not an absolute bar:
        it yields to the sanctioned session flag `cth.class_universe_destroying`.
        The canonical hard-deletion path `_hard_delete_class_scope`
        (app/routes/admin.py) runs `SET LOCAL cth.class_universe_destroying='on'`
        and then deletes the `classes` row; the ondelete='CASCADE' foreign key on
        `economic_engine.class_id` removes the owned engine versions, which the
        trigger now permits. This test drives that exact boundary (flag + class
        row delete) rather than a naive `DELETE FROM classes`."""
        with app.app_context():
            cid = classroom.class_id

            # Grow the version chain so the cascade must remove root + child.
            r = execute_evolve_economic_engine(
                canonical_context=_ctx(classroom), class_id=cid,
                updates={"economy_policy_mode": "comfortable"},
                feature_list=["payroll"], idempotency_key="cascade-ee",
            )
            assert r.success is True, r.error_message
            assert EconomicEngine.query.filter_by(class_id=cid).count() >= 2

            # Canonical destruction boundary: authorize immutable-history deletion
            # for this class universe, then delete the class row in the same
            # transaction (CASCADE removes the engine versions).
            db.session.execute(text("SET LOCAL cth.class_universe_destroying = 'on'"))
            db.session.execute(
                text("DELETE FROM classes WHERE class_id = :cid"), {"cid": cid}
            )
            db.session.commit()

            db.session.expire_all()
            assert EconomicEngine.query.filter_by(class_id=cid).count() == 0


# --------------------------------------------------------------------------- #
# Invariant 5 & 6: class_features append-only timeline
# --------------------------------------------------------------------------- #

class TestClassFeatureAppendOnly:
    """Append-only class_features timeline and effective-version resolution."""

    def test_multiple_feature_entries_same_class_feature(self, app, classroom):
        """Enable then disable a feature: two append-only rows for the same
        (class_id, feature) with distinct effective_at (invariant 5)."""
        with app.app_context():
            ctx = _ctx(classroom)
            root = get_initial_economic_engine(classroom.class_id)

            enabled = execute_enable_feature(
                canonical_context=ctx, class_id=classroom.class_id,
                feature="banking", economic_version_id=root.economic_version_id,
                correlation_id="append-enable",
            )
            assert enabled.success is True, enabled.error_message

            disabled = execute_disable_feature(
                canonical_context=ctx, class_id=classroom.class_id,
                feature="banking", correlation_id="append-disable",
            )
            assert disabled.success is True, disabled.error_message

            rows = ClassFeature.query.filter_by(
                class_id=classroom.class_id, feature="banking"
            ).all()
            assert len(rows) == 2

    def test_composite_primary_key_uniqueness(self, app, classroom):
        """Composite PK (class_id, feature, effective_at) rejects a duplicate row.

        Probed at the DB boundary via raw SQL — INSERT is not intercepted by the
        append-only triggers (which guard UPDATE/DELETE only)."""
        with app.app_context():
            root = get_initial_economic_engine(classroom.class_id)
            at = _now()
            _raw_insert_feature(
                classroom.class_id, "banking", at,
                economic_version_id=root.economic_version_id,
            )
            with pytest.raises(IntegrityError):
                _raw_insert_feature(
                    classroom.class_id, "banking", at,
                    economic_version_id=root.economic_version_id,
                )
            db.session.rollback()

    def test_effective_version_resolution_latest_enabled(self, app, classroom):
        """enabled_names_for_class resolves the latest effective row per feature
        (invariant 6). Evolving banking to a new version keeps it enabled."""
        with app.app_context():
            ctx = _ctx(classroom)
            root = get_initial_economic_engine(classroom.class_id)

            enabled = execute_enable_feature(
                canonical_context=ctx, class_id=classroom.class_id,
                feature="banking", economic_version_id=root.economic_version_id,
                correlation_id="resolve-enable",
            )
            assert enabled.success is True, enabled.error_message

            # Evolve: append a later banking row linked to a new engine version.
            evolved = execute_evolve_economic_engine(
                canonical_context=ctx, class_id=classroom.class_id,
                updates={"economy_policy_mode": "comfortable"},
                feature_list=["banking"], idempotency_key="resolve-evolve",
            )
            assert evolved.success is True, evolved.error_message

            names = ClassFeature.enabled_names_for_class(classroom.class_id)
            assert "banking" in names
            # The resolved banking row points at the newest engine version.
            latest = (
                ClassFeature.query.filter_by(
                    class_id=classroom.class_id, feature="banking"
                )
                .order_by(ClassFeature.effective_at.desc())
                .first()
            )
            assert latest.economic_version_id == evolved.new_engine_id

    def test_disabled_feature_excluded_from_resolution(self, app, classroom):
        """A feature whose latest row is a disablement (NULL version) is excluded
        from enabled resolution (invariant 6)."""
        with app.app_context():
            ctx = _ctx(classroom)
            root = get_initial_economic_engine(classroom.class_id)

            execute_enable_feature(
                canonical_context=ctx, class_id=classroom.class_id,
                feature="store", economic_version_id=root.economic_version_id,
                correlation_id="disabled-enable",
            )
            execute_disable_feature(
                canonical_context=ctx, class_id=classroom.class_id,
                feature="store", correlation_id="disabled-disable",
            )
            names = ClassFeature.enabled_names_for_class(classroom.class_id)
            assert "store" not in names

    def test_enabled_names_empty_for_unknown_class(self, app, classroom):
        """A class with no feature history resolves to an empty enabled set."""
        with app.app_context():
            assert ClassFeature.enabled_names_for_class(str(uuid.uuid4())) == set()

    def test_default_seed_enables_only_payroll(self, app, classroom):
        """The canonical seed enables exactly 'payroll' at provision time
        (invariant 5/6 baseline)."""
        with app.app_context():
            names = ClassFeature.enabled_names_for_class(classroom.class_id)
            assert names == {"payroll"}


# --------------------------------------------------------------------------- #
# EconomicEngine CHECK constraints (persistence enforcement via raw SQL)
# --------------------------------------------------------------------------- #

class TestEconomicEngineCheckConstraints:
    """DB CHECK constraints reject illegal engine rows. Probed at the DB boundary
    with raw SQL because canonical producers never emit illegal values."""

    def test_economy_policy_mode_valid_values(self, app, classroom):
        with app.app_context():
            for mode in ("tight", "default", "comfortable"):
                _raw_insert_engine(classroom.class_id, mode=mode)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, mode="invalid_mode")
            db.session.rollback()

    def test_interest_rate_range_constraint(self, app, classroom):
        with app.app_context():
            for rate in (0.0, 0.05, 1.0):
                _raw_insert_engine(classroom.class_id, interest_rate=rate)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, interest_rate=1.5)
            db.session.rollback()

    def test_interest_rate_null_allowed(self, app, classroom):
        with app.app_context():
            vid = _raw_insert_engine(classroom.class_id, interest_rate=None)
            assert EconomicEngine.query.get(vid).interest_rate is None

    def test_expected_weekly_hours_positive_constraint(self, app, classroom):
        with app.app_context():
            _raw_insert_engine(classroom.class_id, expected_weekly_hours=40.0)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, expected_weekly_hours=0.0)
            db.session.rollback()

    def test_expected_weekly_hours_null_allowed(self, app, classroom):
        with app.app_context():
            vid = _raw_insert_engine(classroom.class_id, expected_weekly_hours=None)
            assert EconomicEngine.query.get(vid).expected_weekly_hours is None

    def test_interest_calculation_type_constraint(self, app, classroom):
        with app.app_context():
            for calc in ("simple", "compound"):
                _raw_insert_engine(classroom.class_id, interest_calculation_type=calc)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, interest_calculation_type="invalid")
            db.session.rollback()

    def test_compound_frequency_constraint(self, app, classroom):
        with app.app_context():
            for freq in ("never", "daily", "weekly", "monthly"):
                _raw_insert_engine(classroom.class_id, compound_frequency=freq)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, compound_frequency="quarterly")
            db.session.rollback()

    def test_interest_accrual_frequency_constraint(self, app, classroom):
        with app.app_context():
            for freq in ("daily", "weekly", "monthly"):
                _raw_insert_engine(classroom.class_id, interest_accrual_frequency=freq)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, interest_accrual_frequency="hourly")
            db.session.rollback()

    def test_interest_payout_frequency_constraint(self, app, classroom):
        with app.app_context():
            for freq in ("weekly", "monthly"):
                _raw_insert_engine(classroom.class_id, interest_payout_frequency=freq)
            with pytest.raises(IntegrityError):
                _raw_insert_engine(classroom.class_id, interest_payout_frequency="daily")
            db.session.rollback()


# --------------------------------------------------------------------------- #
# class_features CHECK constraints
# --------------------------------------------------------------------------- #

class TestClassFeatureCheckConstraints:
    """DB CHECK constraint on class_features.feature."""

    def test_feature_valid_values(self, app, classroom):
        with app.app_context():
            base = _now()
            valid = ["payroll", "insurance", "banking", "rent", "hall_pass", "store"]
            for i, feature in enumerate(valid):
                # payroll already exists at seed time; use distinct effective_at
                # per feature to avoid PK collisions with the seed row.
                _raw_insert_feature(
                    classroom.class_id, feature,
                    base + timedelta(seconds=i + 1),
                )
            with pytest.raises(IntegrityError):
                _raw_insert_feature(
                    classroom.class_id, "invalid_feature",
                    base + timedelta(hours=1),
                )
            db.session.rollback()

    def test_cascade_delete_on_class_deletion(self, app, classroom):
        """Deleting a class through the CANONICAL universe-destruction boundary
        physically removes its ClassFeature history.

        As with EconomicEngine, the class_features_no_delete append-only trigger
        yields to the sanctioned `cth.class_universe_destroying='on'` flag that the
        canonical hard-deletion path (`_hard_delete_class_scope`) sets before
        deleting the `classes` row; the ondelete='CASCADE' foreign key on
        `class_features.class_id` then removes the owned feature rows."""
        with app.app_context():
            cid = classroom.class_id
            ctx = _ctx(classroom)

            # Append a second feature so the cascade must remove more than the
            # seeded 'payroll' row.
            root = get_initial_economic_engine(cid)
            enabled = execute_enable_feature(
                canonical_context=ctx, class_id=cid, feature="banking",
                economic_version_id=root.economic_version_id,
                correlation_id="cascade-cf",
            )
            assert enabled.success is True, enabled.error_message
            assert ClassFeature.query.filter_by(class_id=cid).count() >= 2

            # Canonical destruction boundary: authorize immutable-history deletion,
            # then delete the class row (CASCADE removes the feature rows).
            db.session.execute(text("SET LOCAL cth.class_universe_destroying = 'on'"))
            db.session.execute(
                text("DELETE FROM classes WHERE class_id = :cid"), {"cid": cid}
            )
            db.session.commit()

            db.session.expire_all()
            assert ClassFeature.query.filter_by(class_id=cid).count() == 0


# --------------------------------------------------------------------------- #
# Phase 2d / 2a migration verification (query-only, unchanged)
# --------------------------------------------------------------------------- #

class TestPhase2dImmutability:
    """Verify Phase 2d database-level immutability triggers are present."""

    def test_immutability_triggers_created(self, app):
        with app.app_context():
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT trigger_name FROM information_schema.triggers "
                "WHERE trigger_name IN ('economic_engine_no_update', 'economic_engine_no_delete')"
            )
            ee_triggers = {row[0] for row in cursor.fetchall()}
            assert 'economic_engine_no_update' in ee_triggers
            assert 'economic_engine_no_delete' in ee_triggers

            cursor.execute(
                "SELECT trigger_name FROM information_schema.triggers "
                "WHERE trigger_name IN ('class_features_no_update', 'class_features_no_delete')"
            )
            cf_triggers = {row[0] for row in cursor.fetchall()}
            assert 'class_features_no_update' in cf_triggers
            assert 'class_features_no_delete' in cf_triggers

            cursor.close()
            conn.close()

    def test_timeline_query_uses_temporal_resolver(self, app):
        with app.app_context():
            assert hasattr(ClassFeature, 'enabled_names_for_class')
            assert callable(ClassFeature.enabled_names_for_class)
            result = ClassFeature.enabled_names_for_class("non-existent-class")
            assert isinstance(result, set)
            assert len(result) == 0


class TestPhase2aMigration:
    """Verify Phase 2a migration produced a queryable economic_engine table."""

    def test_economic_engine_table_exists_and_is_queryable(self, app):
        with app.app_context():
            versions = EconomicEngine.query.all()
            assert isinstance(versions, list)

    def test_economic_engine_interest_payout_frequency_column_exists(self, app):
        with app.app_context():
            assert hasattr(EconomicEngine, 'interest_payout_frequency')
            test_query = EconomicEngine.query.filter(
                EconomicEngine.interest_payout_frequency.in_(['weekly', 'monthly'])
            ).all()
            assert isinstance(test_query, list)
