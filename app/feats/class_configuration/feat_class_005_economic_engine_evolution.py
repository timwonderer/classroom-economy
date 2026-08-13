"""
FEAT-CLASS-005: Economic Engine Evolution (v1.0)

Orchestrates economic policy transitions per DOM-CLASS-002:
- Creates new immutable EconomicEngine version with new policy_mode
- Links all affected features to new engine version via class_features rows
- Preserves complete version chain via previous_version_id
- Supports future-law scheduling via effective_at per SPEC-ECON-002

Authority: DOM-CLASS-001, DOM-CLASS-002, INV-ARC-015, INV-ARC-016, SPEC-TIME-001, SPEC-ECON-002
Sole lawful writer for: economic_engine table + class_features rows for affected features

MED Blast Radius: Idempotency_key recommended but not required
Natural idempotency on (class_id, feature, effective_at) primary key tuple in class_features
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime as dt, timezone as tz
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell
from app.models import ClassEconomy, EconomicEngine, ClassFeature, Seat
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_economic_engine_history,
    is_feature_enabled,
)
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION


class EconomicEngineEvolutionError(Exception):
    """Raised when engine evolution validation or execution fails."""
    pass


@dataclass
class EconomicEngineEvolutionResult:
    """Result of successful economic engine evolution."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    new_engine_id: Optional[str] = None
    new_policy_mode: Optional[str] = None
    features_updated: list[str] = field(default_factory=list)
    effective_at: Optional[str] = None  # ISO 8601 timestamp
    error_code: Optional[str] = None
    error_message: Optional[str] = None


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
    """
    Execute lawful teacher-directed economic policy transition.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        class_id: Class to modify
        new_policy_mode: Target mode ('tight', 'default', 'comfortable')
        feature_list: List of features affected by this transition (e.g., ['payroll', 'rent'])
        effective_at: When this policy transition takes effect (default: canonical_now, ISO 8601 string)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        EconomicEngineEvolutionResult with success status and engine details

    Contract: Teacher authority and class scope are validated via CanonicalContext.
    All affected features must currently be enabled.
    Engine versions are immutable once committed; policy evolution is versioned history.
    """
    return _execute_transition_economic_policy_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        new_policy_mode=new_policy_mode,
        feature_list=feature_list,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-CLASS-005")
def _execute_transition_economic_policy_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    new_policy_mode: str,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
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

    # Validate policy mode
    valid_modes = ('tight', 'default', 'comfortable')
    if new_policy_mode not in valid_modes:
        return EconomicEngineEvolutionResult(
            success=False,
            correlation_id="",
            error_code="INVALID_POLICY_MODE",
            error_message=f"Policy mode '{new_policy_mode}' is not valid. Must be one of: {', '.join(valid_modes)}",
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
        # Let resolver handle the timestamp normalization and comparison
        # Use earlier_than to check if effective_at is before now
        try:
            earlier_eval = canonical_temporal_resolver(
                CLASS_LEVEL_EVALUATION,
                canonical_execution_context=canonical_context,
                primitive="earlier_than",
                candidate=effective_at,
                reference=timestamp_utc,
            )
            if earlier_eval.is_earlier:
                return EconomicEngineEvolutionResult(
                    success=False,
                    correlation_id="",
                    error_code="INVALID_TEMPORAL_ORDER",
                    error_message=f"effective_at cannot be in the past",
                )
            # Parse effective_at into a proper datetime
            try:
                effective_at_ts = dt.fromisoformat(effective_at)
                if effective_at_ts.tzinfo is None:
                    effective_at_ts = effective_at_ts.replace(tzinfo=tz.utc)
            except ValueError:
                return EconomicEngineEvolutionResult(
                    success=False,
                    correlation_id="",
                    error_code="INVALID_EFFECTIVE_AT",
                    error_message="effective_at must be a valid ISO 8601 datetime string",
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
        # All feature rows already exist: full idempotent return
        new_engine = db.session.query(EconomicEngine).filter_by(
            class_id=class_id,
        ).order_by(EconomicEngine.created_at.desc()).first()
        return EconomicEngineEvolutionResult(
            success=True,
            correlation_id=idempotency_key or f"engine_evolution_idempotent_{class_id}",
            class_id=class_id,
            new_engine_id=new_engine.economic_version_id if new_engine else None,
            new_policy_mode=new_policy_mode,
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

    # Create new EconomicEngine version
    new_engine_id = str(uuid.uuid4())
    new_engine = EconomicEngine(
        economic_version_id=new_engine_id,
        class_id=class_id,
        economy_policy_mode=new_policy_mode,
        previous_version_id=current_engine.economic_version_id,  # Link to previous version
        created_at=timestamp_utc,
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
        new_policy_mode=new_policy_mode,
        features_updated=sorted(feature_list),
        effective_at=effective_at_ts.isoformat(),
        error_code=None,
        error_message=None,
    )
