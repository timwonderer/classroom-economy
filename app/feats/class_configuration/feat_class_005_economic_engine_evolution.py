"""
FEAT-CLASS-005: Economic Engine Evolution (v1.1)

Orchestrates economic engine field transitions per DOM-CLASS-002:
- Creates new immutable EconomicEngine version with any subset of updated fields
- Carries forward all unchanged fields from the current engine
- Links all affected features to new engine version via class_features rows
- Preserves complete version chain via previous_version_id
- Supports future-law scheduling via effective_at per SPEC-ECON-002

Authority: DOM-CLASS-001, DOM-CLASS-002, INV-ARC-015, INV-ARC-016, SPEC-TIME-001, SPEC-ECON-002
Sole lawful writer for: economic_engine table + class_features rows for affected features

MED Blast Radius: Idempotency_key recommended but not required
Natural idempotency on (class_id, feature, effective_at) primary key tuple in class_features

v1.1 (2026-08-15): Generalized from policy-mode-only to arbitrary EconomicEngine field
updates. `execute_transition_economic_policy` retained as backward-compat wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime as dt, timezone as tz
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import ClassEconomy, EconomicEngine, ClassFeature, Seat
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_economic_engine_by_version,
    get_economic_engine_history,
    is_feature_enabled,
)
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION


class EconomicEngineEvolutionError(Exception):
    """Raised when engine evolution validation or execution fails."""
    pass


# Whitelist of EconomicEngine fields that may be mutated via FEAT-CLASS-005,
# with validators. Any field not listed here cannot be updated through this FEAT.
_VALID_POLICY_MODES = ('tight', 'default', 'comfortable')
_VALID_CALC_TYPES = ('simple', 'compound')
_VALID_COMPOUND_FREQS = ('never', 'daily', 'weekly', 'monthly')
_VALID_ACCRUAL_FREQS = ('daily', 'weekly', 'monthly')
_VALID_PAYOUT_FREQS = ('weekly', 'monthly')


def _validate_engine_field(field_name: str, value):
    """Validate a single EconomicEngine field update. Returns (ok, error_message)."""
    if field_name == 'economy_policy_mode':
        if value not in _VALID_POLICY_MODES:
            return False, f"economy_policy_mode must be one of {_VALID_POLICY_MODES}"
    elif field_name == 'expected_weekly_hours':
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, "expected_weekly_hours must be numeric"
        if v <= 0:
            return False, "expected_weekly_hours must be > 0"
    elif field_name == 'interest_rate':
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, "interest_rate must be numeric"
        if v < 0 or v > 1.0:
            return False, "interest_rate must be between 0 and 1.0"
    elif field_name == 'interest_calculation_type':
        if value is not None and value not in _VALID_CALC_TYPES:
            return False, f"interest_calculation_type must be one of {_VALID_CALC_TYPES}"
    elif field_name == 'compound_frequency':
        if value is not None and value not in _VALID_COMPOUND_FREQS:
            return False, f"compound_frequency must be one of {_VALID_COMPOUND_FREQS}"
    elif field_name == 'interest_accrual_frequency':
        if value is not None and value not in _VALID_ACCRUAL_FREQS:
            return False, f"interest_accrual_frequency must be one of {_VALID_ACCRUAL_FREQS}"
    elif field_name == 'interest_payout_frequency':
        if value is not None and value not in _VALID_PAYOUT_FREQS:
            return False, f"interest_payout_frequency must be one of {_VALID_PAYOUT_FREQS}"
    else:
        return False, f"'{field_name}' is not a valid EconomicEngine field for FEAT-CLASS-005"
    return True, None


# Fields carried forward from the current engine when creating a new version.
_CARRY_FORWARD_FIELDS = (
    'economy_policy_mode',
    'expected_weekly_hours',
    'interest_rate',
    'interest_calculation_type',
    'compound_frequency',
    'interest_accrual_frequency',
    'interest_payout_frequency',
)


def _parse_effective_at_timestamp(effective_at: str):
    """Parse ISO 8601 effective_at into a timezone-aware datetime."""
    try:
        effective_at_ts = dt.fromisoformat(effective_at)
    except ValueError:
        return None
    if effective_at_ts.tzinfo is None:
        effective_at_ts = effective_at_ts.replace(tzinfo=tz.utc)
    return effective_at_ts


@dataclass
class EconomicEngineEvolutionResult:
    """Result of successful economic engine evolution."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    new_engine_id: Optional[str] = None
    new_policy_mode: Optional[str] = None  # Kept for backward compat with policy-mode callers
    updates_applied: dict = field(default_factory=dict)  # Full set of fields written
    features_updated: list[str] = field(default_factory=list)
    effective_at: Optional[str] = None  # ISO 8601 timestamp
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_evolve_economic_engine(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    updates: dict,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """
    Execute lawful teacher-directed EconomicEngine field evolution.

    Creates a new immutable EconomicEngine version with the requested field updates
    applied on top of the current engine's values, and links the specified features
    to the new version via class_features rows.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        class_id: Class to modify
        updates: Dict of EconomicEngine field name → new value. Fields not present
                 are carried forward from the current engine. Whitelist enforced.
                 Supported keys:
                     economy_policy_mode, expected_weekly_hours, interest_rate,
                     interest_calculation_type, compound_frequency,
                     interest_accrual_frequency, interest_payout_frequency
        feature_list: List of features affected by this transition (e.g., ['payroll', 'rent'])
        effective_at: When this transition takes effect (default: canonical_now, ISO 8601 string)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        EconomicEngineEvolutionResult with success status and engine details.
    """
    return _execute_evolve_economic_engine_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        updates=updates,
        feature_list=feature_list,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


def execute_transition_economic_policy(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    new_policy_mode: str,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """Backward-compat wrapper: policy-mode-only transition.

    Prefer `execute_evolve_economic_engine(updates={...})` for new callers.
    """
    return _execute_evolve_economic_engine_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        updates={'economy_policy_mode': new_policy_mode},
        feature_list=feature_list,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-CLASS-005")
def _execute_evolve_economic_engine_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    updates: dict,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """
    Internal implementation wrapped in @requires_feat_context for context management.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate class_id matches canonical context
    if class_id != canonical_context.class_id:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    # Validate actor is teacher
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="UNAUTHORIZED",
            error_message="Only teachers can transition economic policy",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate class exists
    class_economy = get_class_economy(class_id)
    if not class_economy:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="CLASS_NOT_FOUND",
            error_message=f"Class {class_id} not found",
        )

    # Validate updates dict: non-empty and every field passes its validator
    if not updates or not isinstance(updates, dict):
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="INVALID_UPDATES",
            error_message="updates must be a non-empty dict of EconomicEngine field → value",
        )
    for field_name, value in updates.items():
        ok, err = _validate_engine_field(field_name, value)
        if not ok:
            return EconomicEngineEvolutionResult(
                success=False,
                correlation_id="",
                error_code="INVALID_UPDATES",
                error_message=err,
            )

    # Validate feature_list is not empty
    if not feature_list or not isinstance(feature_list, list):
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="INVALID_FEATURE_LIST",
            error_message="feature_list must be a non-empty list",
        )

    # Validate each feature
    valid_features = ClassFeature.feature_names()
    for feature in feature_list:
        if feature not in valid_features:
            return EconomicEngineEvolutionResult(
                success=False,
                correlation_id="",
                error_code="INVALID_FEATURE",
                error_message=f"Feature '{feature}' is not valid. Must be one of: {', '.join(valid_features)}",
            )
        # Validate feature is currently enabled
        if not is_feature_enabled(class_id, feature):
            return EconomicEngineEvolutionResult(
                success=False,
                correlation_id="",
                error_code="FEATURE_NOT_ENABLED",
                error_message=f"Feature '{feature}' is not currently enabled for class {class_id}",
            )

    # Get current timestamp via canonical temporal resolver (CLE)
    temporal_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="current_time",
    )
    timestamp_utc = temporal_eval.canonical_now_utc

    # Use resolver to validate effective_at
    # If effective_at provided, resolver normalizes it; otherwise use current time
    if effective_at:
        effective_at_ts = _parse_effective_at_timestamp(effective_at)
        if effective_at_ts is None:
            return EconomicEngineEvolutionResult(
                success=False,
                correlation_id="",
                error_code="INVALID_EFFECTIVE_AT",
                error_message="effective_at must be a valid ISO 8601 datetime string",
            )
        try:
            earlier_eval = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=canonical_context,
                primitive="earlier_than",
                candidate=effective_at_ts,
                reference=timestamp_utc,
            )
            if earlier_eval.is_earlier:
                return EconomicEngineEvolutionResult(
                    success=False,
                    correlation_id="",
                    error_code="INVALID_TEMPORAL_ORDER",
                    error_message=f"effective_at cannot be in the past",
                )
        except Exception as e:
            return EconomicEngineEvolutionResult(
                success=False,
                correlation_id="",
                error_code="INVALID_TEMPORAL_ORDER",
                error_message=f"Cannot validate effective_at timestamp: {str(e)}",
            )
    else:
        effective_at_ts = timestamp_utc

    # Idempotency check: identify which features already have rows at this effective_at
    missing_features = []
    for feature in feature_list:
        existing_row = db.session.query(ClassFeature).filter_by(
            class_id=class_id,
            feature=feature,
            effective_at=effective_at_ts,
        ).first()
        if not existing_row:
            missing_features.append(feature)

    if not missing_features:
        # All feature rows already exist: resolve engine from persisted ClassFeature
        # Use the first feature's economic_version_id to find the actual engine
        anchor_row = db.session.query(ClassFeature).filter_by(
            class_id=class_id,
            feature=feature_list[0],
            effective_at=effective_at_ts,
        ).first()
        persisted_engine = None
        if anchor_row and anchor_row.economic_version_id:
            persisted_engine = get_economic_engine_by_version(
                class_id, anchor_row.economic_version_id
            )
        return EconomicEngineEvolutionResult(
            success=True,
            correlation_id=idempotency_key or f"engine_evolution_idempotent_{class_id}",
            class_id=class_id,
            new_engine_id=persisted_engine.economic_version_id if persisted_engine else None,
            new_policy_mode=persisted_engine.economy_policy_mode if persisted_engine else updates.get('economy_policy_mode'),
            updates_applied=dict(updates),
            features_updated=sorted(feature_list),
            effective_at=effective_at_ts.isoformat() if hasattr(effective_at_ts, 'isoformat') else effective_at_ts,
        )

    # Get current engine version (most recent first)
    engine_history = get_economic_engine_history(class_id)
    current_engine = engine_history[0] if engine_history else None
    if not current_engine:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="NO_CURRENT_ENGINE",
            error_message=f"No economic engine version found for class {class_id}",
        )

    # Generate correlation ID
    corr_id = correlation_id or idempotency_key or f"engine_evolution_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Atomic Economic Engine Evolution
    # =========================================================================

    # Create new EconomicEngine version: carry forward every field from the current
    # engine, then overwrite with requested updates. This preserves the invariant
    # that each version is a complete self-describing snapshot.
    new_engine_id = str(uuid.uuid4())
    carried_fields = {
        field_name: getattr(current_engine, field_name)
        for field_name in _CARRY_FORWARD_FIELDS
    }
    carried_fields.update(updates)

    new_engine = EconomicEngine(
        economic_version_id=new_engine_id,
        class_id=class_id,
        previous_version_id=current_engine.economic_version_id,  # Link to previous version
        created_at=timestamp_utc,
        **carried_fields,
    )
    db.session.add(new_engine)
    db.session.flush()

    # Create class_features rows only for features not yet persisted (partial replay safe)
    for feature in missing_features:
        class_feature = ClassFeature(
            class_id=class_id,
            feature=feature,
            effective_at=effective_at_ts,
            economic_version_id=new_engine_id,
            deleted_at=None,
            created_at=timestamp_utc,
        )
        db.session.add(class_feature)

    db.session.flush()

    return EconomicEngineEvolutionResult(
        success=True,
        correlation_id=corr_id,
        class_id=class_id,
        new_engine_id=new_engine_id,
        new_policy_mode=carried_fields.get('economy_policy_mode'),
        updates_applied=dict(updates),
        features_updated=sorted(feature_list),
        effective_at=effective_at_ts.isoformat(),
        error_code=None,
        error_message=None,
    )
