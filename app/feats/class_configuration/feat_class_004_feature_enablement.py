"""
FEAT-CLASS-004: Feature Enablement/Disablement (v1.0)

Orchestrates class feature state mutations per DOM-CLASS-002:
- Enable feature: append new class_features row with economic_version_id link
- Disable feature: append new class_features row with deleted_at timestamp (soft deletion)
- Timeline is immutable and append-only per INV-ARC-016

Authority: DOM-CLASS-001, DOM-CLASS-002, INV-ARC-015, INV-ARC-016, SPEC-TIME-001, SPEC-ECON-002
Sole lawful writer for: class_features table (ClassFeature model)

MED Blast Radius: Idempotency_key recommended but not required
Natural idempotency on (class_id, feature, effective_at) primary key tuple
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell
from app.models import ClassEconomy, EconomicEngine, ClassFeature, Seat
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_initial_economic_engine,
    is_feature_enabled,
)
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION


class FeatureEnablementError(Exception):
    """Raised when feature enablement validation or execution fails."""
    pass


@dataclass
class FeatureEnablementResult:
    """Result of successful feature enablement."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    feature: Optional[str] = None
    effective_at: Optional[str] = None  # ISO 8601 timestamp
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class FeatureDisablementResult:
    """Result of successful feature disablement."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    feature: Optional[str] = None
    effective_at: Optional[str] = None  # ISO 8601 timestamp
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_enable_feature(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    feature: str,
    economic_version_id: str,
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> FeatureEnablementResult:
    """
    Execute lawful teacher-directed feature enablement.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        class_id: Class to modify
        feature: Feature name ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')
        economic_version_id: EconomicEngine version UUID that governs this feature
        effective_at: When this enablement takes effect (default: canonical_now, ISO 8601 string)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        FeatureEnablementResult with success status and feature details

    Contract: Teacher authority and class scope are validated via CanonicalContext.
    Feature enablement is immutable once committed (append-only).
    """
    return _execute_enable_feature_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        feature=feature,
        economic_version_id=economic_version_id,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


def execute_disable_feature(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    feature: str,
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> FeatureDisablementResult:
    """
    Execute lawful teacher-directed feature disablement (soft deletion).

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        class_id: Class to modify
        feature: Feature name to disable
        effective_at: When this disablement takes effect (default: canonical_now, ISO 8601 string)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        FeatureDisablementResult with success status and feature details

    Contract: Feature must currently be enabled.
    Disablement creates new row with deleted_at timestamp per INV-ARC-016.
    """
    return _execute_disable_feature_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        feature=feature,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-CLASS-004")
def _execute_enable_feature_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    feature: str,
    economic_version_id: str,
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> FeatureEnablementResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate class_id matches canonical context
    if class_id != canonical_context.class_id:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    # Validate actor is teacher
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="UNAUTHORIZED",
            error_message="Only teachers can enable features",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate class exists
    class_economy = get_class_economy(class_id)
    if not class_economy:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="CLASS_NOT_FOUND",
            error_message=f"Class {class_id} not found",
        )

    # Validate feature name
    valid_features = ClassFeature.feature_names()
    if feature not in valid_features:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="INVALID_FEATURE",
            error_message=f"Feature '{feature}' is not valid. Must be one of: {', '.join(valid_features)}",
        )

    # Validate economic_version_id exists and belongs to this class
    engine_version = db.session.query(EconomicEngine).filter_by(
        economic_version_id=economic_version_id,
        class_id=class_id,
    ).first()
    if not engine_version:
        return FeatureEnablementResult(
            success=False,
            correlation_id="",
            error_code="ENGINE_VERSION_NOT_FOUND",
            error_message=f"Economic engine version {economic_version_id} not found for class {class_id}",
        )

    # Get current timestamp via canonical temporal resolver (CLE)
    temporal_eval = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=canonical_context,
        primitive="current_time",
    )
    timestamp_utc = temporal_eval.canonical_now_utc

    # Use resolver to parse and validate effective_at
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
                return FeatureEnablementResult(
                    success=False,
                    correlation_id="",
                    error_code="INVALID_TEMPORAL_ORDER",
                    error_message=f"effective_at cannot be in the past",
                )
            # If not earlier, use the effective_at; resolver will normalize it
            effective_at_ts = effective_at
        except Exception as e:
            return FeatureEnablementResult(
                success=False,
                correlation_id="",
                error_code="INVALID_TEMPORAL_ORDER",
                error_message=f"Cannot validate effective_at timestamp: {str(e)}",
            )
    else:
        effective_at_ts = timestamp_utc

    # Idempotency check: look for existing row at same (class_id, feature, effective_at)
    existing_row = db.session.query(ClassFeature).filter_by(
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts,
    ).first()
    if existing_row:
        # Row already exists: return idempotent result
        return FeatureEnablementResult(
            success=True,
            correlation_id=idempotency_key or f"enable_feature_{uuid.uuid4().hex}",
            class_id=class_id,
            feature=feature,
            effective_at=effective_at_ts.isoformat(),
        )

    # Generate correlation ID
    corr_id = correlation_id or idempotency_key or f"enable_feature_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Atomic Feature Enablement
    # =========================================================================

    # Create and insert class_features row
    class_feature = ClassFeature(
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts,
        economic_version_id=economic_version_id,
        deleted_at=None,
        created_at=timestamp_utc,
    )
    db.session.add(class_feature)
    db.session.flush()

    return FeatureEnablementResult(
        success=True,
        correlation_id=corr_id,
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts.isoformat(),
        error_code=None,
        error_message=None,
    )


@feat_shell("FEAT-CLASS-004")
def _execute_disable_feature_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    feature: str,
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> FeatureDisablementResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    # Validate class_id matches canonical context
    if class_id != canonical_context.class_id:
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    # Validate actor is teacher
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="UNAUTHORIZED",
            error_message="Only teachers can disable features",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id:
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate class exists
    class_economy = get_class_economy(class_id)
    if not class_economy:
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="CLASS_NOT_FOUND",
            error_message=f"Class {class_id} not found",
        )

    # Validate feature name
    valid_features = ClassFeature.feature_names()
    if feature not in valid_features:
        return FeatureDisablementResult(
            success=False,
            correlation_id="",
            error_code="INVALID_FEATURE",
            error_message=f"Feature '{feature}' is not valid. Must be one of: {', '.join(valid_features)}",
        )

    # Validate feature is currently enabled
    if not is_feature_enabled(class_id, feature):
        return FeatureDisablementResult(
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
                return FeatureDisablementResult(
                    success=False,
                    correlation_id="",
                    error_code="INVALID_TEMPORAL_ORDER",
                    error_message=f"effective_at cannot be in the past",
                )
            # If not earlier, use the effective_at; resolver will normalize it
            effective_at_ts = effective_at
        except Exception as e:
            return FeatureDisablementResult(
                success=False,
                correlation_id="",
                error_code="INVALID_TEMPORAL_ORDER",
                error_message=f"Cannot validate effective_at timestamp: {str(e)}",
            )
    else:
        effective_at_ts = timestamp_utc

    # Idempotency check: look for existing disablement row at same (class_id, feature, effective_at)
    # with deleted_at set
    existing_row = db.session.query(ClassFeature).filter_by(
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts,
    ).filter(ClassFeature.deleted_at.isnot(None)).first()
    if existing_row:
        # Disablement already exists at this effective_at: return idempotent result
        return FeatureDisablementResult(
            success=True,
            correlation_id=idempotency_key or f"disable_feature_{uuid.uuid4().hex}",
            class_id=class_id,
            feature=feature,
            effective_at=effective_at_ts.isoformat(),
        )

    # Generate correlation ID
    corr_id = correlation_id or idempotency_key or f"disable_feature_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Atomic Feature Disablement (Soft Deletion)
    # =========================================================================

    # Create and insert class_features row with deleted_at set (soft deletion)
    # This marks the feature as disabled without removing the historical record
    class_feature = ClassFeature(
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts,
        economic_version_id=None,  # Disabled features don't link to an engine version
        deleted_at=timestamp_utc,  # Soft deletion timestamp
        created_at=timestamp_utc,
    )
    db.session.add(class_feature)
    db.session.flush()

    return FeatureDisablementResult(
        success=True,
        correlation_id=corr_id,
        class_id=class_id,
        feature=feature,
        effective_at=effective_at_ts.isoformat(),
        error_code=None,
        error_message=None,
    )
