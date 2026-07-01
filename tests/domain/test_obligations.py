"""Wave 7 — Obligations Domain (DOM-OBL-001) schema tests.

These tests verify the canonical obligation table definitions without requiring
a live database connection. They check that models have the right columns,
ForeignKey targets, and constraints to implement the DOM-OBL-001 spec.
"""
from sqlalchemy import UniqueConstraint

from app.models import (
    User,
    UserRole,
    EntitlementEvent,
    InsuranceEnrollment,
    ObligationAssessment,
    ObligationLifecycle,
    ObligationReversal,
    ObligationSatisfaction,
)


def _fk_targets(model, column_name):
    return {fk.target_fullname for fk in model.__table__.c[column_name].foreign_keys}


def _column_names(model):
    return set(model.__table__.c.keys())


def _unique_constraints(model):
    return {c.name for c in model.__table__.constraints if isinstance(c, UniqueConstraint)}


# ---------------------------------------------------------------------------
# ObligationAssessment — debt fact record
# ---------------------------------------------------------------------------

def test_obligation_assessment_has_required_columns():
    """DOM-OBL-001 §VIII.1: assessment must have seat_id, class_id, obligation_type, amount_snap, assessed_at."""
    cols = _column_names(ObligationAssessment)
    assert {"seat_id", "class_id", "obligation_type", "amount_snap", "assessed_at"} <= cols


def test_obligation_assessment_has_rent_cycle_fields():
    """Coverage-window fields required by pre-existing rent cycle model (Wave 7 constraint: MUST NOT alter behavior)."""
    cols = _column_names(ObligationAssessment)
    assert {
        "coverage_start_time",
        "coverage_end_time",
        "cycle_idempotency_key",
        "period_month",
        "period_year",
        "coverage_month",
        "coverage_year",
        "period_key",
    } <= cols


def test_obligation_assessment_seat_fk_targets_seats():
    assert _fk_targets(ObligationAssessment, "seat_id") == {"seats.id"}


def test_obligation_assessment_class_fk_targets_classes():
    assert _fk_targets(ObligationAssessment, "class_id") == {"classes.class_id"}


def test_obligation_assessment_idempotency_unique_constraint_exists():
    """INV-OBL-004: duplicate (seat_id, class_id, cycle_idempotency_key) must be rejected."""
    constraint_names = _unique_constraints(ObligationAssessment)
    assert "uq_assessment_events_idempotency" in constraint_names


def test_obligation_assessment_uses_canonical_table_name():
    assert ObligationAssessment.__tablename__ == "assessment_events"


def test_obligation_lifecycle_has_required_columns():
    assert {"assessment_id", "status", "updated_at"} <= _column_names(ObligationLifecycle)


def test_obligation_lifecycle_assessment_fk_targets_assessment():
    assert _fk_targets(ObligationLifecycle, "assessment_id") == {"assessment_events.id"}


# ---------------------------------------------------------------------------
# ObligationSatisfaction — payment/waiver record
# ---------------------------------------------------------------------------

def test_obligation_satisfaction_has_required_columns():
    """DOM-OBL-001 §VIII.2: satisfaction must link to assessment and record method, satisfied_at."""
    cols = _column_names(ObligationSatisfaction)
    assert {"assessment_id", "method", "satisfied_at"} <= cols


def test_obligation_satisfaction_has_payment_detail_columns():
    cols = _column_names(ObligationSatisfaction)
    assert {"amount_paid", "was_late", "late_fee_charged", "transaction_id"} <= cols


def test_obligation_satisfaction_assessment_fk_targets_assessment():
    assert _fk_targets(ObligationSatisfaction, "assessment_id") == {"assessment_events.id"}


def test_obligation_satisfaction_transaction_fk_targets_ledger():
    assert _fk_targets(ObligationSatisfaction, "transaction_id") == {"ledger_transaction.id"}


def test_obligation_satisfaction_assessment_id_is_unique():
    """DOM-OBL-001 §VIII.2: one satisfaction per assessment (1:1)."""
    cols = ObligationSatisfaction.__table__.c
    assert cols["assessment_id"].unique is True


# ---------------------------------------------------------------------------
# ObligationReversal — nullification record
# ---------------------------------------------------------------------------

def test_obligation_reversal_has_required_columns():
    """DOM-OBL-001 §VIII.3: reversal must link to assessment with reason and timestamp."""
    cols = _column_names(ObligationReversal)
    assert {"assessment_id", "reason", "reversed_at", "reversed_by_seat_id"} <= cols


def test_obligation_reversal_assessment_fk_targets_assessment():
    assert _fk_targets(ObligationReversal, "assessment_id") == {"assessment_events.id"}


def test_obligation_reversal_actor_fk_targets_seats():
    assert _fk_targets(ObligationReversal, "reversed_by_seat_id") == {"seats.id"}


def test_obligation_reversal_assessment_id_is_unique():
    """INV-OBL-005: one reversal per assessment — reversal wins."""
    cols = ObligationReversal.__table__.c
    assert cols["assessment_id"].unique is True


# ---------------------------------------------------------------------------
# InsuranceEnrollment — canonical seat-level contract
# ---------------------------------------------------------------------------

def test_insurance_enrollment_has_required_columns():
    cols = _column_names(InsuranceEnrollment)
    assert {"seat_id", "class_id", "policy_id", "status", "purchase_date", "coverage_start_date"} <= cols


def test_insurance_enrollment_has_policy_snapshot_columns():
    """INV-OBL-009: snapshot must be captured at purchase time — mutable template changes don't affect enrollments."""
    cols = _column_names(InsuranceEnrollment)
    assert {
        "frozen_policy_title",
        "frozen_max_claim_amount",
        "frozen_max_payout_per_period",
        "frozen_max_claims_count",
        "frozen_max_claims_period",
        "frozen_claim_time_limit_days",
        "policy_version",
    } <= cols


def test_insurance_enrollment_seat_fk_targets_seats():
    assert _fk_targets(InsuranceEnrollment, "seat_id") == {"seats.id"}


def test_insurance_enrollment_class_fk_targets_classes():
    assert _fk_targets(InsuranceEnrollment, "class_id") == {"classes.class_id"}


def test_insurance_enrollment_policy_fk_targets_policies():
    assert _fk_targets(InsuranceEnrollment, "policy_id") == {"insurance_policies.id"}


def test_insurance_enrollment_freeze_policy_snapshot_method_exists():
    """freeze_policy_snapshot() is required to capture terms at purchase time."""
    assert callable(getattr(InsuranceEnrollment, "freeze_policy_snapshot", None))


def test_insurance_enrollment_contract_properties_exist():
    """Contract properties provide a stable interface over the frozen snapshot."""
    for prop in (
        "contract_title",
        "contract_description",
        "contract_max_claim_amount",
        "contract_max_payout_per_period",
        "contract_max_claims_count",
        "contract_max_claims_period",
        "contract_claim_time_limit_days",
    ):
        assert isinstance(getattr(InsuranceEnrollment, prop, None), property), f"Missing property: {prop}"


# ---------------------------------------------------------------------------
# EntitlementEvent — append-only perk stream
# ---------------------------------------------------------------------------

def test_entitlement_event_has_required_columns():
    """DOM-OBL-001 §VIII.4: must have seat_id, quantity_delta, event_type, occurred_at."""
    cols = _column_names(EntitlementEvent)
    assert {"seat_id", "class_id", "quantity_delta", "event_type", "occurred_at"} <= cols


def test_entitlement_event_has_idempotency_key_column():
    """INV-OBL-003: consumption trigger_id enables idempotent deduplication."""
    assert "trigger_id" in _column_names(EntitlementEvent)


def test_entitlement_event_seat_fk_targets_seats():
    assert _fk_targets(EntitlementEvent, "seat_id") == {"seats.id"}


def test_entitlement_event_assessment_fk_is_nullable():
    """assessment_id is nullable so grants not tied to a specific obligation can still be recorded."""
    col = EntitlementEvent.__table__.c["assessment_id"]
    assert col.nullable is True


# ---------------------------------------------------------------------------
# Cross-model relationship wiring
# ---------------------------------------------------------------------------

def test_obligation_assessment_satisfaction_relationship_exists():
    """ObligationAssessment.satisfaction should be a one-to-one relationship to ObligationSatisfaction."""
    rel = ObligationAssessment.satisfaction
    assert rel is not None


def test_obligation_assessment_reversal_relationship_exists():
    """ObligationAssessment.reversal should be a one-to-one relationship to ObligationReversal."""
    rel = ObligationAssessment.reversal
    assert rel is not None


def test_obligation_assessment_entitlement_events_relationship_exists():
    rel = ObligationAssessment.entitlement_events
    assert rel is not None
